"""
mask_generator.py
=================
Server-side automatic conjunctiva ROI mask generation for phone-camera captures.

WHY THIS EXISTS
---------------
The existing AI predictor (`ai_model/src/inference/predictor.py`) requires an
RGBA conjunctiva ROI mask alongside the raw photo. Dataset masks were manually
annotated, so a live smartphone capture (which has no mask) previously could
never reach successful inference — the documented project blocker in
HANDOFF.md ("Add/route an ROI mask generation step ... that does not require
a pre-existing dataset mask").

WHAT THIS MODULE DOES
---------------------
Generates the mask INPUT required by the existing pipeline using classical
OpenCV heuristics (red/pink tissue chroma detection + morphology). It does NOT:

  - modify, retrain, or replace the AI model,
  - estimate Hb,
  - bypass any quality gate.

After generation, the full existing pipeline still runs unchanged: raw-image
quality gate -> ROI extraction -> ROI quality gate -> CLAHE normalization ->
MobileNetV3 regression -> confidence calibration. If the generated mask is
poor, those existing gates reject the request honestly (ROI_FAILED /
IMAGE_QUALITY_FAILED). If no plausible tissue region is found, this module
returns None and the caller reports ROI_FAILED — never a fabricated result.

ALIGNMENT CONTRACT
------------------
`src/data/segmentation.extract_roi` EXIF-rotates the raw photo and upscales
the mask to that rotated resolution. Therefore the mask produced here MUST be
computed on the EXIF-rotated image (Pillow `ImageOps.exif_transpose`), which
this module does.

All thresholds are engineering heuristics for prototype screening — they are
NOT clinically validated.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# ── Heuristic constants (prototype-grade, deliberately conservative) ────────
_WORKING_MAX_SIDE = 720        # analysis resolution; mask is upscaled by roi.py
_HUE_RED_BANDS = ((0, 11), (169, 180))   # OpenCV hue (0-179) bands for red/pink
_MIN_SATURATION = 45           # tissue has visible chroma; skin/shadow often lower
_MIN_VALUE = 50                # discard near-black regions (shadows/hairline)
_MAX_VALUE = 250               # discard blown-out highlights
_REDIFF_MARGIN = 18            # R - mean(G, B) margin for the redness fallback
_OPEN_KERNEL = 5               # morphological open (despeckle)
_CLOSE_KERNEL = 9              # morphological close (fill pinholes)
_MIN_BLOB_AREA_FRACTION = 0.0015   # ignore connected components < 0.15% of frame
_MIN_COVERAGE_FRACTION = 0.002     # final mask must cover >= 0.2% of frame
_MAX_COVERAGE_FRACTION = 0.60      # >60% coverage means detection is not selective
_MAX_BLOBS = 3                     # keep at most the N largest plausible blobs
_MIN_LOCAL_DARK_FRACTION = 0.005   # eye boundary/iris context must be visible


def _decode_exif_rgb(image_bytes: bytes) -> Optional[np.ndarray]:
    """Decode upload bytes to an EXIF-rotated RGB uint8 array (or None)."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        return np.asarray(img, dtype=np.uint8)
    except Exception as exc:
        logger.warning("Mask generator: Pillow decode failed (%s)", exc)
        return None


