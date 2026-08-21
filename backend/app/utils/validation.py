"""
Image validation — file-level checks before any CV processing.
"""
import io
import logging
import os

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from ..core.config import get_settings
from .errors import (
    FileTooLargeError,
    FileTooSmallError,
    UnsupportedFormatError,
    InvalidImageError,
    ImageDimensionError,
)

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/octet-stream",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Minimum acceptable image dimensions (pixels)
MIN_WIDTH  = 100
MIN_HEIGHT = 100


def _decode_image(data: bytes) -> np.ndarray:
    """
    Decode upload bytes to an RGB numpy array.

    Pillow is preferred because it handles EXIF orientation and common camera
    formats well. OpenCV is a fallback for PNGs with malformed ancillary chunks,
    which were observed in the sample dataset verification.
    """
    try:
        pil_img = Image.open(io.BytesIO(data))
        pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
        return np.array(pil_img)
    except UnidentifiedImageError:
        logger.warning("Pillow could not identify uploaded image")
    except Exception as exc:
        logger.warning("Pillow decode failed; trying OpenCV fallback: %s", exc)

    np_bytes = np.frombuffer(data, dtype=np.uint8)
    decoded = cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)
    if decoded is None:
        raise InvalidImageError()

    return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)


def validate_upload(
    filename: str,
    content_type: str,
    data: bytes,
) -> np.ndarray:
    """
    Run all file-level validation checks and return a decoded numpy image.

    Raises a typed AppError on any failure — never exposes internals.
    """
    settings = get_settings()

    # 1. Empty file
    if not data:
        logger.warning("Upload rejected: empty file bytes")
        raise FileTooSmallError()

    # 2. File size
    size_bytes = len(data)
    if size_bytes > settings.max_upload_bytes:
        logger.warning(
            "Upload rejected: size %d bytes > max %d bytes",
            size_bytes,
            settings.max_upload_bytes,
        )
        raise FileTooLargeError(settings.MAX_UPLOAD_SIZE_MB)

    if size_bytes < 1024:  # < 1 KB is almost certainly not a real image
        logger.warning("Upload rejected: suspiciously small (%d bytes)", size_bytes)
        raise FileTooSmallError()

    # 3. File extension
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning("Upload rejected: extension=%s", ext)
        raise UnsupportedFormatError()

    # 4. MIME type. Flutter multipart uploads may arrive as
    # application/octet-stream, so the byte decoder remains the final authority.
    if content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning("Upload rejected: content-type=%s", content_type)
        raise UnsupportedFormatError()

    # 5. Decode image
    try:
        image_rgb = _decode_image(data)
    except InvalidImageError:
        logger.warning("Upload rejected: could not decode as image")
        raise
    except Exception as exc:
        logger.warning("Upload rejected: decode error — %s", exc)
        raise InvalidImageError()

    # 6. Dimensions
    height, width = image_rgb.shape[:2]
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        logger.warning(
            "Upload rejected: dimensions %dx%d below minimum %dx%d",
            width, height, MIN_WIDTH, MIN_HEIGHT,
        )
        raise ImageDimensionError()

    logger.info(
        "Image validated OK: %s | %d bytes | %dx%d",
        filename, size_bytes, width, height,
    )

    # Return as RGB numpy array for downstream CV
    return image_rgb
