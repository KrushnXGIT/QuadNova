"""Backend-friendly AnaemiaPredictor wrapper around the existing CV + Hb model pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union

import cv2
import numpy as np
import torch
from PIL import Image

from src.model.config import INPUT_SIZE, MODEL_DIR, QUALITY_OVERRIDES
from src.model.confidence import ConfidenceCalibrator
from src.model.decision import HbDecisionSystem
from src.model.model import HbRegressor
from src.vision.pipeline import process_subject
from src.vision.quality_gate import make_quality_gate

from .schemas import MODEL_NAME, MODEL_VERSION, build_failure_payload, ensure_serializable


class AnaemiaPredictor:
    """Thin backend-facing API around the existing CV pipeline and Hb regressor."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        mask_path: Optional[Union[str, Path]] = None,
        device: str = "cpu",
        quality_overrides: Optional[Dict[str, Any]] = None,
    ):
        default_model_path = MODEL_DIR / "hb_regressor_best.pt"
        self.model_path = Path(model_path) if model_path is not None else default_model_path
        self.mask_path = Path(mask_path) if mask_path is not None else None
        self.device = device
        self.quality_overrides = quality_overrides or QUALITY_OVERRIDES.copy()
        self.model: Optional[HbRegressor] = None
        self.model_info: Dict[str, Any] = {}
        self.loaded = False
        self.calibrator = ConfidenceCalibrator()

    def load(self) -> bool:
        """Load the checkpoint once and verify the saved architecture/weights match."""
        model_path = Path(self.model_path)
        if not model_path.is_file():
            self.loaded = False
            self.model = None
            self.model_info = {"status": "MODEL_NOT_READY", "checkpoint": str(model_path), "reason": "checkpoint missing"}
            return False

        try:
            checkpoint = torch.load(str(model_path), map_location=self.device, weights_only=False)
        except Exception as exc:
            self.loaded = False
            self.model = None
            self.model_info = {"status": "MODEL_NOT_READY", "checkpoint": str(model_path), "reason": f"checkpoint unreadable: {exc}"}
            return False

        config = checkpoint.get("config", {}) if isinstance(checkpoint, dict) else {}
        try:
            model = HbRegressor(
                pretrained=bool(config.get("pretrained", False)),
                freeze_backbone=bool(config.get("freeze_backbone", False)),
            ).to(self.device)
            state_dict = checkpoint["model_state_dict"] if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint else checkpoint
            model.load_state_dict(state_dict)
            model.eval()
        except Exception as exc:
            self.loaded = False
            self.model = None
            self.model_info = {"status": "MODEL_NOT_READY", "checkpoint": str(model_path), "reason": f"weights mismatch: {exc}"}
            return False

        self.model = model
        self.loaded = True
        self.model_info = {
            "name": MODEL_NAME,
            "architecture": "MobileNetV3-small regression",
            "version": MODEL_VERSION,
            "checkpoint": str(model_path),
            "input_size": list(INPUT_SIZE),
            "input_channels": 3,
            "preprocessing_version": "clahe_roi_norm_v1",
            "dataset_version": "verified_labels_v1",
            "metrics": {
                "train_mae": 6.24,
                "val_mae": 6.41,
                "test_mae": 6.33,
                "baseline_mae": 1.66,
                "r2": -11.13,
            },
            "known_limitations": [
                "Current model does not outperform the mean-Hb baseline.",
                "Uncertainty is experimental and should be treated as screening-only.",
                "Quality and ROI thresholds are heuristic, not clinically validated.",
            ],
        }
        return True

    def is_ready(self) -> bool:
        return bool(self.loaded and self.model is not None)

    def get_model_info(self) -> Dict[str, Any]:
        return ensure_serializable(self.model_info if self.model_info else {"name": MODEL_NAME, "version": MODEL_VERSION, "status": "not_loaded"})

    def predict_from_path(self, image_path: Union[str, Path], mask_path: Optional[Union[str, Path]] = None, subject_id: str = "inference") -> Dict[str, Any]:
        if not self.is_ready() and not self.load():
            return build_failure_payload("MODEL_NOT_READY", retry=True, message="Model checkpoint was not loaded successfully.")

        image_path = Path(image_path)
        if not image_path.is_file():
            return build_failure_payload("IMAGE_QUALITY_FAILED", retry=True, message="Input image file does not exist.")

        mask_path = Path(mask_path) if mask_path is not None else self.mask_path
        if mask_path is None or not Path(mask_path).is_file():
            return build_failure_payload("ROI_FAILED", retry=True, message="A valid conjunctiva ROI mask is required for prediction.")

        rgb = self._read_rgb_image(image_path)
        if rgb is None:
            return build_failure_payload("IMAGE_QUALITY_FAILED", retry=True, message="Image could not be decoded.")

        quality_gate = make_quality_gate(self.quality_overrides)
        quality_result = quality_gate.check(rgb)
        if quality_result["quality_status"] != "ACCEPTED":
            return {
                "success": False,
                "status": "IMAGE_QUALITY_FAILED",
                "data": {
                    "retry": True,
                    "message": "Please capture a clearer image.",
                    "failure_reasons": quality_result.get("failure_reasons", []),
                },
            }

        try:
            pipeline_result = process_subject(
                subject_id=subject_id,
                raw_path=str(image_path),
                mask_path=str(mask_path),
                quality_overrides=self.quality_overrides,
            )
        except Exception as exc:
            return build_failure_payload("INFERENCE_ERROR", retry=False, message=f"Pipeline error: {exc}")

        if not pipeline_result.accepted:
            reason = pipeline_result.quality_report.get("reject_reason", "unknown")
            if any(token in reason.upper() for token in ["ROI", "COVERAGE", "MASK", "EMPTY"]):
                return {"success": False, "status": "ROI_FAILED", "data": {"retry": True, "message": reason}}
            return {"success": False, "status": "IMAGE_QUALITY_FAILED", "data": {"retry": True, "message": reason}}

        roi_tensor = pipeline_result.roi_tensor
        if roi_tensor is None or roi_tensor.size == 0:
            return build_failure_payload("ROI_FAILED", retry=True, message="ROI extraction produced no usable image.")

        try:
            image_tensor = self._preprocess_roi(roi_tensor)
            result = self._predict_tensor(image_tensor, quality_result)
        except Exception as exc:
            return build_failure_payload("INFERENCE_ERROR", retry=False, message=f"Prediction failed: {exc}")

        return self._wrap_prediction_result(result, quality_result, pipeline_result)

    def predict(self, image: Any, mask_path: Optional[Union[str, Path]] = None, subject_id: str = "inference") -> Dict[str, Any]:
        """Public API accepting a path, NumPy array, or PIL image."""
        if not self.is_ready() and not self.load():
            return build_failure_payload("MODEL_NOT_READY", retry=True, message="Model checkpoint was not loaded successfully.")

        if isinstance(image, (str, Path)):
            return self.predict_from_path(image, mask_path=mask_path, subject_id=subject_id)
        if image is None:
            return build_failure_payload("IMAGE_QUALITY_FAILED", retry=True, message="Input image is missing.")

        rgb = self._coerce_rgb_image(image)
        if rgb is None:
            return build_failure_payload("IMAGE_QUALITY_FAILED", retry=True, message="Input image could not be decoded.")

        quality_gate = make_quality_gate(self.quality_overrides)
        quality_result = quality_gate.check(rgb)
        if quality_result["quality_status"] != "ACCEPTED":
            return {
                "success": False,
                "status": "IMAGE_QUALITY_FAILED",
                "data": {
                    "retry": True,
                    "message": "Please capture a clearer image.",
                    "failure_reasons": quality_result.get("failure_reasons", []),
                },
            }

        if mask_path is None and self.mask_path is None:
            return build_failure_payload("ROI_FAILED", retry=True, message="No ROI mask was supplied for the provided image.")

        mask_used = Path(mask_path) if mask_path is not None else self.mask_path
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_raw:
            raw_path = tmp_raw.name
        try:
            Image.fromarray(rgb.astype(np.uint8)).save(raw_path)
            return self.predict_from_path(raw_path, mask_path=mask_used, subject_id=subject_id)
        finally:
            try:
                Path(raw_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _read_rgb_image(self, image_path: Path) -> Optional[np.ndarray]:
        try:
            img = Image.open(image_path)
            img = img.convert("RGB")
            arr = np.asarray(img)
        except Exception:
            try:
                arr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
                if arr is None:
                    return None
                arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
            except Exception:
                return None
        if arr.ndim == 2:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
        return np.asarray(arr, dtype=np.uint8)

    def _coerce_rgb_image(self, image: Any) -> Optional[np.ndarray]:
        if isinstance(image, np.ndarray):
            arr = image
        elif hasattr(image, "convert"):
            try:
                arr = np.asarray(image.convert("RGB"))
            except Exception:
                return None
        else:
            return None

        if arr.ndim == 2:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
        elif arr.ndim == 3 and arr.shape[2] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
        elif arr.ndim != 3 or arr.shape[2] != 3:
            return None
        return np.asarray(arr, dtype=np.uint8)

    def _preprocess_roi(self, roi_tensor: np.ndarray) -> torch.Tensor:
        if roi_tensor.dtype != np.float32:
            roi_tensor = roi_tensor.astype(np.float32)
        if roi_tensor.ndim == 3 and roi_tensor.shape[-1] == 3:
            roi_tensor = np.transpose(roi_tensor, (2, 0, 1))
        else:
            raise ValueError(f"ROI tensor is not shaped as HxWx3: {roi_tensor.shape}")
        tensor = torch.from_numpy(roi_tensor).unsqueeze(0).float().to(self.device)
        if tensor.shape[-2:] != tuple(INPUT_SIZE):
            tensor = torch.nn.functional.interpolate(tensor, size=tuple(INPUT_SIZE), mode="bilinear", align_corners=False)
        return tensor

    def _predict_tensor(self, image_tensor: torch.Tensor, quality_result: Dict[str, Any]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Model not loaded")

        self.model.eval()
        with torch.no_grad():
            raw_pred = self.model(image_tensor)
        checkpoint = torch.load(str(self.model_path), map_location=self.device, weights_only=False)
        config = checkpoint.get("config", {}) if isinstance(checkpoint, dict) else {}
        target_mean = float(config.get("target_mean", 12.0))
        target_std = float(config.get("target_std", 1.0))
        estimate = float(raw_pred.cpu().squeeze(0).item())
        estimate = estimate * target_std + target_mean

        mc_samples = 25
        was_training = self.model.training
        self.model.train()
        with torch.no_grad():
            outputs = [float(self.model(image_tensor).cpu().squeeze(0).item()) for _ in range(mc_samples)]
        self.model.train(was_training)
        self.model.eval()
        samples = torch.tensor(outputs, dtype=torch.float32)
        std_mc = float(samples.std(unbiased=False).item()) * target_std

        decision = HbDecisionSystem(self.calibrator).decide(
            estimated_hb=estimate,
            uncertainty=std_mc,
            quality_status="ACCEPTED",
            quality_score=float(quality_result.get("quality_score", 0.75)),
            failure_reasons=[],
            model_version=MODEL_VERSION,
        )

        return {
            "estimated_hb_g_dl": estimate,
            "hb_std_g_dl": std_mc,
            "confidence_interval_95": decision["confidence_interval_95"],
            "confidence_status": decision["confidence_status"],
            "recommendation": "Screening estimate only. Consider confirmatory testing when appropriate.",
            "image_quality": {
                "status": "GOOD" if quality_result["quality_status"] == "ACCEPTED" else "FAILED",
                "score": float(quality_result.get("quality_score", 0.0)),
                "failure_reasons": list(quality_result.get("failure_reasons", [])),
            },
        }

    def _wrap_prediction_result(self, prediction: Dict[str, Any], quality_result: Dict[str, Any], pipeline_result: Any) -> Dict[str, Any]:
        payload = {
            "success": True,
            "status": "PREDICTION_COMPLETE",
            "data": {
                "estimated_hb_g_dl": float(prediction["estimated_hb_g_dl"]),
                "hb_std_g_dl": float(prediction["hb_std_g_dl"]),
                "confidence_interval_95": [float(v) for v in prediction["confidence_interval_95"]],
                "confidence_status": prediction["confidence_status"],
                "image_quality": {
                    "status": "GOOD" if quality_result["quality_status"] == "ACCEPTED" else "FAILED",
                    "score": float(quality_result.get("quality_score", 0.0)),
                    "failure_reasons": list(quality_result.get("failure_reasons", [])),
                },
                "roi": {"status": "VALID" if pipeline_result.accepted else "FAILED"},
                "recommendation": prediction["recommendation"],
                "model": {"name": MODEL_NAME, "version": MODEL_VERSION},
            },
        }
        return ensure_serializable(payload)

    def __call__(self, image: Any, mask_path: Optional[Union[str, Path]] = None, subject_id: str = "inference") -> Dict[str, Any]:
        return self.predict(image, mask_path=mask_path, subject_id=subject_id)
