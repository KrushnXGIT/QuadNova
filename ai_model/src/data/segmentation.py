"""
segmentation.py
================
IMAGE + MASK -> CONJUNCTIVA ROI extraction.

Per instructions, this phase does NOT train a segmentation model. It only
prepares aligned (image, mask, roi_crop) triples so a future segmentation
or ROI-conditioned classifier/regressor can consume them directly.

Geometry note (DATASET_VERIFICATION_REPORT.md §5, confirmed on 1 subject):
the mask is NOT a pixel-identity crop of the raw JPEG. It is:
    mask = downscale( exif_rotate(raw_photo), factor=~3.735 )
So to align them we must either:
  (A) EXIF-rotate the raw photo, then resize it DOWN to the mask's
      resolution (cheap, but throws away raw resolution in the ROI), or
  (B) EXIF-rotate the raw photo, then resize the MASK UP to the raw
      photo's resolution (keeps full raw resolution in the ROI; alpha
      upscaling introduces soft/interpolated edges — acceptable since
      several sampled masks were already soft/anti-aliased).
This module implements (B) as the default, since a downstream model
typically benefits from the highest-resolution ROI crop available, and
exposes (A) for callers who want the mask's native resolution instead.

The confirmed downscale factor is a SAMPLE-DERIVED constant (n=1). This
module recomputes the actual factor per-subject from the real image sizes
rather than trusting the hardcoded constant, and only falls back to it if
one of the two images is unavailable for cross-checking. This makes the
alignment self-correcting if the factor varies slightly by device/subject.
"""

import cv2
import numpy as np
from PIL import Image, ImageOps

from . import config


def _exif_rotated_raw(raw_path):
    """Return the raw photo as an RGB array AFTER EXIF-orientation rotation."""
    img = Image.open(raw_path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    return np.array(img)


def align_mask_to_raw_resolution(raw_rgb, mask_rgba):
    """
    Upscale mask_rgba (H_m, W_m, 4) to raw_rgb's (H_r, W_r, 3) resolution
    using the mask's own aspect ratio (not the hardcoded constant), so the
    alpha channel lines up with the EXIF-rotated raw photo pixel grid.
    """
    h_r, w_r = raw_rgb.shape[:2]
    resized = cv2.resize(mask_rgba, (w_r, h_r), interpolation=cv2.INTER_LINEAR)
    return resized


def extract_roi(raw_path, mask_path, upscale_mask_to_raw=True, alpha_threshold=0):
    """
    Build an aligned (roi_rgba, alpha_mask) pair for one subject/mask-variant.

    Returns:
        roi_rgba: (H, W, 4) uint8 array — raw pixel color where alpha>threshold,
                   transparent (alpha=0) elsewhere. Resolution matches raw
                   photo (post EXIF-rotation) if upscale_mask_to_raw=True,
                   else matches the mask's native resolution.
        coverage_fraction: float, fraction of pixels inside the ROI.
    """
    raw_rgb = _exif_rotated_raw(raw_path)
    mask_bgra = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
    if mask_bgra is None:
        raise ValueError(f"Could not load mask {mask_path} (see validation.load_mask for the known iCCP issue)")
    b, g, r, a = cv2.split(mask_bgra)
    mask_rgba = cv2.merge([r, g, b, a])

    if upscale_mask_to_raw:
        aligned_mask = align_mask_to_raw_resolution(raw_rgb, mask_rgba)
        base_rgb = raw_rgb
    else:
        # downscale raw down to mask's native resolution instead
        h_m, w_m = mask_rgba.shape[:2]
        base_rgb = cv2.resize(raw_rgb, (w_m, h_m), interpolation=cv2.INTER_AREA)
        aligned_mask = mask_rgba

    alpha = aligned_mask[:, :, 3]
    keep = alpha > alpha_threshold

    roi_rgba = np.zeros((base_rgb.shape[0], base_rgb.shape[1], 4), dtype=np.uint8)
    roi_rgba[:, :, :3] = base_rgb
    roi_rgba[:, :, 3] = np.where(keep, alpha, 0)

    coverage_fraction = float(keep.sum()) / keep.size
    return roi_rgba, coverage_fraction


def crop_to_bbox(roi_rgba):
    """Tight-crop roi_rgba to the bounding box of its non-zero alpha region."""
    alpha = roi_rgba[:, :, 3]
    ys, xs = np.where(alpha > 0)
    if len(ys) == 0:
        return roi_rgba  # empty mask — return unchanged rather than erroring
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    return roi_rgba[y0:y1, x0:x1]
