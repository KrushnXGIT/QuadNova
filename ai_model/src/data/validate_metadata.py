"""Validate verified SUBJECT_ID -> Hb metadata before model training."""

import argparse
import json
import math
import re
from pathlib import Path

import pandas as pd

from . import config
from .matching import scan_raw_data_dir

METADATA_SUBJECT_RE = re.compile(
    r"^(?:\d{8}_\d{6}(?:_\d+)?|\d+|T_\d+_\d{8}_\d{6}|[A-Za-z]+_\d+)$"
)


class MetadataValidationError(ValueError):
    """Raised when clinical metadata cannot be used for supervised training."""


def _read_metadata(path):
    path = Path(path)
    if not path.is_file():
        raise MetadataValidationError(f"Metadata file not found: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, comment="#")
    if path.suffix.lower() in {".xls", ".xlsx"}:
        return pd.read_excel(path)
    if path.suffix.lower() == ".json":
        return pd.read_json(path)
    raise MetadataValidationError("Supported metadata formats are CSV, XLS, XLSX, and JSON")


def _image_subjects(raw_dir):
    raw_dir = Path(raw_dir)
    if not raw_dir.is_absolute() and not raw_dir.is_dir():
        project_relative_dir = config.PROJECT_ROOT.parent / raw_dir
        if project_relative_dir.is_dir():
            raw_dir = project_relative_dir
    if not raw_dir.is_dir():
        raise MetadataValidationError(f"Raw image directory not found: {raw_dir}")
    records, _ = scan_raw_data_dir(str(raw_dir))
    raw_subjects = set()
    raw_files_by_subject = {}
    for path in raw_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in config.RAW_EXTS:
            continue
        subject_id = path.stem
        raw_subjects.add(subject_id)
        raw_files_by_subject.setdefault(subject_id, []).append(path.name)
    return records, raw_subjects, raw_files_by_subject


def validate_metadata(metadata_path, raw_dir=None):
    """Return a validation report or raise MetadataValidationError.

    Hb validation uses positive finite values below 30 g/dL as a data-integrity
    bound. This is not an anaemia classification threshold or a clinical claim.
    """
    dataframe = _read_metadata(metadata_path)
    required = {"SUBJECT_ID", "Hb"}
    missing_columns = sorted(required - set(dataframe.columns))
    if missing_columns:
        raise MetadataValidationError(f"Missing required columns: {missing_columns}")
    if dataframe.empty:
        raise MetadataValidationError("Metadata contains no data rows")

    subject_ids = dataframe["SUBJECT_ID"].astype("string").str.strip()
    hb_values = pd.to_numeric(dataframe["Hb"], errors="coerce")
    missing_subject_rows = subject_ids.isna() | subject_ids.eq("") | subject_ids.eq("nan")
    missing_hb_rows = hb_values.isna()
    duplicate_subject_ids = sorted(subject_ids[subject_ids.duplicated(keep=False)].dropna().unique().tolist())
    invalid_subject_ids = sorted(
        subject_ids[~subject_ids.fillna("").str.match(METADATA_SUBJECT_RE)].dropna().unique().tolist()
    )
    invalid_hb_rows = sorted(
        dataframe.index[(~np_is_finite(hb_values)) | (hb_values <= 0) | (hb_values >= 30)].tolist()
    )

    if missing_subject_rows.any():
        raise MetadataValidationError(f"Missing SUBJECT_ID rows: {dataframe.index[missing_subject_rows].tolist()}")
    if missing_hb_rows.any():
        raise MetadataValidationError(f"Missing or non-numeric Hb rows: {dataframe.index[missing_hb_rows].tolist()}")
    if duplicate_subject_ids:
        raise MetadataValidationError(f"Duplicate SUBJECT_ID values: {duplicate_subject_ids}")
    if invalid_subject_ids:
        raise MetadataValidationError(f"Invalid SUBJECT_ID format: {invalid_subject_ids}")
    if invalid_hb_rows:
        raise MetadataValidationError(f"Invalid Hb values at rows: {invalid_hb_rows}")

    report = {
        "metadata_file": str(metadata_path),
        "metadata_rows": int(len(dataframe)),
        "metadata_subject_ids": sorted(subject_ids.tolist()),
        "raw_dir": str(raw_dir) if raw_dir else None,
        "missing_subject_ids": [],
        "missing_hb": [],
        "duplicate_subject_ids": [],
        "invalid_hb_rows": [],
        "unmatched_metadata_subjects": [],
        "unmatched_image_subjects": [],
        "multiple_images_per_subject": {},
        "valid": True,
    }

    if raw_dir:
        _, image_subjects, raw_files_by_subject = _image_subjects(raw_dir)
        metadata_subjects = set(subject_ids.tolist())
        report["unmatched_metadata_subjects"] = sorted(metadata_subjects - image_subjects)
        report["unmatched_image_subjects"] = sorted(image_subjects - metadata_subjects)
        report["multiple_images_per_subject"] = {
            subject_id: files for subject_id, files in raw_files_by_subject.items() if len(files) > 1
        }
        if report["unmatched_metadata_subjects"] or report["unmatched_image_subjects"] or report["multiple_images_per_subject"]:
            report["valid"] = False
            raise MetadataValidationError(json.dumps(report, indent=2))

    return report


def np_is_finite(values):
    return values.map(lambda value: isinstance(value, (int, float)) and math.isfinite(float(value)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", help="Verified CSV/XLS/XLSX/JSON metadata path")
    parser.add_argument("--raw-dir", default=None, help="Flat raw image directory for subject matching")
    parser.add_argument("--report", default=None, help="Optional JSON report output path")
    args = parser.parse_args()
    try:
        report = validate_metadata(args.metadata, args.raw_dir)
    except MetadataValidationError as error:
        print(f"INVALID METADATA: {error}")
        raise SystemExit(1) from error
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
