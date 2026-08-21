"""Backend-facing inference API for the anaemia screening model."""

from .predictor import AnaemiaPredictor
from .schemas import MODEL_NAME, MODEL_VERSION, ensure_serializable

__all__ = ["AnaemiaPredictor", "MODEL_NAME", "MODEL_VERSION", "ensure_serializable"]
