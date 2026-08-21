"""
make_synthetic_fixtures.py
===========================
Generates a SYNTHETIC, CLEARLY-FAKE test dataset that mimics the *file
structure and known defects* Account 1 confirmed in DATASET_SCHEMA.md /
DATASET_VERIFICATION_REPORT.md — nothing else. This exists ONLY so the
Phase 2 pipeline code can be executed and checked mechanically (does it
run, does the split leak, does it detect the iCCP defect, etc.) since the
real dataset was not included in the ZIP handed to Account 2 (see
HANDOFF.md "Blockers").

THIS IS NOT REAL DATA. No Hb values, no real subjects, no real images.
Pixel content is random noise; do not use these files for anything other
than exercising the pipeline code path. A "labels.csv" fixture with
obviously-fake Hb values is also generated, SEPARATELY, and is only used
to test the labels.py loading code path — it is written to a directory
that is clearly named synthetic and is never treated as real metadata.

Mimicked properties (traced to Account 1's findings):
  - filename convention {SUBJECT_ID}[.jpg|_forniceal.png|_palpebral.png|
    _forniceal_palpebral.png], SUBJECT_ID = YYYYMMDD_HHMMSS
  - raw photo: JPEG, RGB, EXIF Orientation=6 tag on some subjects
  - masks: RGBA PNG, corrupted iCCP chunk (bad CRC) injected, to test that
    validation.load_mask (OpenCV) succeeds where PIL would fail
  - one subject with mask files but no raw photo (missing-raw case)
  - one subject with a duplicate raw photo (exact byte copy, to test
    duplicate detection)
  - one corrupted/truncated file (to test corrupted-image detection)
  - forniceal_palpebral mask = union of forniceal + palpebral (alpha OR)
"""

import io
import os
import shutil
import stat
import zlib

import numpy as np
import piexif
from PIL import Image

SYNTHETIC_ROOT = os.path.join(os.path.dirname(__file__), "synthetic_fixtures")
SYNTHETIC_RAW_DIR = os.path.join(SYNTHETIC_ROOT, "raw")
SYNTHETIC_METADATA_DIR = os.path.join(SYNTHETIC_ROOT, "metadata")

SUBJECT_IDS = [
    "20990101_120000",  # complete quad, orientation=6 (needs rotation)
    "20990102_130500",  # complete quad, orientation=1 (no rotation needed)
    "20990103_140000",  # masks only, NO raw photo (missing-raw case)
    "20990104_150000",  # raw photo only, NO masks
    "20990105_160000",  # complete quad, will get a duplicate raw photo
]


def _corrupt_iccp_crc(png_bytes):
    """Flip one byte inside the first iCCP chunk's CRC to reproduce the
    exact defect Account 1 found in the real masks (bad CRC, chunk data
    otherwise intact -> OpenCV still decodes it, PIL raises SyntaxError)."""
    sig = b"\x89PNG\r\n\x1a\n"
    assert png_bytes[:8] == sig
    pos = 8
    out = bytearray(png_bytes)
    while pos < len(out):
        length = int.from_bytes(out[pos:pos + 4], "big")
        ctype = bytes(out[pos + 4:pos + 8])
        if ctype == b"iCCP":
            crc_pos = pos + 8 + length
            out[crc_pos] ^= 0xFF  # flip bits -> CRC mismatch, chunk data untouched
            return bytes(out)
        if ctype == b"IEND":
            break
        pos += 8 + length + 4
    # no iCCP chunk existed (Pillow doesn't write one by default) -> insert a
    # deliberately-bad one right after IHDR so downstream code has one to trip on
    ihdr_end = 8 + 8 + 13 + 4  # sig + (len+type) + IHDR data + crc
    fake_iccp_data = b"fake_icc_profile_data_for_testing"
    chunk_type = b"iCCP"
    bad_crc = (zlib.crc32(chunk_type + fake_iccp_data) & 0xFFFFFFFF) ^ 0xFFFFFFFF
    chunk = (
        len(fake_iccp_data).to_bytes(4, "big")
        + chunk_type
        + fake_iccp_data
        + bad_crc.to_bytes(4, "big")
    )
    return bytes(out[:ihdr_end]) + chunk + bytes(out[ihdr_end:])


