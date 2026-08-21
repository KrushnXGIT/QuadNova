"""
validation.py
=============
Per-file validation and SAFE loaders.

Account 1 confirmed that every sampled PNG mask has a corrupted iCCP chunk
(bad CRC) and that plain PIL.Image.open() crashes on all of them, while
cv2.imread(path, cv2.IMREAD_UNCHANGED) loads them fine. This module bakes
that finding in as the standard loader so every later stage (preprocessing,
segmentation, augmentation) uses a loader that is known to work on this
dataset's masks, instead of each script re-discovering the iCCP issue.

Raw photos load fine under both PIL and OpenCV in the sample; PIL is used
for raw photos specifically because it gives clean EXIF-orientation
handling (ImageOps.exif_transpose), which OpenCV does not do natively.
"""

import hashlib
import os

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config


class InvalidImageError(Exception):
    pass


def load_raw_photo(path, apply_exif_rotation=True):
    """
    Load a raw JPEG photo as an RGB numpy array (H, W, 3), uint8.
    Applies EXIF orientation correction by default (confirmed necessary —
    DATASET_VERIFICATION_REPORT.md §3/§5: image data is NOT pre-rotated).
    Raises InvalidImageError on any failure instead of returning garbage.
    """
    try:
        img = Image.open(path)
        img.load()  # force read now so truncated files raise here, not later
    except (UnidentifiedImageError, OSError) as e:
        raise InvalidImageError(f"Cannot open raw photo {path}: {e}")

    if apply_exif_rotation:
        img = ImageOps.exif_transpose(img)

    img = img.convert("RGB")
    arr = np.array(img)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise InvalidImageError(f"Raw photo {path} did not convert to RGB HxWx3, got shape {arr.shape}")
    return arr


def load_mask(path):
    """
    Load an RGBA mask as a numpy array (H, W, 4), uint8, via OpenCV.
    Do NOT switch this to PIL.Image.open() without re-verifying the iCCP
    CRC defect rate on the full dataset first (see DATA_PREPROCESSING.md).
    """
    img_bgra = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img_bgra is None:
        raise InvalidImageError(f"OpenCV failed to load mask {path} (corrupt or unreadable)")
    if img_bgra.ndim != 3 or img_bgra.shape[2] != 4:
        raise InvalidImageError(
            f"Mask {path} does not have 4 channels (RGBA expected), got shape {img_bgra.shape}"
        )
    # cv2 loads as BGRA -> convert to RGBA for consistency with raw-photo RGB convention
    b, g, r, a = cv2.split(img_bgra)
    return cv2.merge([r, g, b, a])


def validate_file(path, role):
    """
    Validate a single file. Returns a dict with at least {"valid": bool}.
    Never raises — failures are captured in the report for the QC step.
    """
    result = {"path": path, "role": role, "valid": False, "error": None}
    if not os.path.isfile(path):
        result["error"] = "file does not exist"
        return result
    if os.path.getsize(path) == 0:
        result["error"] = "zero-byte file"
        return result

    try:
        if role == "raw_photo":
            arr = load_raw_photo(path)
            result["width"] = int(arr.shape[1])
            result["height"] = int(arr.shape[0])
            result["channels"] = int(arr.shape[2])
        else:
            arr = load_mask(path)
            result["width"] = int(arr.shape[1])
            result["height"] = int(arr.shape[0])
            result["channels"] = int(arr.shape[2])
        result["valid"] = True
    except InvalidImageError as e:
        result["error"] = str(e)
    except Exception as e:  # defensive: never let one bad file kill a full-dataset scan
        result["error"] = f"unexpected error: {e}"
    return result


def file_md5(path, chunk_size=8192):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def find_duplicate_files(paths):
    """Return dict[md5_hash] -> list[paths] for any hash shared by >1 file."""
    by_hash = {}
    for p in paths:
        try:
            h = file_md5(p)
        except OSError:
            continue
        by_hash.setdefault(h, []).append(p)
    return {h: ps for h, ps in by_hash.items() if len(ps) > 1}


def snapshot_raw_dir_checksums(raw_data_dir=None):
    """Checksum every file in RAW_DATA_DIR. Used to prove the pipeline never
    mutates raw data (call before and after running the pipeline, diff the two)."""
    raw_data_dir = str(raw_data_dir or config.RAW_DATA_DIR)
    out = {}
    for fname in sorted(os.listdir(raw_data_dir)):
        fpath = os.path.join(raw_data_dir, fname)
        if os.path.isfile(fpath):
            out[fname] = file_md5(fpath)
    return out
