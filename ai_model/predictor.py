"""Deployment wrapper for the backend-facing Hb predictor."""

from src.inference.predictor import AnaemiaPredictor

__all__ = ["AnaemiaPredictor"]
