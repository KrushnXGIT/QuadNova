"""Deployment wrapper for JSON-safe schemas."""

from src.inference.schemas import MODEL_NAME, MODEL_VERSION, build_failure_payload, build_success_payload, ensure_serializable

__all__ = ["MODEL_NAME", "MODEL_VERSION", "build_failure_payload", "build_success_payload", "ensure_serializable"]
