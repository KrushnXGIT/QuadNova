"""
data_analysis.py
=================
Phase 1 - Dataset Verification (read-only).

Scans an Eyes-Defy-Anemia-style image folder and reports, per subject:
  - which files exist (raw photo / segmentation masks)
  - image format, dimensions, color mode
  - EXIF capture metadata (device, orientation, timestamp) when present
  - mask alpha-channel statistics (coverage %, distinct alpha levels,
    binary vs. soft/anti-aliased mask)
  - geometric relationship between raw photo size and mask size
    (detects EXIF-orientation rotation + downscale factor)
  - PNG structural integrity (chunk-level CRC check), since this sample
    contains masks with a corrupted iCCP chunk that crashes a naive
    PIL.Image.open() call.

This script NEVER writes to, moves, renames, or deletes anything inside
the input dataset directory. All output is printed to stdout and written
to a separate report file passed via --out.

Usage:
    python3 data_analysis.py --data-dir /path/to/sample_dataset --out report.json
"""

import argparse
import json
import os
import re
import struct
import sys
import zlib
from collections import defaultdict

import cv2
import numpy as np
from PIL import Image, ExifTags

MASK_SUFFIXES = ["_forniceal_palpebral", "_forniceal", "_palpebral"]
RAW_EXTS = {".jpg", ".jpeg"}
MASK_EXTS = {".png"}

SUBJECT_ID_RE = re.compile(r"^(?P<subject_id>\d{8}_\d{6})")


def classify_file(filename):
    """Return (subject_id, role) for a file in the dataset folder."""
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    m = SUBJECT_ID_RE.match(name)
    if not m:
        return None, None
    subject_id = m.group("subject_id")
    remainder = name[len(subject_id):]

    if ext in RAW_EXTS and remainder == "":
        return subject_id, "raw_photo"
    if ext in MASK_EXTS:
        for suffix in MASK_SUFFIXES:
            if remainder == suffix:
                return subject_id, f"mask{suffix}"
    return subject_id, f"unclassified:{remainder}{ext}"


def check_png_crc_integrity(path):
    """Manually walk PNG chunks and verify CRC per chunk.
    Returns (is_valid, list_of_bad_chunks). Does not use PIL, since a
    single bad-CRC chunk makes PIL refuse to open the file at all.
    """
    bad_chunks = []
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return False, ["missing PNG signature"]
    pos = 8
    while pos < len(data):
        if pos + 8 > len(data):
            bad_chunks.append("truncated file (chunk header)")
            break
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunk_data = data[pos + 8:pos + 8 + length]
        stored_crc = data[pos + 8 + length:pos + 12 + length]
        if len(stored_crc) < 4:
            bad_chunks.append(f"{ctype.decode(errors='replace')}: truncated CRC")
            break
        computed_crc = zlib.crc32(ctype + chunk_data) & 0xFFFFFFFF
        stored_crc_int = struct.unpack(">I", stored_crc)[0]
        if computed_crc != stored_crc_int:
            bad_chunks.append(ctype.decode(errors="replace"))
        pos += 8 + length + 4
        if ctype == b"IEND":
            break
    return (len(bad_chunks) == 0), bad_chunks


def read_exif(path):
    try:
        img = Image.open(path)
        exif = img._getexif()
        if not exif:
            return {}
        out = {}
        for tag_id, val in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag in ("Make", "Model", "Orientation", "DateTime",
                       "DateTimeOriginal", "ExifImageWidth", "ExifImageHeight"):
                out[tag] = val
        return out
    except Exception as e:
        return {"_error": str(e)}


