"""
TEMPORARY DIAGNOSTIC PROBE — check IoU overlap between the real annotated
dataset mask and the independently auto-detected mask, to calibrate the
overlap threshold for the fix (client-supplied masks must overlap the
server-detected region to be trusted).
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

BACKEND_ROOT = Path(__file__).resolve().parent
AI_MODEL_ROOT = BACKEND_ROOT.parent / "ai_model"
for p in (str(BACKEND_ROOT), str(AI_MODEL_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.mask_generator import generate_mask_png, _detect_conjunctiva_alpha, _decode_exif_rgb  # noqa: E402

DATA_DIR = BACKEND_ROOT.parent / "data" / "raw" / "sample_dataset"


def load_mask_alpha(path: Path) -> np.ndarray:
    bgra = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    return bgra[:, :, 3]


def iou(a: np.ndarray, b: np.ndarray) -> float:
    a_bin = a > 0
    b_bin = b > 0
    inter = np.logical_and(a_bin, b_bin).sum()
    union = np.logical_or(a_bin, b_bin).sum()
    return float(inter) / float(union) if union else 0.0


def overlap_fraction_of_client(detected: np.ndarray, client: np.ndarray) -> float:
    d = detected > 0
    c = client > 0
    inter = np.logical_and(d, c).sum()
    return float(inter) / float(c.sum()) if c.sum() else 0.0


def main() -> None:
    for stem in ["20200118_164733", "20200203_091841"]:
        raw_path = DATA_DIR / f"{stem}.jpg"
        mask_path = DATA_DIR / f"{stem}_forniceal_palpebral.png"
        if not raw_path.is_file() or not mask_path.is_file():
            print(f"{stem}: missing files, skipping")
            continue

        image_bytes = raw_path.read_bytes()
        rgb = _decode_exif_rgb(image_bytes)
        detected = _detect_conjunctiva_alpha(rgb)
        print(f"{stem}: detected={'YES' if detected is not None else 'NO'}, raw_shape={rgb.shape[:2]}")
        if detected is None:
            continue

        client_alpha_native = load_mask_alpha(mask_path)
        # Resize the real annotated (native, low-res) mask up to raw resolution,
        # matching the convention used elsewhere in the pipeline.
        client_alpha = cv2.resize(
            client_alpha_native, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR
        )

        the_iou = iou(detected, client_alpha)
        overlap_of_client = overlap_fraction_of_client(detected, client_alpha)
        print(
            f"{stem}: IoU(detected, real_mask)={the_iou:.4f}  "
            f"overlap_fraction_of_client={overlap_of_client:.4f}  "
            f"detected_coverage={detected.mean()/255:.4f}  "
            f"client_coverage={ (client_alpha>0).mean():.4f}"
        )


if __name__ == "__main__":
    main()
