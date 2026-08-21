"""Serializable schemas for the backend-facing model interface."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

MODEL_NAME = "MobileNetV3-small"
MODEL_VERSION = "anaemia-hb-mobilenetv3-v1"


def ensure_serializable(value: Any) -> Any:
    """Recursively convert values to JSON-friendly Python primitives."""
    if isinstance(value, dict):
        return {str(k): ensure_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [ensure_serializable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [ensure_serializable(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bool)):
        return value.item()
    if value is None:
        return None
    return value


def build_success_payload(model_name: str, model_version: str, prediction: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "success": True,
        "status": "PREDICTION_COMPLETE",
        "data": {
            "estimated_hb_g_dl": prediction["estimated_hb_g_dl"],
            "hb_std_g_dl": prediction["hb_std_g_dl"],
            "confidence_interval_95": prediction["confidence_interval_95"],
            "confidence_status": prediction["confidence_status"],
            "image_quality": {
                "status": prediction["image_quality"]["status"],
                "score": prediction["image_quality"]["score"],
                "failure_reasons": prediction["image_quality"]["failure_reasons"],
            },
            "roi": {"status": prediction["roi"]["status"]},
            "recommendation": prediction["recommendation"],
            "model": {"name": model_name, "version": model_version},
        },
    }
    return ensure_serializable(payload)


def build_failure_payload(status: str, retry: bool = False, message: str = "") -> Dict[str, Any]:
    payload = {"success": False, "status": status}
    if status in {"IMAGE_QUALITY_FAILED", "ROI_FAILED"}:
        payload["data"] = {"retry": bool(retry), "message": message or "Please retake the image or provide a valid ROI mask."}
    elif status == "MODEL_NOT_READY":
        payload["data"] = {"retry": bool(retry), "message": message or "Model is not available."}
    elif status == "INFERENCE_ERROR":
        payload["data"] = {"retry": False, "message": message or "Inference failed."}
    return ensure_serializable(payload)
