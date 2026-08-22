"""
Backend wrapper around the existing ai_model predictor.

This is the only backend module that imports or calls the AI project. The
backend does not duplicate ROI extraction, preprocessing, regression, confidence,
or uncertainty logic.
"""
from __future__ import annotations

import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .input_domain_gate import (
    DomainGateResult,
    build_rejection_payload,
    validate_conjunctiva_input,
)
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class AIService:
    """Singleton-style service for loading and reusing AnaemiaPredictor."""

    def __init__(self) -> None:
        self._predictor: Any | None = None
        self._ready = False
        self._load_error: str | None = None
        self._load_seconds: float | None = None
        self._settings = get_settings()

    def initialize(self) -> bool:
        """Import ai_model and load the checkpoint once."""
        start = time.perf_counter()
        model_root = self._settings.ai_model_root
        model_path = self._settings.resolved_ai_model_path

        if str(model_root) not in sys.path:
            sys.path.insert(0, str(model_root))

        try:
            from src.inference.predictor import AnaemiaPredictor

            self._predictor = AnaemiaPredictor(
                model_path=model_path,
                device=self._settings.AI_DEVICE,
            )
            self._ready = bool(self._predictor.load())
            self._load_error = None if self._ready else "MODEL_NOT_READY"
        except Exception as exc:
            logger.error("AI model initialization failed: %s", exc, exc_info=True)
            self._predictor = None
            self._ready = False
            self._load_error = "MODEL_NOT_READY"

        self._load_seconds = time.perf_counter() - start
        if self._ready:
            logger.info("AI model loaded in %.3fs", self._load_seconds)
        else:
            logger.warning("AI model not ready after %.3fs", self._load_seconds)
        return self._ready

    def is_ready(self) -> bool:
        return bool(self._ready and self._predictor is not None)

    def get_model_info(self) -> dict[str, Any]:
        """Return actual model state without exposing local absolute paths."""
        if not self.is_ready():
            return {
                "ready": False,
                "available": False,
                "status": "MODEL_NOT_READY",
                "model": {
                    "name": "MobileNetV3-small",
                    "version": "anaemia-hb-mobilenetv3-v1",
                    "checkpoint": self._settings.AI_MODEL_PATH,
                },
                "load_seconds": self._load_seconds,
            }

        info = self._predictor.get_model_info()
        info["checkpoint"] = self._settings.AI_MODEL_PATH
        return {
            "ready": True,
            "available": True,
            "status": "MODEL_READY",
            "model": info,
            "load_seconds": self._load_seconds,
        }

    def predict_upload(
        self,
        image_bytes: bytes,
        image_suffix: str,
        mask_bytes: bytes | None = None,
        mask_suffix: str = ".png",
        subject_id: str = "api_upload",
    ) -> dict[str, Any]:
        """Run the inference firewall, then existing AI inference for uploads.

        MANDATORY FLOW (fail-closed):
            1. validate_conjunctiva_input()  <- the ONLY route to the model
            2. if invalid  -> structured rejection; predictor NEVER called
            3. if valid    -> predict_from_path with the VALIDATED mask only
        """
        logger.info("REQUEST RECEIVED | subject=%s | bytes=%d", subject_id, len(image_bytes))

        if not self.is_ready():
            return {
                "success": False,
                "status": "MODEL_NOT_READY",
                "data": {
                    "retry": True,
                    "message": "The AI screening model is not currently available.",
                },
            }

        # ── INFERENCE FIREWALL — single mandatory validation checkpoint ───
        logger.info("VALIDATION START")
        try:
            gate_result = validate_conjunctiva_input(image_bytes, mask_bytes)
        except Exception:
            # Fail closed: an exception inside validation must never reach the
            # Hb model. Report a structured rejection instead.
            logger.error("Domain gate raised unexpectedly", exc_info=True)
            gate_failure = DomainGateResult(
                valid=False,
                status="INVALID_INPUT",
                error={
                    "code": "VALIDATION_FAILED",
                    "message": "The image could not be validated.",
                    "retryable": True,
                },
                validation={"domain": None, "mask_source": None, "roi_quality": None},
            )
            return build_rejection_payload(gate_failure)

        if not gate_result.valid:
            rejection = build_rejection_payload(gate_result)
            logger.info(
                "HB MODEL INVOKED=NO | reason=%s",
                gate_result.error_code,
            )
            return self._sanitize_result(rejection)

        assert gate_result.validated_mask_png is not None  # guaranteed by gate

        image_suffix = image_suffix if image_suffix.startswith(".") else ".jpg"
        mask_suffix = mask_suffix if mask_suffix.startswith(".") else ".png"

        image_path: Path | None = None
        mask_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=image_suffix, delete=False) as image_tmp:
                image_tmp.write(image_bytes)
                image_path = Path(image_tmp.name)

            # ONLY the gate-validated mask may be used for ROI extraction.
            with tempfile.NamedTemporaryFile(suffix=mask_suffix, delete=False) as mask_tmp:
                mask_tmp.write(gate_result.validated_mask_png)
                mask_path = Path(mask_tmp.name)

            logger.info(
                "DOMAIN RESULT=%s ROI RESULT=%s QUALITY RESULT=%s",
                gate_result.validation.get("domain") or "VALID",
                "VALID",
                (gate_result.validation.get("roi_quality") or {}).get("quality_status"),
            )

            start = time.perf_counter()
            result = self._predictor.predict_from_path(
                image_path=image_path,
                mask_path=mask_path,
                subject_id=subject_id,
            )
            result.setdefault("meta", {})["inference_seconds"] = round(
                time.perf_counter() - start,
                4,
            )
            result.setdefault("validation", {})["domain_gate"] = {
                k: v for k, v in gate_result.validation.items()
                if k != "roi_quality"
            }
            result["validation"]["inference_authorized"] = True
            hb_invoked = bool(result.get("success"))
            logger.info("HB MODEL INVOKED=%s", "YES" if hb_invoked else "NO")
            return self._sanitize_result(result)
        except Exception as exc:
            logger.error("AI inference failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "status": "INFERENCE_ERROR",
                "data": {
                    "retry": False,
                    "message": "Inference failed. Please try again.",
                },
            }
        finally:
            for path in (image_path, mask_path):
                if path is None:
                    continue
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    logger.warning("Temporary upload cleanup failed for %s", path)

    def _sanitize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Keep structured AI output but avoid leaking internal paths/details."""
        if result.get("success") is True:
            data = result.get("data")
            required = (
                "estimated_hb_g_dl", "hb_std_g_dl", "confidence_interval_95",
                "confidence_status", "image_quality", "roi", "model",
            )
            if (
                result.get("status") != "PREDICTION_COMPLETE"
                or not isinstance(data, dict)
                or any(key not in data for key in required)
                or result.get("validation", {}).get("inference_authorized") is not True
            ):
                logger.error("Rejecting incomplete or unauthorized prediction payload")
                return {
                    "success": False,
                    "status": "INFERENCE_ERROR",
                    "error": {
                        "code": "UNAUTHORIZED_PREDICTION",
                        "message": "The prediction did not pass the validated ROI contract.",
                        "retryable": True,
                    },
                    "data": {
                        "retry": True,
                        "message": "The image could not be processed safely. Please retake it.",
                    },
                }
            return result

        status = result.get("status")
        data = result.setdefault("data", {})
        if status == "MODEL_NOT_READY":
            data["message"] = "The AI screening model is not currently available."
        elif status == "INFERENCE_ERROR":
            data["message"] = "Inference failed. Please try again."
        elif status in {"INVALID_INPUT", "EYE_NOT_DETECTED", "CONJUNCTIVA_NOT_DETECTED", "ROI_QUALITY_FAILED"}:
            error = result.setdefault(
                "error",
                {"code": "CONJUNCTIVA_NOT_DETECTED", "message": "", "retryable": True},
            )
            code = error.get("code", "")
            if code == "ROI_QUALITY_FAILED":
                data.setdefault(
                    "message",
                    "The image quality is insufficient. Please retake the image.",
                )
                error.setdefault(
                    "message",
                    "The detected region is not usable for screening "
                    "(sharpness/exposure/resolution).",
                )
            elif code in {"ROI_MASK_INVALID", "IMAGE_UNREADABLE"}:
                data.setdefault("message", "The uploaded file could not be used.")
            else:
                data.setdefault(
                    "message",
                    "Conjunctiva not detected. Please position the inner eyelid "
                    "correctly and capture the image again.",
                )
            # Hard guarantee: a rejection payload NEVER carries prediction data.
            for forbidden in (
                "estimated_hb_g_dl",
                "hb_std_g_dl",
                "confidence_interval_95",
                "confidence_status",
                "recommendation",
            ):
                data.pop(forbidden, None)
                result.pop(forbidden, None)
        elif status == "ROI_FAILED":
            data.setdefault(
                "message",
                "Could not locate a valid conjunctiva ROI. Please retake the image.",
            )
        elif status == "IMAGE_QUALITY_FAILED":
            data.setdefault(
                "message",
                "The image quality is insufficient. Please retake the image.",
            )
        return result


ai_service = AIService()
