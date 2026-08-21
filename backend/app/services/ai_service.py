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
        """Run existing AI inference for uploaded bytes."""
        if not self.is_ready():
            return {
                "success": False,
                "status": "MODEL_NOT_READY",
                "data": {
                    "retry": True,
                    "message": "The AI screening model is not currently available.",
                },
            }

        image_suffix = image_suffix if image_suffix.startswith(".") else ".jpg"
        mask_suffix = mask_suffix if mask_suffix.startswith(".") else ".png"

        image_path: Path | None = None
        mask_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=image_suffix, delete=False) as image_tmp:
                image_tmp.write(image_bytes)
                image_path = Path(image_tmp.name)

            if mask_bytes is not None:
                with tempfile.NamedTemporaryFile(suffix=mask_suffix, delete=False) as mask_tmp:
                    mask_tmp.write(mask_bytes)
                    mask_path = Path(mask_tmp.name)

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
            return result

        status = result.get("status")
        data = result.setdefault("data", {})
        if status == "MODEL_NOT_READY":
            data["message"] = "The AI screening model is not currently available."
        elif status == "INFERENCE_ERROR":
            data["message"] = "Inference failed. Please try again."
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
