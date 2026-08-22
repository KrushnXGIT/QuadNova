"""
POST /api/v1/predict
GET  /api/v1/model/status
"""
from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from ..schemas.common import ModelStatusResponse, ResponseStatus
from ..services.ai_service import ai_service
from ..utils.validation import validate_upload
from ..utils.errors import AppError, InternalError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Prediction"])


@router.get("/model/status", response_model=ModelStatusResponse)
async def model_status() -> ModelStatusResponse:
    """Returns live model readiness — no caching."""
    info = ai_service.get_model_info()
    return ModelStatusResponse(**info)


@router.post("/predict")
async def predict(
    image: UploadFile = File(..., description="Conjunctival image (JPG/PNG/WebP)"),
    mask: UploadFile | None = File(
        None,
        description="Optional conjunctiva ROI mask required by the current AI model.",
    ),
) -> JSONResponse:
    """
    Main prediction endpoint.

    Accepts a multipart image upload and returns a structured JSON response
    that the Flutter result screen can parse directly.
    """
    t_start = time.perf_counter()
    logger.info(
        "Prediction request received | filename=%s content_type=%s",
        image.filename,
        image.content_type,
    )

    try:
        # ── Read upload ─────────────────────────────────────
        data = await image.read()

        # ── Validate ────────────────────────────────────────
        validate_upload(
            filename=image.filename or "upload",
            content_type=image.content_type or "",
            data=data,
        )

        mask_data = None
        mask_suffix = ".png"
        if mask is not None:
            mask_data = await mask.read()
            validate_upload(
                filename=mask.filename or "mask.png",
                content_type=mask.content_type or "",
                data=mask_data,
            )
            mask_suffix = os.path.splitext((mask.filename or "mask.png").lower())[1]

        image_suffix = os.path.splitext((image.filename or "upload.jpg").lower())[1]

        # ── Run existing AI pipeline ─────────────────────────
        result = ai_service.predict_upload(
            image_bytes=data,
            image_suffix=image_suffix,
            mask_bytes=mask_data,
            mask_suffix=mask_suffix,
        )

        elapsed = time.perf_counter() - t_start
        logger.info("Request completed in %.3fs | status=%s", elapsed, result.get("status"))

        return JSONResponse(
            content=result,
            status_code=_status_code_for(result),
        )

    except AppError as exc:
        elapsed = time.perf_counter() - t_start
        logger.warning(
            "AppError [%s] in %.3fs: %s",
            exc.status.value, elapsed, exc.message,
        )
        return JSONResponse(
            content={
                "success": False,
                "status": exc.status.value,
                "message": exc.message,
            },
            status_code=exc.status_code,
        )

    except Exception as exc:
        elapsed = time.perf_counter() - t_start
        logger.error("Unhandled error in %.3fs: %s", elapsed, exc, exc_info=True)
        err = InternalError()
        return JSONResponse(
            content={
                "success": False,
                "status": err.status.value,
                "message": err.message,
            },
            status_code=500,
        )

    finally:
        # Ensure upload bytes are released — images never persisted to disk
        await image.close()
        if mask is not None:
            await mask.close()


def _status_code_for(result) -> int:
    """Map response status to HTTP status code."""
    status = result.get("status") if isinstance(result, dict) else result.status
    status = status if isinstance(status, str) else status.value
    mapping = {
        ResponseStatus.PREDICTION_COMPLETE.value: 200,
        ResponseStatus.LOW_CONFIDENCE.value: 200,
        ResponseStatus.MODEL_NOT_READY.value: 503,
        ResponseStatus.IMAGE_QUALITY_FAILED.value: 422,
        ResponseStatus.ROI_FAILED.value: 422,
        "EYE_NOT_DETECTED": 422,
        "CONJUNCTIVA_NOT_DETECTED": 422,
        "ROI_QUALITY_FAILED": 422,
        ResponseStatus.INVALID_INPUT.value: 422,
        ResponseStatus.INFERENCE_ERROR.value: 500,
        ResponseStatus.INTERNAL_ERROR.value: 500,
    }
    return mapping.get(status, 200)
