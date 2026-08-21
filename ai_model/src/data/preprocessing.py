"""
preprocessing.py
=================
Deterministic, non-destructive image preprocessing.

Every operation here reads from RAW_DATA_DIR and writes only to
PROCESSED_DATA_DIR / REPORTS_DIR — raw files are never opened in write
mode, moved, renamed, or deleted. See tests/test_pipeline.py::test_raw_dir_unchanged.

Operations implemented (all directly justified by Account 1's findings):
  - image loading            (validation.load_raw_photo / load_mask)
  - EXIF-orientation rotation (confirmed necessary — image data is not
                                pre-rotated; DATASET_VERIFICATION_REPORT.md §3)
  - RGB conversion            (raw photos are 3-channel RGB already, but we
                                normalize any CMYK/L/RGBA JPEGs defensively)
  - resizing                  (to config.MODEL_INPUT_SIZE, for model input)
  - normalization             (to [0,1] float32, then optionally to
                                ImageNet mean/std — placeholder until
                                dataset-specific stats can be computed at
                                full scale)
  - invalid image detection   (delegated to validation.validate_file)
"""

import cv2
import numpy as np

from . import config
from .validation import load_raw_photo, InvalidImageError


def resize_image(rgb_array, size=None, interpolation=cv2.INTER_AREA):
    """Resize an (H, W, 3) uint8 RGB array to `size` = (H_out, W_out)."""
    size = size or config.MODEL_INPUT_SIZE
    h_out, w_out = size
    return cv2.resize(rgb_array, (w_out, h_out), interpolation=interpolation)


def normalize_image(rgb_array, mean=None, std=None):
    """
    Convert uint8 [0,255] RGB array to float32, scale to [0,1], then
    standardize with per-channel mean/std. Returns (H, W, 3) float32.

    NOTE: mean/std default to ImageNet statistics as a documented
    placeholder (config.NORMALIZE_MEAN/STD). These should be replaced with
    dataset-specific stats computed over the actual TRAIN split once the
    full dataset is available — using val/test data to compute stats would
    itself be a (mild) form of leakage.
    """
    mean = np.array(mean or config.NORMALIZE_MEAN, dtype=np.float32)
    std = np.array(std or config.NORMALIZE_STD, dtype=np.float32)
    x = rgb_array.astype(np.float32) / 255.0
    x = (x - mean) / std
    return x


def preprocess_raw_photo(path, size=None, normalize=True):
    """
    Full single-image pipeline: load -> EXIF-rotate -> RGB -> resize -> normalize.
    Raises InvalidImageError (caught upstream by quality_checks) on bad files.
    """
    rgb = load_raw_photo(path, apply_exif_rotation=True)  # RGB, EXIF-corrected
    resized = resize_image(rgb, size=size)
    if not normalize:
        return resized
    return normalize_image(resized)


def compute_dataset_mean_std(image_paths, sample_limit=None):
    """
    Compute per-channel mean/std over a list of raw photo paths (intended
    to be called on the TRAIN split only). Returns (mean, std) as (3,) arrays
    in [0,1] scale. Skips unreadable files rather than crashing the whole run.
    """
    paths = image_paths if sample_limit is None else image_paths[:sample_limit]
    pixel_sum = np.zeros(3, dtype=np.float64)
    pixel_sq_sum = np.zeros(3, dtype=np.float64)
    n_pixels = 0
    for p in paths:
        try:
            rgb = load_raw_photo(p, apply_exif_rotation=True)
        except InvalidImageError:
            continue
        resized = resize_image(rgb)
        arr = resized.astype(np.float64) / 255.0
        pixel_sum += arr.sum(axis=(0, 1))
        pixel_sq_sum += (arr ** 2).sum(axis=(0, 1))
        n_pixels += arr.shape[0] * arr.shape[1]

    if n_pixels == 0:
        raise InvalidImageError("No readable images to compute dataset mean/std from")

    mean = pixel_sum / n_pixels
    var = (pixel_sq_sum / n_pixels) - mean ** 2
    std = np.sqrt(np.clip(var, a_min=1e-8, a_max=None))
    return mean.astype(np.float32), std.astype(np.float32)
