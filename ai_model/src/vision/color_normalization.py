"""
color_normalization.py
======================
Color normalization techniques for conjunctiva ROI images.

IMPORTANT LIMITATION NOTICE
-----------------------------
The methods in this module REDUCE lighting, exposure, and some camera variation,
but they do NOT eliminate all sources of systematic color bias. In particular:

  - Camera sensor differences between devices introduce systematic color shifts
    that vary per make/model and cannot be fully corrected without a calibration
    target or device-specific characterization.
  - Skin tone affects the visible conjunctiva color even for the same Hb level,
    and no method here corrects for this. This is a known, documented limitation
    of smartphone-based conjunctival pallor assessment in the literature.
  - White balance normalization assumes a scene-average gray, which may not hold
    when the field-of-view is dominated by a single tissue color (as is common
    in close-up conjunctiva captures).

These caveats apply to ALL methods below. Callers and users of this pipeline
MUST communicate these limitations clearly rather than claiming camera/skin-tone
bias is resolved by normalization.

Methods implemented
-------------------
1. CLAHE (Contrast Limited Adaptive Histogram Equalization)
   Applied on the L-channel (CIE LAB). Improves local contrast and reduces
   exposure variation while preserving relative color information.
   Best for: single-image contrast normalization, conjunctiva detail enhancement.

2. Gray-world white balance
   Scales each channel so mean(R) ≈ mean(G) ≈ mean(B). Assumes the average
   color of the scene is neutral grey. Reduces gross illumination color casts
   (e.g. yellow indoor lighting). Simple, fast, no reference needed.
   Limitation: the assumption holds poorly for close-up single-tissue images
   where one hue dominates. Applied with a configurable clip to limit distortion.

3. Reinhard color transfer
   Transfers the mean and std of each LAB channel to match a reference image or
   reference statistics. Reduces cross-subject and cross-device color variation
   at the population level when a representative reference is chosen.
   Reference statistics can be set from the training set mean (recommended) or
   left at default neutral values.

4. Per-image z-score normalization
   Subtracts per-channel mean and divides by per-channel std for this image.
   Makes each image zero-mean unit-variance per channel. Strong cross-image
   standardization but discards absolute color information — use with caution
   for anaemia screening where absolute redness is a key signal.

Output
------
All normalize_roi() variants return a (H, W, 3) float32 array in [0.0, 1.0].
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CLAHE defaults
# ---------------------------------------------------------------------------
CLAHE_CLIP_LIMIT: float = 2.0
CLAHE_TILE_GRID_SIZE: Tuple[int, int] = (8, 8)

# ---------------------------------------------------------------------------
# Gray-world clipping: channel scale factors are clipped to this range to
# prevent extreme distortion when the gray-world assumption fails badly.
# ---------------------------------------------------------------------------
GRAY_WORLD_CLIP_MIN: float = 0.5
GRAY_WORLD_CLIP_MAX: float = 2.0

# ---------------------------------------------------------------------------
# Reinhard default reference statistics (LAB, L in [0,255] OpenCV range).
# These neutral defaults (L=128, a=0, b=0) are a reasonable starting point.
# Replace with training-set LAB statistics once real data is available.
# ---------------------------------------------------------------------------
REINHARD_REF_MEAN: Tuple[float, float, float] = (128.0, 128.0, 128.0)
REINHARD_REF_STD: Tuple[float, float, float] = (30.0, 5.0, 5.0)


def _to_float(rgb: np.ndarray) -> np.ndarray:
    """Convert uint8 [0,255] RGB to float32 [0,1]."""
    return rgb.astype(np.float32) / 255.0


def _clip_to_unit(arr: np.ndarray) -> np.ndarray:
    """Clip float array to [0, 1]."""
    return np.clip(arr, 0.0, 1.0)


def clahe_normalize(
    roi_rgb: np.ndarray,
    clip_limit: float = CLAHE_CLIP_LIMIT,
    tile_grid_size: Tuple[int, int] = CLAHE_TILE_GRID_SIZE,
) -> np.ndarray:
    """
    Apply CLAHE to the L-channel of the ROI in CIE LAB color space.

    CLAHE improves local contrast and reduces per-image exposure variation.
    It operates only on the L (luminance) channel, leaving the A and B
    (colour opponent) channels unchanged — this preserves the red/green/blue
    colour ratios that carry the anaemia-relevant pallor signal.

    Args:
        roi_rgb:        (H, W, 3) uint8 RGB array.
        clip_limit:     CLAHE clip limit (default 2.0; lower = less enhancement).
        tile_grid_size: Grid size for adaptive histogram (default 8×8).

    Returns:
        (H, W, 3) float32 RGB array in [0.0, 1.0].
    """
    lab = cv2.cvtColor(roi_rgb, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    rgb_out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    return _clip_to_unit(rgb_out.astype(np.float32) / 255.0)


def gray_world_normalize(
    roi_rgb: np.ndarray,
    clip_min: float = GRAY_WORLD_CLIP_MIN,
    clip_max: float = GRAY_WORLD_CLIP_MAX,
) -> np.ndarray:
    """
    Apply gray-world white balance to the ROI.

    Scales each RGB channel so that its mean equals the overall image mean.
    This reduces gross illumination color casts (e.g., from warm indoor light).

    Limitation: the gray-world assumption (that average scene color is neutral
    grey) often fails for close-up tissue images where one hue dominates.
    Scale factors are clipped to [clip_min, clip_max] to limit distortion.

    Args:
        roi_rgb:  (H, W, 3) uint8 RGB array.
        clip_min: Minimum channel scale factor (default 0.5).
        clip_max: Maximum channel scale factor (default 2.0).

    Returns:
        (H, W, 3) float32 RGB array in [0.0, 1.0].
    """
    img_f = roi_rgb.astype(np.float32)
    channel_means = img_f.mean(axis=(0, 1))  # shape (3,)
    overall_mean = channel_means.mean()

    if overall_mean < 1e-6:
        # Near-black image: no meaningful normalization possible
        logger.warning("gray_world_normalize: overall mean near 0, skipping WB")
        return _clip_to_unit(img_f / 255.0)

    scales = overall_mean / np.clip(channel_means, 1e-6, None)
    scales = np.clip(scales, clip_min, clip_max)

    result = img_f * scales[np.newaxis, np.newaxis, :]
    return _clip_to_unit(result / 255.0)


def reinhard_normalize(
    roi_rgb: np.ndarray,
    ref_mean: Tuple[float, float, float] = REINHARD_REF_MEAN,
    ref_std: Tuple[float, float, float] = REINHARD_REF_STD,
) -> np.ndarray:
    """
    Apply Reinhard color transfer to the ROI.

    Matches the per-channel LAB mean and standard deviation of this image to
    the reference statistics. Reduces systematic color differences between
    subjects and devices at the population level.

    Reference statistics (ref_mean, ref_std) should ideally be computed from
    the training set's ROIs rather than left at default neutral values.
    See src/data/preprocessing.compute_dataset_mean_std() for guidance on
    computing these from the training split.

    Args:
        roi_rgb:  (H, W, 3) uint8 RGB array.
        ref_mean: Target per-channel LAB mean (L, A, B) in OpenCV scale [0,255].
        ref_std:  Target per-channel LAB std (L, A, B) in OpenCV scale.

    Returns:
        (H, W, 3) float32 RGB array in [0.0, 1.0].
    """
    lab = cv2.cvtColor(roi_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    ref_m = np.array(ref_mean, dtype=np.float32)
    ref_s = np.array(ref_std, dtype=np.float32)

    for c in range(3):
        src_mean = lab[:, :, c].mean()
        src_std = lab[:, :, c].std()
        if src_std < 1e-6:
            # Flat channel: just shift to reference mean
            lab[:, :, c] = ref_m[c]
        else:
            lab[:, :, c] = (lab[:, :, c] - src_mean) * (ref_s[c] / src_std) + ref_m[c]

    lab = np.clip(lab, 0, 255).astype(np.uint8)
    rgb_out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    return _clip_to_unit(rgb_out.astype(np.float32) / 255.0)


def zscore_normalize(roi_rgb: np.ndarray) -> np.ndarray:
    """
    Per-image, per-channel z-score normalization.

    Subtracts per-channel mean and divides by per-channel std for this specific
    image. Makes each image zero-mean unit-variance per channel.

    WARNING: This discards absolute color information. Since absolute conjunctival
    redness is a key signal for anaemia screening, this method should be used with
    caution and only if the model architecture accounts for the information loss
    (e.g., it uses relative features rather than absolute colour).

    Output values are NOT in [0,1] — they are z-scores (unbounded). The caller
    is responsible for any additional scaling needed for their model.

    Args:
        roi_rgb: (H, W, 3) uint8 RGB array.

    Returns:
        (H, W, 3) float32 array. Values are z-scores (mean=0, std=1 per channel).
        Clipped to [-3, 3] before returning to limit the effect of outlier pixels.
    """
    img_f = roi_rgb.astype(np.float32) / 255.0
    mean = img_f.mean(axis=(0, 1), keepdims=True)
    std = img_f.std(axis=(0, 1), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)  # avoid division by zero on flat channels
    z = (img_f - mean) / std
    return np.clip(z, -3.0, 3.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

SUPPORTED_METHODS = ("clahe", "gray_world", "reinhard", "zscore", "none")


def normalize_roi(
    roi_rgb: np.ndarray,
    method: str = "clahe",
    reinhard_ref_mean: Optional[Tuple[float, float, float]] = None,
    reinhard_ref_std: Optional[Tuple[float, float, float]] = None,
) -> np.ndarray:
    """
    Apply color normalization to a conjunctiva ROI.

    This is the primary entry point for Account 4 (modelling phase).

    Args:
        roi_rgb:           (H, W, 3) uint8 RGB array from ROIResult.roi_rgb.
        method:            One of: 'clahe', 'gray_world', 'reinhard', 'zscore', 'none'.
                           Default is 'clahe' — recommended for single-image processing.
        reinhard_ref_mean: Override reference mean for Reinhard method. If None,
                           uses REINHARD_REF_MEAN (neutral default).
        reinhard_ref_std:  Override reference std for Reinhard method. If None,
                           uses REINHARD_REF_STD (neutral default).

    Returns:
        (H, W, 3) float32 array.
        For 'clahe', 'gray_world', 'reinhard', 'none': values in [0.0, 1.0].
        For 'zscore': values clipped to [-3.0, 3.0] (see zscore_normalize).

    Raises:
        ValueError: If method is not one of the supported options.
    """
    if roi_rgb is None or roi_rgb.size == 0:
        raise ValueError("normalize_roi: roi_rgb is None or empty")

    if method == "clahe":
        return clahe_normalize(roi_rgb)
    elif method == "gray_world":
        return gray_world_normalize(roi_rgb)
    elif method == "reinhard":
        kw = {}
        if reinhard_ref_mean is not None:
            kw["ref_mean"] = reinhard_ref_mean
        if reinhard_ref_std is not None:
            kw["ref_std"] = reinhard_ref_std
        return reinhard_normalize(roi_rgb, **kw)
    elif method == "zscore":
        return zscore_normalize(roi_rgb)
    elif method == "none":
        return _clip_to_unit(roi_rgb.astype(np.float32) / 255.0)
    else:
        raise ValueError(
            f"Unknown normalization method '{method}'. "
            f"Supported: {SUPPORTED_METHODS}"
        )


def compute_roi_color_stats(roi_rgb: np.ndarray) -> dict:
    """
    Compute descriptive color statistics for a conjunctiva ROI.

    Useful for exploratory analysis and for computing reference statistics
    for the Reinhard method from the training set.

    Returns a dict with mean/std/min/max for each of R, G, B and L, A, B channels.
    """
    img_f = roi_rgb.astype(np.float32)
    lab = cv2.cvtColor(roi_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    stats = {}
    for i, ch in enumerate(["R", "G", "B"]):
        stats[f"mean_{ch}"] = float(img_f[:, :, i].mean())
        stats[f"std_{ch}"] = float(img_f[:, :, i].std())
        stats[f"min_{ch}"] = float(img_f[:, :, i].min())
        stats[f"max_{ch}"] = float(img_f[:, :, i].max())

    for i, ch in enumerate(["L", "A", "B_lab"]):
        stats[f"mean_{ch}"] = float(lab[:, :, i].mean())
        stats[f"std_{ch}"] = float(lab[:, :, i].std())

    return stats
