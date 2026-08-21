"""
quality_checks.py
==================
Runs the full required QC suite and returns a single JSON-serializable
report. Read-only against RAW_DATA_DIR throughout.

Checks implemented (per PROJECT instructions):
  - missing images            -> subjects with masks but no raw photo
  - missing labels            -> reported as a dataset-wide blocker (no
                                  metadata table exists yet — see labels.py)
  - corrupted images          -> validation.validate_file() on every file
  - duplicate images          -> md5-based exact-duplicate detection
  - subject leakage           -> splitting.assert_no_overlap()
  - split overlap             -> same check, explicit pass/fail
  - target distribution       -> only computable once labels are available;
                                  reported as "not computable" otherwise,
                                  never fabricated
  - image dimensions          -> distribution of (H, W) across raw photos
                                  and masks, to catch inconsistent capture
                                  devices/resolutions
"""

import os
from collections import Counter

from . import config, labels
from .matching import scan_raw_data_dir
from .splitting import assert_no_overlap
from .validation import validate_file, find_duplicate_files


def run_quality_checks(raw_data_dir=None, split=None):
    raw_data_dir = str(raw_data_dir or config.RAW_DATA_DIR)
    records, unclassified_files = scan_raw_data_dir(raw_data_dir)

    report = {"raw_data_dir": raw_data_dir}

    # --- missing images (masks with no raw photo) ---
    missing_raw = [sid for sid, r in records.items() if r.has_any_mask and not r.has_raw]
    missing_mask = [sid for sid, r in records.items() if r.has_raw and not r.has_any_mask]
    report["missing_images"] = {
        "subjects_with_mask_but_no_raw_photo": sorted(missing_raw),
        "subjects_with_raw_photo_but_no_mask": sorted(missing_mask),
        "count_mask_no_raw": len(missing_raw),
        "count_raw_no_mask": len(missing_mask),
    }

    # --- missing labels ---
    report["missing_labels"] = {
        "labels_available": labels.labels_available(),
        "note": (
            "No Hb/label metadata table is available (documented blocker — "
            "see HANDOFF.md). Every subject is therefore currently 'missing "
            "its label'. This is not evaluated per-subject until a metadata "
            "table is supplied."
        ),
    }

    # --- corrupted images ---
    all_file_entries = []  # (path, role)
    for sid, rec in records.items():
        for role in rec.available_roles():
            fname = getattr(rec, role)
            all_file_entries.append((os.path.join(raw_data_dir, fname), role))

    validations = [validate_file(p, role) for p, role in all_file_entries]
    corrupted = [v for v in validations if not v["valid"]]
    report["corrupted_images"] = {
        "total_files_checked": len(validations),
        "total_corrupted": len(corrupted),
        "details": corrupted,
    }

    # --- duplicate images ---
    all_paths = [p for p, _ in all_file_entries]
    dupes = find_duplicate_files(all_paths)
    report["duplicate_images"] = {
        "duplicate_groups": len(dupes),
        "details": {h: paths for h, paths in dupes.items()},
    }

    # --- image dimensions ---
    dim_counter_raw = Counter()
    dim_counter_mask = Counter()
    for v in validations:
        if not v["valid"]:
            continue
        dims = (v.get("height"), v.get("width"))
        if v["role"] == "raw_photo":
            dim_counter_raw[dims] += 1
        else:
            dim_counter_mask[dims] += 1
    report["image_dimensions"] = {
        "raw_photo_dimension_counts": {f"{h}x{w}": c for (h, w), c in dim_counter_raw.items()},
        "mask_dimension_counts": {f"{h}x{w}": c for (h, w), c in dim_counter_mask.items()},
    }

    # --- unclassified files ---
    report["unclassified_files"] = unclassified_files

    # --- subject leakage / split overlap ---
    if split is not None:
        try:
            assert_no_overlap(split)
            report["split_overlap"] = {"overlap_detected": False}
        except AssertionError as e:
            report["split_overlap"] = {"overlap_detected": True, "detail": str(e)}

        # every subject with data should appear in exactly one split
        all_split_ids = set(split["train"]) | set(split["val"]) | set(split["test"])
        all_data_ids = set(records.keys())
        report["subject_leakage"] = {
            "subjects_in_data_not_in_any_split": sorted(all_data_ids - all_split_ids),
            "subjects_in_split_not_in_data": sorted(all_split_ids - all_data_ids),
        }
    else:
        report["split_overlap"] = {"note": "no split provided to quality_checks"}
        report["subject_leakage"] = {"note": "no split provided to quality_checks"}

    # --- target distribution ---
    if labels.labels_available():
        df = labels.load_labels()
        if "Hb" in df.columns:
            report["target_distribution"] = {
                "target": "Hb",
                "count": int(df["Hb"].count()),
                "mean": float(df["Hb"].mean()),
                "std": float(df["Hb"].std()),
                "min": float(df["Hb"].min()),
                "max": float(df["Hb"].max()),
            }
        elif "anaemia_class" in df.columns:
            report["target_distribution"] = {
                "target": "anaemia_class",
                "value_counts": df["anaemia_class"].value_counts().to_dict(),
            }
        else:
            report["target_distribution"] = {"note": "metadata file present but no Hb/anaemia_class column found"}
    else:
        report["target_distribution"] = {
            "note": "NOT COMPUTABLE — no metadata table available. Not fabricated."
        }

    return report