def _detect_conjunctiva_alpha(rgb: np.ndarray) -> Optional[np.ndarray]:
    """
    Compute a binary uint8 alpha mask (255 = candidate conjunctiva tissue)
    for an EXIF-rotated RGB image. Returns None when nothing plausible is found.
    """
    h, w = rgb.shape[:2]
    if min(h, w) < 100:
        return None

    # Work at reduced resolution for speed; roi.py upscales the mask anyway.
    scale = min(1.0, _WORKING_MAX_SIDE / float(max(h, w)))
    if scale < 1.0:
        small = cv2.resize(
            rgb,
            (int(round(w * scale)), int(round(h * scale))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        small = rgb

    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    hue, sat, val = cv2.split(hsv)

    # Signal 1 — red/pink hue band with sane brightness/chroma.
    hue_red = np.zeros(hue.shape, dtype=bool)
    for lo, hi in _HUE_RED_BANDS:
        hue_red |= (hue >= lo) & (hue < hi)
    chroma_ok = (sat >= _MIN_SATURATION) & (val >= _MIN_VALUE) & (val < _MAX_VALUE)
    hue_mask = hue_red & chroma_ok

    # Signal 2 — plain redness dominance (R noticeably above G/B average).
    r = small[:, :, 0].astype(np.int16)
    g = small[:, :, 1].astype(np.int16)
    b = small[:, :, 2].astype(np.int16)
    redness = ((r - ((g + b) // 2)) >= _REDIFF_MARGIN) \
        & (val >= _MIN_VALUE) & (val < _MAX_VALUE)

    combined = hue_mask | redness

    # Morphological cleanup: despeckle, then consolidate the region.
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_OPEN_KERNEL,) * 2)
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_CLOSE_KERNEL,) * 2)
    combined = cv2.morphologyEx(combined.astype(np.uint8), cv2.MORPH_OPEN, k_open)
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_close)

    # Keep only sufficiently large connected components.
    frame_area = combined.shape[0] * combined.shape[1]
    min_blob_area = _MIN_BLOB_AREA_FRACTION * frame_area
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        combined, connectivity=8
    )

    kept = np.zeros_like(combined, dtype=np.uint8)
    candidates = []
    for label in range(1, num_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= min_blob_area:
            candidates.append((area, label))
    if not candidates:
        logger.info("Mask generator: no tissue-sized blob found")
        return None

    candidates.sort(reverse=True)
    for _, label in candidates[:_MAX_BLOBS]:
        kept[labels == label] = 255

    coverage = float(np.count_nonzero(kept)) / frame_area
    if coverage < _MIN_COVERAGE_FRACTION or coverage > _MAX_COVERAGE_FRACTION:
        logger.info(
            "Mask generator: implausible coverage %.4f — rejecting mask", coverage
        )
        return None

    # Redness alone is not an eye detector: food, clothing, skin and red
    # objects can all satisfy the chroma test. A real close-up eye should have
    # a nearby dark iris/lid boundary. Require that context before creating a
    # mask that could reach the Hb model. The margin is measured locally so a
    # dark room elsewhere in the frame cannot satisfy the gate.
    ys, xs = np.where(kept > 0)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    pad = max(4, int(0.15 * max(y1 - y0, x1 - x0)))
    context = small[
        max(0, y0 - pad):min(small.shape[0], y1 + pad),
        max(0, x0 - pad):min(small.shape[1], x1 + pad),
    ]
    context_gray = cv2.cvtColor(context, cv2.COLOR_RGB2GRAY)
    local_dark_fraction = float(np.mean(context_gray < 55))
    if local_dark_fraction < _MIN_LOCAL_DARK_FRACTION:
        logger.info(
            "Mask generator: no eye context near candidate (dark_fraction=%.4f)",
            local_dark_fraction,
        )
        return None

    # Restore full resolution (nearest keeps the mask crisp for upscaling).
    if scale < 1.0:
        kept = cv2.resize(kept, (w, h), interpolation=cv2.INTER_NEAREST)

    return kept


def generate_mask_png(image_bytes: bytes) -> Optional[bytes]:
    """
    Generate an RGBA conjunctiva mask PNG aligned to the EXIF-rotated image.

    Returns PNG bytes where alpha=255 marks the detected candidate tissue
    region, or None when no plausible region is found (caller must treat this
    as ROI_FAILED — never fabricate a mask or a prediction).
    """
    rgb = _decode_exif_rgb(image_bytes)
    if rgb is None:
        return None

    alpha = _detect_conjunctiva_alpha(rgb)
    if alpha is None:
        return None

    rgba = np.dstack([rgb, alpha])           # RGB + alpha
    bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
    ok, buf = cv2.imencode(".png", bgra)
    if not ok:
        logger.warning("Mask generator: PNG encoding failed")
        return None

    logger.info(
        "Mask generator: produced %d-byte mask (coverage=%.3f)",
        buf.size,
        float(np.count_nonzero(alpha)) / alpha.size,
    )
    return buf.tobytes()