def _make_raw_photo_bytes(width, height, orientation, seed):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, size=(height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")

    exif_dict = {"0th": {piexif.ImageIFD.Orientation: orientation,
                          piexif.ImageIFD.Make: b"SyntheticTestDevice",
                          piexif.ImageIFD.Model: b"FixtureCam"}}
    exif_bytes = piexif.dump(exif_dict)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, exif=exif_bytes)
    return buf.getvalue()


def _make_mask_bytes(width, height, seed, coverage="hard"):
    """Return (rgba_array, png_bytes_with_corrupted_iccp)."""
    rng = np.random.default_rng(seed)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, :3] = rng.integers(80, 200, size=(height, width, 3), dtype=np.uint8)

    yy, xx = np.mgrid[0:height, 0:width]
    cy, cx = height // 2, width // 2
    r = min(height, width) // 3
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    if coverage == "hard":
        alpha = np.where(dist < r, 255, 0).astype(np.uint8)
    else:  # soft/anti-aliased, mimicking the second sampled subject
        alpha = np.clip(255 - (dist - r), 0, 255).astype(np.uint8)

    rgba[:, :, 3] = alpha
    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    corrupted = _corrupt_iccp_crc(buf.getvalue())
    return rgba, corrupted


def _remove_synthetic_root(path):
    """Delete a synthetic fixture tree even when Windows marks files read-only."""
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files + dirs:
            full = os.path.join(root, name)
            try:
                os.chmod(full, os.stat(full).st_mode | stat.S_IWRITE)
            except OSError:
                pass
            try:
                os.remove(full) if os.path.isfile(full) else os.rmdir(full)
            except OSError:
                pass
    try:
        os.rmdir(path)
    except OSError:
        pass


