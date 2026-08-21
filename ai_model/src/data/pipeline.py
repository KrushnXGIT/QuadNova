"""
pipeline.py
===========
End-to-end orchestrator:

    Raw Data -> Validation -> Image/Mask Matching -> Subject-Level Split
             -> Preprocessing (+ Segmentation ROI prep) -> Quality Checks
             -> [Augmentation applied only inside the train dataloader]
                                                                           +                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             
Usage:
    python3 -m src.data.pipeline --raw-dir data/raw --out-dir outputs

Writes:
    <out-dir>/matching_report.json
    <out-dir>/split.json              (also written to config.SPLITS_DIR)
    <out-dir>/quality_report.json
    <out-dir>/pipeline_run_summary.json
    <processed-dir>/<split>/<subject_id>/...  preprocessed .npy tensors +
        conjunctiva ROI crops, for every subject whose files pass validation

This script NEVER opens files in RAW_DATA_DIR for writing. It is safe to
run repeatedly and re-run against the same raw directory.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

from . import config
from .matching import scan_raw_data_dir, matching_report
from .validation import validate_file, snapshot_raw_dir_checksums
from .splitting import compute_split, assert_no_overlap, save_split
from .preprocessing import preprocess_raw_photo, resize_image
from .segmentation import extract_roi, crop_to_bbox
from .quality_checks import run_quality_checks
from . import labels as labels_mod


def run_pipeline(raw_dir=None, out_dir=None, processed_dir=None, seed=None, write_tensors=True):
    raw_dir = str(raw_dir or config.RAW_DATA_DIR)
    out_dir = str(out_dir or config.REPORTS_DIR)
    processed_dir = str(processed_dir or config.PROCESSED_DATA_DIR)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    t0 = time.time()
    summary = {"started_at": t0, "raw_dir": raw_dir}

    # --- 0. checksum raw dir before touching anything ---
    checksums_before = snapshot_raw_dir_checksums(raw_dir)

    # --- 1. matching ---
    records, unclassified = scan_raw_data_dir(raw_dir)
    m_report = matching_report(raw_dir)
    with open(os.path.join(out_dir, "matching_report.json"), "w") as f:
        json.dump(m_report, f, indent=2)
    summary["n_subjects_found"] = m_report["total_subjects"]

    # --- 2. subject-level split ---
    subject_ids = list(records.keys())
    split = compute_split(subject_ids, seed=seed)
    assert_no_overlap(split)
    split_path = save_split(split, out_path=os.path.join(out_dir, "split.json"), seed=seed)
    save_split(split, seed=seed)  # also write canonical copy to config.SPLITS_DIR
    summary["split_counts"] = {k: len(v) for k, v in split.items()}
    summary["split_path"] = split_path

    # --- 3. per-subject preprocessing + ROI prep ---
    subject_to_split = {}
    for split_name, ids in split.items():
        for sid in ids:
            subject_to_split[sid] = split_name

    processed_log = []
    for sid, rec in records.items():
        split_name = subject_to_split[sid]
        subject_out = os.path.join(processed_dir, split_name, sid)
        entry = {"subject_id": sid, "split": split_name, "status": "skipped_no_raw_photo"}

        if rec.raw_photo:
            raw_path = os.path.join(raw_dir, rec.raw_photo)
            v = validate_file(raw_path, "raw_photo")
            if v["valid"]:
                try:
                    tensor = preprocess_raw_photo(raw_path, normalize=True)
                    entry["status"] = "ok"
                    entry["preprocessed_shape"] = list(tensor.shape)
                    if write_tensors:
                        os.makedirs(subject_out, exist_ok=True)
                        np.save(os.path.join(subject_out, "image.npy"), tensor.astype(np.float32))
                except Exception as e:
                    entry["status"] = f"preprocess_error: {e}"
            else:
                entry["status"] = f"invalid_raw_photo: {v['error']}"

        # segmentation ROI prep, if a combined mask exists and raw photo is valid
        if rec.raw_photo and rec.mask_forniceal_palpebral:
            mask_path = os.path.join(raw_dir, rec.mask_forniceal_palpebral)
            raw_path = os.path.join(raw_dir, rec.raw_photo)
            try:
                roi_rgba, coverage = extract_roi(raw_path, mask_path, upscale_mask_to_raw=True)
                roi_cropped = crop_to_bbox(roi_rgba)
                roi_resized = resize_image(roi_cropped[:, :, :3], size=config.MODEL_INPUT_SIZE)
                entry["roi_coverage_fraction"] = coverage
                entry["roi_shape"] = list(roi_resized.shape)
                if write_tensors:
                    os.makedirs(subject_out, exist_ok=True)
                    np.save(os.path.join(subject_out, "roi.npy"), roi_resized.astype(np.uint8))
            except Exception as e:
                entry["roi_status"] = f"roi_error: {e}"

        processed_log.append(entry)

    with open(os.path.join(out_dir, "preprocessing_log.json"), "w") as f:
        json.dump(processed_log, f, indent=2)

    # --- 4. labels (documented no-op if unavailable) ---
    labels_status = "unavailable"
    if labels_mod.labels_available():
        try:
            df = labels_mod.load_labels()
            labels_status = f"loaded {len(df)} rows"
        except labels_mod.LabelsUnavailableError as e:
            labels_status = f"error: {e}"
    summary["labels_status"] = labels_status

    # --- 5. quality checks ---
    q_report = run_quality_checks(raw_dir, split=split)
    with open(os.path.join(out_dir, "quality_report.json"), "w") as f:
        json.dump(q_report, f, indent=2)

    # --- 6. verify raw dir unchanged ---
    checksums_after = snapshot_raw_dir_checksums(raw_dir)
    raw_unchanged = checksums_before == checksums_after
    summary["raw_data_unchanged"] = raw_unchanged

    summary["duration_seconds"] = round(time.time() - t0, 3)
    summary["n_corrupted_files"] = q_report["corrupted_images"]["total_corrupted"]
    summary["n_duplicate_groups"] = q_report["duplicate_images"]["duplicate_groups"]
    summary["target_mode"] = config.TARGET_MODE

    with open(os.path.join(out_dir, "pipeline_run_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--processed-dir", default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-tensors", action="store_true", help="skip writing .npy tensors, just run checks")
    args = ap.parse_args()

    try:
        summary = run_pipeline(
            raw_dir=args.raw_dir,
            out_dir=args.out_dir,
            processed_dir=args.processed_dir,
            seed=args.seed,
            write_tensors=not args.no_tensors,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
