"""
config.py
=========
Central configuration for the Phase 2 data pipeline.

Every constant here traces back to a specific, verified claim in
DATASET_VERIFICATION_REPORT.md / DATASET_SCHEMA.md written by Account 1.
Nothing here is invented. Where Account 1's verification was scoped to a
tiny sample (n=2 subjects) or left something unresolved, that is called out
explicitly instead of silently assumed at full-dataset scale.

IMPORTANT — TARGET STATUS (read this before wiring in a model):
Account 1's feasibility determination was "C — undetermined" because no
Hb-value metadata table was available in their session (see HANDOFF.md and
DATASET_VERIFICATION_REPORT.md §10). Neither "IMAGE -> Hb" (regression) nor
"IMAGE -> ANAEMIA CLASS" (classification) has been confirmed. This module
therefore does NOT hardcode a target. TARGET_MODE is left as "UNVERIFIED"
and the label-joining step (see labels.py) is a documented placeholder,
not a working join, until the metadata table is supplied.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (override via environment variables — nothing here assumes a
# specific machine layout)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Directory containing the RAW, UNMODIFIED dataset files (*.jpg + *.png
# masks, flat directory, per DATASET_SCHEMA.md). This pipeline never
# writes into this directory.
RAW_DATA_DIR = Path(os.environ.get("ANAEMIA_RAW_DATA_DIR", PROJECT_ROOT / "data" / "raw"))

# Directory containing the external Hb metadata table, if/when supplied.
# Expected columns are documented in labels.py. Not present as of Phase 2.
METADATA_DIR = Path(os.environ.get("ANAEMIA_METADATA_DIR", PROJECT_ROOT / "data" / "metadata"))

# Where processed/derived artifacts are written. Derived data ONLY —
# never raw data. Safe to delete and regenerate at any time.
PROCESSED_DATA_DIR = Path(os.environ.get("ANAEMIA_PROCESSED_DATA_DIR", PROJECT_ROOT / "data" / "processed"))
SPLITS_DIR = Path(os.environ.get("ANAEMIA_SPLITS_DIR", PROJECT_ROOT / "data" / "splits"))
REPORTS_DIR = Path(os.environ.get("ANAEMIA_REPORTS_DIR", PROJECT_ROOT / "outputs"))

# ---------------------------------------------------------------------------
# File naming schema (confirmed in DATASET_SCHEMA.md, n=2 subjects)
# ---------------------------------------------------------------------------
SUBJECT_ID_PATTERN = r"^(?P<subject_id>\d{8}_\d{6})"  # YYYYMMDD_HHMMSS
RAW_EXTS = {".jpg", ".jpeg"}
MASK_EXTS = {".png"}
MASK_SUFFIXES = {
    "forniceal": "_forniceal",
    "palpebral": "_palpebral",
    "forniceal_palpebral": "_forniceal_palpebral",  # confirmed = union of the two above
}

# ---------------------------------------------------------------------------
# Known data-integrity defects (confirmed by Account 1, 4/4 sampled masks —
# rate at full-dataset scale is UNCONFIRMED, see DATA_PREPROCESSING.md)
# ---------------------------------------------------------------------------
# All sampled masks fail iCCP CRC validation. Plain PIL.Image.open() raises
# UnidentifiedImageError on them. cv2.imread(..., IMREAD_UNCHANGED) loads
# them fine, so this pipeline standardizes on OpenCV for mask I/O.
MASK_LOADER = "opencv"  # do not switch to PIL for masks without re-verifying iCCP fix rate

# Raw photo -> mask geometric relationship (confirmed for 1/2 sampled
# subjects that had both files): mask = raw photo rotated per its EXIF
# Orientation tag, then downscaled by ~3.735x. This is NOT a direct crop
# of the raw pixel grid at identity scale/rotation.
CONFIRMED_MASK_DOWNSCALE_FACTOR = 3.735  # raw (post-EXIF-rotation) size / mask size, sample-derived

# ---------------------------------------------------------------------------
# Preprocessing parameters
# ---------------------------------------------------------------------------
MODEL_INPUT_SIZE = (224, 224)  # (H, W) — standard for CNN backbones; adjust with Account 3
NORMALIZE_MEAN = (0.485, 0.456, 0.406)  # ImageNet stats — placeholder until
NORMALIZE_STD = (0.229, 0.224, 0.225)   # dataset-specific mean/std can be computed at full scale

# ---------------------------------------------------------------------------
# Split parameters
# ---------------------------------------------------------------------------
SPLIT_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Target status — DO NOT set this to "regression" or "classification"
# without updating DATASET_VERIFICATION_REPORT.md / HANDOFF.md with the
# evidence (the actual Hb metadata table) that justifies it.
# ---------------------------------------------------------------------------
TARGET_MODE = "regression"  # verified Hgb columns from India.xlsx and Italy.xlsx
