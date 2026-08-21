"""Prepare the nested Eyes-Defy-Anemia release for the existing flat pipeline.

This copies only usable derived image/mask files; source data is never modified.
Hb values are copied from the country workbooks after exact Number-folder
matching. Rows without usable Hgb or a combined mask are excluded and reported.
"""

import argparse
import json
import math
import shutil
from pathlib import Path

import pandas as pd
import cv2


COUNTRIES = ("India", "Italy")


def _usable_hgb(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and 0 < number < 30


def prepare_dataset(source_root, output_root, metadata_path, report_path):
    source_root = Path(source_root)
    output_root = Path(output_root)
    metadata_path = Path(metadata_path)
    report_path = Path(report_path)
    output_root.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    for existing in output_root.iterdir():
        if existing.is_file() or existing.is_symlink():
            existing.unlink()
        elif existing.is_dir():
            shutil.rmtree(existing)

    labels = []
    report = {"source_root": str(source_root), "countries": {}, "excluded": []}
    seen_subject_ids = set()

    for country in COUNTRIES:
        country_root = source_root / country
        workbook = country_root / f"{country}.xlsx"
        if not workbook.is_file():
            raise FileNotFoundError(f"Missing workbook: {workbook}")
        dataframe = pd.read_excel(workbook)
        required = {"Number", "Hgb"}
        missing = required - set(dataframe.columns)
        if missing:
            raise ValueError(f"{workbook} missing columns: {sorted(missing)}")

        rows = {int(row["Number"]): row for _, row in dataframe.iterrows()}
        country_report = {"workbook": str(workbook), "workbook_rows": len(dataframe), "included": 0, "excluded": []}
        for folder in sorted(country_root.iterdir(), key=lambda path: int(path.name) if path.name.isdigit() else 10**9):
            if not folder.is_dir() or not folder.name.isdigit():
                continue
            number = int(folder.name)
            row = rows.get(number)
            raw_files = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.jpeg"))
            mask_files = sorted(folder.glob("*_forniceal_palpebral.png"))
            reason = None
            if row is None:
                reason = "folder_number_missing_from_workbook"
            elif not _usable_hgb(row["Hgb"]):
                reason = "missing_or_invalid_hgb"
            elif len(raw_files) != 1:
                reason = f"expected_one_raw_image_found_{len(raw_files)}"
            elif len(mask_files) != 1:
                reason = f"expected_one_combined_mask_found_{len(mask_files)}"
            elif (mask_image := cv2.imread(str(mask_files[0]), cv2.IMREAD_UNCHANGED)) is None or mask_image.ndim != 3 or mask_image.shape[2] != 4:
                reason = "combined_mask_not_rgba"

            if reason:
                entry = {"country": country, "number": number, "reason": reason}
                country_report["excluded"].append(entry)
                report["excluded"].append(entry)
                continue

            raw_path = raw_files[0]
            mask_path = mask_files[0]
            # The workbook Number is a per-country ID, so use a country-qualified
            # subject key to keep the flat dataset globally unique. Some source
            # images use raw date-style stems, while others were already numbered,
            # so the canonical ID is derived from the verified workbook metadata
            # rather than the file stem.
            subject_id = f"{country}_{number}"
            if subject_id in seen_subject_ids:
                raise ValueError(f"Duplicate raw-image subject ID across countries: {subject_id}")
            seen_subject_ids.add(subject_id)
            shutil.copy2(raw_path, output_root / f"{subject_id}{raw_path.suffix}")
            shutil.copy2(mask_path, output_root / f"{subject_id}_forniceal_palpebral.png")
            labels.append({"SUBJECT_ID": subject_id, "Hb": float(row["Hgb"]), "country": country, "source_number": number})
            country_report["included"] += 1
        report["countries"][country] = country_report

    labels_frame = pd.DataFrame(labels)
    labels_frame.to_csv(metadata_path, index=False)
    report["included_subjects"] = len(labels)
    report["metadata_path"] = str(metadata_path)
    report["output_root"] = str(output_root)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default="data/raw/dataset anemia")
    parser.add_argument("--output-root", default="data/raw/verified_flat")
    parser.add_argument("--metadata", default="data/metadata/labels.csv")
    parser.add_argument("--report", default="outputs/dataset_preparation_report.json")
    args = parser.parse_args()
    report = prepare_dataset(args.source_root, args.output_root, args.metadata, args.report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
