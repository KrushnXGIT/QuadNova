"""
roi.py
======
Conjunctiva ROI extraction using the supplied RGBA mask files.

This module builds on top of src/data/segmentation.py (Phase 2) and does NOT
re-implement mask alignment from scratch. Phase 2 confirmed:

  1. Masks are RGBA cutouts — pixel color inside the mask is REAL tissue color,
     not a flat highlight (DATASET_VERIFICATION_REPORT.md §6).
  2. alpha > 0 means "inside ROI"; the raw alpha value can be soft/anti-aliased.
  3. mask = EXIF_rotate(raw) downscaled ~3.735× — alignment is recomputed per-subject
     from actual image sizes (not the hardcoded constant).
  4. All sampled masks have a corrupted iCCP chunk — must use OpenCV
     (DATASET_VERIFICATION_REPORT.md §4, confirmed via cv2.IMREAD_UNCHANGED).
  5. The combined _forniceal_palpebral mask is the pixel-wise union of the two
     individual masks (confirmed in DATASET_VERIFICATION_REPORT.md §6).

Background fill strategy (transparent pixels → model input):
  Instead of filling with black (0,0,0), we fill with the mean conjunctiva color
  computed from the non-transparent pixels. This avoids introducing a large constant
  background signal that has nothing to do with conjunctival tissue, which could
  bias CNN feature maps near ROI borders.
"""

import logging
from pathlib import Path
from typing import NamedTuple, Optional, Tuple

import cv2
import numpy as np

from src.data.segmentation import extract_roi, crop_to_bbox

logger = logging.getLogger(__name__)

# Supported mask variants (ordered by preference for ROI quality)
MASK_VARIANT_PRIORITY = ["forniceal_palpebral", "forniceal", "palpebral"]

# Minimum alpha threshold to consider a pixel "inside" the ROI.
# Using 0 (as in Phase 2) to capture soft/anti-aliased mask edges.
ALPHA_THRESHOLD = 0


class ROIResult(NamedTuple):
    """
    Result of conjunctiva ROI extraction.

    Attributes:
        roi_rgb:           (H, W, 3) uint8 RGB array — the cropped ROI region,
                           with transparent pixels filled by mean conjunctiva color.
        bbox:              (y0, y1, x0, x1) bounding box within the EXIF-rotated
                           raw image coordinate system.
        coverage_fraction: float — fraction of mask pixels that were inside the ROI.
        mask_variant:      which mask was used ('forniceal_palpebral', 'forniceal',
                           or 'palpebral').
        raw_shape:         (H, W) of the EXIF-rotated raw image (for reference).
    """
    roi_rgb: np.ndarray
    bbox: Tuple[int, int, int, int]
    coverage_fraction: float
    mask_variant: str
    raw_shape: Tuple[int, int]


