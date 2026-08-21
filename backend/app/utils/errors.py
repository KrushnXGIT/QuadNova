"""
Safe, user-facing error messages.

Never exposes Python stack traces to the Flutter application.
All internal details are logged server-side only.
"""
from fastapi import HTTPException
from ..schemas.common import ResponseStatus


class AppError(Exception):
    """Base application error with a status code and safe message."""

    def __init__(
        self,
        status_code: int,
        status: ResponseStatus,
        message: str,
    ) -> None:
        self.status_code = status_code
        self.status = status
        self.message = message
        super().__init__(message)


# ── Specific error types ──────────────────────────────────

class NoImageError(AppError):
    def __init__(self) -> None:
        super().__init__(
            400,
            ResponseStatus.VALIDATION_ERROR,
            "No image file was provided. Please upload an image.",
        )


class UnsupportedFormatError(AppError):
    def __init__(self) -> None:
        super().__init__(
            415,
            ResponseStatus.VALIDATION_ERROR,
            "Unsupported file format. Please upload a JPG, PNG, or WebP image.",
        )


class FileTooLargeError(AppError):
    def __init__(self, max_mb: int) -> None:
        super().__init__(
            413,
            ResponseStatus.VALIDATION_ERROR,
            f"Image file is too large. Maximum allowed size is {max_mb} MB.",
        )


class FileTooSmallError(AppError):
    def __init__(self) -> None:
        super().__init__(
            400,
            ResponseStatus.VALIDATION_ERROR,
            "Image file appears to be empty or too small to process.",
        )


class InvalidImageError(AppError):
    def __init__(self) -> None:
        super().__init__(
            400,
            ResponseStatus.VALIDATION_ERROR,
            "The uploaded file could not be decoded as a valid image.",
        )


class ImageDimensionError(AppError):
    def __init__(self) -> None:
        super().__init__(
            400,
            ResponseStatus.VALIDATION_ERROR,
            "Image dimensions are too small for reliable analysis. "
            "Please capture a clearer, closer image.",
        )


class ImageQualityError(AppError):
    def __init__(self) -> None:
        super().__init__(
            422,
            ResponseStatus.IMAGE_QUALITY_FAILED,
            "The captured image does not meet the required quality conditions. "
            "Please ensure good lighting and a steady hand.",
        )


class ROIExtractionError(AppError):
    def __init__(self) -> None:
        super().__init__(
            422,
            ResponseStatus.IMAGE_QUALITY_FAILED,
            "Could not locate the conjunctival region in the image. "
            "Please ensure the lower eyelid is clearly visible.",
        )


class ModelNotReadyError(AppError):
    def __init__(self) -> None:
        super().__init__(
            503,
            ResponseStatus.MODEL_NOT_READY,
            "The AI screening model is not currently available. "
            "Please try again later.",
        )


class ModelInferenceError(AppError):
    def __init__(self) -> None:
        super().__init__(
            500,
            ResponseStatus.INFERENCE_ERROR,
            "An error occurred during analysis. Please try again.",
        )


class InternalError(AppError):
    def __init__(self) -> None:
        super().__init__(
            500,
            ResponseStatus.INTERNAL_ERROR,
            "An unexpected error occurred. Please try again.",
        )