def build_synthetic_fixtures(force=False):
    if os.path.isdir(SYNTHETIC_ROOT):
        if not force:
            return SYNTHETIC_RAW_DIR, SYNTHETIC_METADATA_DIR
        _remove_synthetic_root(SYNTHETIC_ROOT)

    os.makedirs(SYNTHETIC_RAW_DIR, exist_ok=True)
    os.makedirs(SYNTHETIC_METADATA_DIR, exist_ok=True)

    raw_w, raw_h = 400, 300          # small on purpose — fixtures only, not realism
    mask_w, mask_h = 107, 80         # keeps the ~3.735x ratio in spirit at tiny scale

    # subject 1: complete quad, orientation=6 (needs rotation)
    sid = SUBJECT_IDS[0]
    raw_bytes = _make_raw_photo_bytes(raw_w, raw_h, orientation=6, seed=1)
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}.jpg"), "wb") as f:
        f.write(raw_bytes)
    forn_rgba, forn_png = _make_mask_bytes(mask_h, mask_w, seed=2, coverage="hard")  # rotated dims
    palp_rgba, palp_png = _make_mask_bytes(mask_h, mask_w, seed=3, coverage="hard")
    union_alpha = np.maximum(forn_rgba[:, :, 3], palp_rgba[:, :, 3])
    union_rgba = forn_rgba.copy()
    union_rgba[:, :, 3] = union_alpha
    union_img = Image.fromarray(union_rgba, mode="RGBA")
    buf = io.BytesIO()
    union_img.save(buf, format="PNG")
    union_png = _corrupt_iccp_crc(buf.getvalue())
    for suffix, data in [("_forniceal", forn_png), ("_palpebral", palp_png), ("_forniceal_palpebral", union_png)]:
        with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}{suffix}.png"), "wb") as f:
            f.write(data)

    # subject 2: complete quad, orientation=1, soft/anti-aliased masks
    sid = SUBJECT_IDS[1]
    raw_bytes = _make_raw_photo_bytes(raw_w, raw_h, orientation=1, seed=11)
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}.jpg"), "wb") as f:
        f.write(raw_bytes)
    forn_rgba, forn_png = _make_mask_bytes(mask_h, mask_w, seed=12, coverage="soft")
    palp_rgba, palp_png = _make_mask_bytes(mask_h, mask_w, seed=13, coverage="soft")
    union_alpha = np.maximum(forn_rgba[:, :, 3], palp_rgba[:, :, 3])
    union_rgba = forn_rgba.copy()
    union_rgba[:, :, 3] = union_alpha
    union_img = Image.fromarray(union_rgba, mode="RGBA")
    buf = io.BytesIO()
    union_img.save(buf, format="PNG")
    union_png = _corrupt_iccp_crc(buf.getvalue())
    for suffix, data in [("_forniceal", forn_png), ("_palpebral", palp_png), ("_forniceal_palpebral", union_png)]:
        with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}{suffix}.png"), "wb") as f:
            f.write(data)

    # subject 3: masks only, no raw photo
    sid = SUBJECT_IDS[2]
    _, forn_png = _make_mask_bytes(mask_h, mask_w, seed=21, coverage="hard")
    _, palp_png = _make_mask_bytes(mask_h, mask_w, seed=22, coverage="hard")
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}_forniceal.png"), "wb") as f:
        f.write(forn_png)
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}_palpebral.png"), "wb") as f:
        f.write(palp_png)

    # subject 4: raw photo only, no masks
    sid = SUBJECT_IDS[3]
    raw_bytes = _make_raw_photo_bytes(raw_w, raw_h, orientation=1, seed=31)
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}.jpg"), "wb") as f:
        f.write(raw_bytes)

    # subject 5: complete quad + an exact duplicate raw photo (different subject id, same bytes)
    sid = SUBJECT_IDS[4]
    raw_bytes = _make_raw_photo_bytes(raw_w, raw_h, orientation=1, seed=41)
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}.jpg"), "wb") as f:
        f.write(raw_bytes)
    forn_rgba, forn_png = _make_mask_bytes(mask_h, mask_w, seed=42, coverage="hard")
    palp_rgba, palp_png = _make_mask_bytes(mask_h, mask_w, seed=43, coverage="hard")
    union_alpha = np.maximum(forn_rgba[:, :, 3], palp_rgba[:, :, 3])
    union_rgba = forn_rgba.copy()
    union_rgba[:, :, 3] = union_alpha
    union_img = Image.fromarray(union_rgba, mode="RGBA")
    buf = io.BytesIO()
    union_img.save(buf, format="PNG")
    union_png = _corrupt_iccp_crc(buf.getvalue())
    for suffix, data in [("_forniceal", forn_png), ("_palpebral", palp_png), ("_forniceal_palpebral", union_png)]:
        with open(os.path.join(SYNTHETIC_RAW_DIR, f"{sid}{suffix}.png"), "wb") as f:
            f.write(data)
    # duplicate: same bytes, different (fake) subject id -> tests duplicate detection
    dup_sid = "20990106_170000"
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{dup_sid}.jpg"), "wb") as f:
        f.write(raw_bytes)

    # a corrupted/truncated file to test corrupted-image detection
    trunc_sid = "20990107_180000"
    full = _make_raw_photo_bytes(raw_w, raw_h, orientation=1, seed=51)
    with open(os.path.join(SYNTHETIC_RAW_DIR, f"{trunc_sid}.jpg"), "wb") as f:
        f.write(full[: len(full) // 3])  # truncate

    # a stray unclassifiable file
    with open(os.path.join(SYNTHETIC_RAW_DIR, "README_not_a_subject_file.txt"), "w") as f:
        f.write("synthetic fixture directory, ignore\n")

    # synthetic (obviously fake) metadata table, to test labels.py's loading
    # code path only -- these Hb values are NOT real and are clearly labeled.
    import csv
    with open(os.path.join(SYNTHETIC_METADATA_DIR, "labels.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["SUBJECT_ID", "Hb"])
        for i, sid in enumerate(SUBJECT_IDS):
            writer.writerow([sid, round(11.0 + i * 0.3, 1)])  # synthetic placeholder values

    return SYNTHETIC_RAW_DIR, SYNTHETIC_METADATA_DIR


if __name__ == "__main__":
    raw_dir, meta_dir = build_synthetic_fixtures(force=True)
    print(f"Synthetic fixtures written to: {raw_dir}")
    print(f"Synthetic metadata written to: {meta_dir}")
    print("Reminder: this is fabricated test data for pipeline validation only, NOT the real dataset.")