def analyze_raw_photo(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return {"error": "cv2 failed to load"}
    h, w = img.shape[:2]
    channels = img.shape[2] if img.ndim == 3 else 1
    return {
        "width": int(w),
        "height": int(h),
        "channels": int(channels),
        "file_size_bytes": os.path.getsize(path),
        "exif": read_exif(path),
    }


def analyze_mask(path):
    crc_ok, bad_chunks = check_png_crc_integrity(path)

    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return {
            "error": "cv2 failed to load",
            "png_crc_valid": crc_ok,
            "png_bad_chunks": bad_chunks,
        }

    h, w = img.shape[:2]
    result = {
        "width": int(w),
        "height": int(h),
        "channels": int(img.shape[2]) if img.ndim == 3 else 1,
        "file_size_bytes": os.path.getsize(path),
        "png_crc_valid": crc_ok,
        "png_bad_chunks": bad_chunks,
    }

    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        nonzero = alpha > 0
        uniq_vals = np.unique(alpha)
        result["has_alpha"] = True
        result["mask_coverage_fraction"] = round(float(nonzero.sum()) / alpha.size, 4)
        result["distinct_alpha_levels"] = int(len(uniq_vals))
        result["alpha_is_binary"] = bool(len(uniq_vals) <= 2)
        if nonzero.any():
            bgr = img[:, :, :3]
            masked_px = bgr[nonzero]
            result["mean_bgr_in_mask"] = [round(float(x), 2) for x in masked_px.mean(axis=0)]
    else:
        result["has_alpha"] = False

    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", required=True, help="Path to the sample dataset directory (read-only)")
    ap.add_argument("--out", default="dataset_analysis_report.json", help="Path to write JSON report")
    args = ap.parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"ERROR: {args.data_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    files = sorted(os.listdir(args.data_dir))
    subjects = defaultdict(dict)
    unclassified = []

    for fname in files:
        fpath = os.path.join(args.data_dir, fname)
        if not os.path.isfile(fpath):
            continue
        subject_id, role = classify_file(fname)
        if subject_id is None:
            unclassified.append(fname)
            continue
        if role.startswith("unclassified"):
            unclassified.append(fname)
            continue

        if role == "raw_photo":
            subjects[subject_id][role] = analyze_raw_photo(fpath)
        else:
            subjects[subject_id][role] = analyze_mask(fpath)

    report = {
        "data_dir": os.path.abspath(args.data_dir),
        "total_files_scanned": len([f for f in files if os.path.isfile(os.path.join(args.data_dir, f))]),
        "unique_subjects": len(subjects),
        "unclassified_files": unclassified,
        "subjects": {},
    }

    for subject_id, roles in sorted(subjects.items()):
        entry = {"available_files": sorted(roles.keys())}
        entry["has_raw_photo"] = "raw_photo" in roles
        entry["has_forniceal_mask"] = "mask_forniceal" in roles
        entry["has_palpebral_mask"] = "mask_palpebral" in roles
        entry["has_combined_mask"] = "mask_forniceal_palpebral" in roles
        entry["details"] = roles

        # geometric relationship: raw photo vs combined mask
        if entry["has_raw_photo"] and entry["has_combined_mask"]:
            raw = roles["raw_photo"]
            mask = roles["mask_forniceal_palpebral"]
            if "width" in raw and "width" in mask:
                raw_w, raw_h = raw["width"], raw["height"]
                mask_w, mask_h = mask["width"], mask["height"]
                # check straight scale vs rotated-then-scaled
                straight_ratio_w = raw_w / mask_w
                straight_ratio_h = raw_h / mask_h
                rotated_ratio_w = raw_h / mask_w
                rotated_ratio_h = raw_w / mask_h
                is_rotated = abs(rotated_ratio_w - rotated_ratio_h) < abs(straight_ratio_w - straight_ratio_h)
                entry["raw_to_mask_geometry"] = {
                    "raw_size": [raw_w, raw_h],
                    "mask_size": [mask_w, mask_h],
                    "appears_rotated_90": is_rotated,
                    "approx_scale_factor": round(rotated_ratio_w if is_rotated else straight_ratio_w, 3),
                }

        report["subjects"][subject_id] = entry

    # Union check: does forniceal_palpebral == forniceal + palpebral (pixel count)?
    for subject_id, entry in report["subjects"].items():
        details = entry["details"]
        if all(k in details for k in ("mask_forniceal", "mask_palpebral", "mask_forniceal_palpebral")):
            f_cov = details["mask_forniceal"].get("mask_coverage_fraction")
            p_cov = details["mask_palpebral"].get("mask_coverage_fraction")
            c_cov = details["mask_forniceal_palpebral"].get("mask_coverage_fraction")
            if None not in (f_cov, p_cov, c_cov):
                entry["combined_mask_equals_union_of_parts"] = abs((f_cov + p_cov) - c_cov) < 0.005

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    print(f"\n[data_analysis.py] Report written to {args.out}", file=sys.stderr)
    print("[data_analysis.py] No files in --data-dir were modified.", file=sys.stderr)


if __name__ == "__main__":
    main()