def _get_bbox(alpha: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Return (y0, y1, x0, x1) bounding box of non-zero alpha, or None if empty."""
    ys, xs = np.where(alpha > ALPHA_THRESHOLD)
    if len(ys) == 0:
        return None
    return int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1


def _fill_background(roi_rgba: np.ndarray) -> np.ndarray:
    """
    Convert an RGBA ROI array to RGB by replacing transparent pixels with the
    mean RGB color of the non-transparent (inside-ROI) pixels.

    This avoids the hard black border artifact that would result from simply
    dropping the alpha channel, while not requiring any external reference image.

    Args:
        roi_rgba: (H, W, 4) uint8 RGBA array where alpha=0 means background.

    Returns:
        (H, W, 3) uint8 RGB array.
    """
    alpha = roi_rgba[:, :, 3]
    inside_mask = alpha > ALPHA_THRESHOLD
    rgb = roi_rgba[:, :, :3].astype(np.float32)

    if inside_mask.any():
        mean_color = rgb[inside_mask].mean(axis=0)  # shape (3,)
    else:
        mean_color = np.array([128.0, 128.0, 128.0])  # fallback: mid-grey

    result = rgb.copy()
    result[~inside_mask] = mean_color
    return result.astype(np.uint8)


def extract_conjunctiva_roi(
    raw_path: str,
    mask_path: str,
    mask_variant: str = "forniceal_palpebral",
    upscale_mask_to_raw: bool = True,
) -> ROIResult:
    """
    Extract the conjunctiva ROI from a raw image + mask pair.

    Args:
        raw_path:           Path to the raw JPEG photo.
        mask_path:          Path to the RGBA PNG mask file.
        mask_variant:       Which mask type this is ('forniceal_palpebral',
                            'forniceal', or 'palpebral'). Used for labeling only.
        upscale_mask_to_raw: If True (default), upscale the mask to raw photo
                            resolution to preserve maximum ROI detail. If False,
                            downscale raw to mask resolution instead.

    Returns:
        ROIResult named tuple.

    Raises:
        ValueError: If the mask is empty (no ROI pixels found) or cannot be loaded.
        FileNotFoundError: If either path does not exist.
    """
    raw_path = str(raw_path)
    mask_path = str(mask_path)

    if not Path(raw_path).is_file():
        raise FileNotFoundError(f"Raw photo not found: {raw_path}")
    if not Path(mask_path).is_file():
        raise FileNotFoundError(f"Mask file not found: {mask_path}")

    # Phase 2's extract_roi: EXIF-rotates raw, aligns mask, returns RGBA ROI
    roi_rgba, coverage_fraction = extract_roi(
        raw_path,
        mask_path,
        upscale_mask_to_raw=upscale_mask_to_raw,
        alpha_threshold=ALPHA_THRESHOLD,
    )

    raw_shape = (roi_rgba.shape[0], roi_rgba.shape[1])

    # Tight bounding-box crop (from Phase 2's crop_to_bbox)
    roi_cropped = crop_to_bbox(roi_rgba)

    # Compute bbox in the full-resolution coordinate system
    alpha_full = roi_rgba[:, :, 3]
    bbox = _get_bbox(alpha_full)
    if bbox is None:
        raise ValueError(
            f"Mask {mask_path} produced an empty ROI (no alpha>0 pixels). "
            "Check mask integrity or consider this subject as QC-failed."
        )

    # Fill transparent background pixels with mean conjunctiva color
    roi_rgb = _fill_background(roi_cropped)

    logger.debug(
        "ROI extracted: subject=%s variant=%s coverage=%.4f bbox=%s",
        Path(raw_path).stem,
        mask_variant,
        coverage_fraction,
        bbox,
    )

    return ROIResult(
        roi_rgb=roi_rgb,
        bbox=bbox,
        coverage_fraction=coverage_fraction,
        mask_variant=mask_variant,
        raw_shape=raw_shape,
    )


def extract_best_roi(raw_path: str, mask_dir: str, subject_id: str) -> ROIResult:
    """
    Try mask variants in order of preference (forniceal_palpebral → forniceal →
    palpebral) and return the first successfully extracted ROI.

    This is a convenience wrapper for callers who have the raw dataset flat directory.

    Args:
        raw_path:   Path to the raw JPEG.
        mask_dir:   Directory containing the mask PNG files.
        subject_id: The YYYYMMDD_HHMMSS subject identifier.

    Returns:
        ROIResult from the highest-priority available mask variant.

    Raises:
        FileNotFoundError: If no mask variant is found for this subject.
        ValueError:        If all found masks produce empty ROIs.
    """
    mask_dir = Path(mask_dir)
    errors = []

    for variant in MASK_VARIANT_PRIORITY:
        suffix_map = {
            "forniceal_palpebral": "_forniceal_palpebral.png",
            "forniceal": "_forniceal.png",
            "palpebral": "_palpebral.png",
        }
        mask_path = mask_dir / f"{subject_id}{suffix_map[variant]}"
        if not mask_path.is_file():
            errors.append(f"{variant}: mask not found")
            continue
        try:
            return extract_conjunctiva_roi(raw_path, str(mask_path), mask_variant=variant)
        except (ValueError, Exception) as e:
            errors.append(f"{variant}: {e}")
            continue

    raise FileNotFoundError(
        f"No usable mask found for subject {subject_id} in {mask_dir}. "
        f"Tried: {'; '.join(errors)}"
    )
