"""
Pydantic schemas — common types shared across endpoints.
"""
from enum import Enum
from pydantic import BaseModel
from pydantic import ConfigDict


class ResponseStatus(str, Enum):
    PREDICTION_COMPLETE = "PREDICTION_COMPLETE"
    LOW_CONFIDENCE      = "LOW_CONFIDENCE"
    IMAGE_QUALITY_FAILED = "IMAGE_QUALITY_FAILED"
    ROI_FAILED          = "ROI_FAILED"
    CONJUNCTIVA_NOT_DETECTED = "CONJUNCTIVA_NOT_DETECTED"
    INVALID_INPUT       = "INVALID_INPUT"
    MODEL_NOT_READY     = "MODEL_NOT_READY"
    INFERENCE_ERROR     = "INFERENCE_ERROR"
    VALIDATION_ERROR    = "VALIDATION_ERROR"
    INTERNAL_ERROR      = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    success: bool = False
    status: ResponseStatus
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str


class ModelStatusResponse(BaseModel):
    ready: bool = False
    available: bool = False
    model: dict | str
    version: str | None = None
    status: str
    load_seconds: float | None = None


class InfoResponse(BaseModel):
    application: str
    api_version: str
    model_name: str
    model_available: bool
    disclaimer: str
