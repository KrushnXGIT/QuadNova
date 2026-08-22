"""
TEMPORARY DIAGNOSTIC PROBE — feature analysis for Level A redesign.

Computes candidate-region features over REAL positive conjunctiva images
(MITINDIA verified_flat) and over the engineered negative suite, so Level A
thresholds can be derived from data instead of guessed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent
AI_MODEL_ROOT = BACKEND_ROOT.parent / "ai_model"
for p in (str(BACKEND_ROOT), str(AI_MODEL_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.mask_generator import _detect_conjunctiva_alpha, _decode_exif_rgb  # noqa: E402
import probe_exploit_mask_bypass as exploit  # noqa: E402
import probe_root_cause as base  # noqa: E402

POSITIVES_DIR = BACKEND_ROOT.parent.parent / "MITINDIA" / "data" / "raw" / "verified_flat"


def skin_fraction_surround(rgb: np.ndarray, alpha: np.ndarray) -> float:
    """Fraction of skin-tone pixels in the ring around the candidate region."""
    ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
    cr, cb = ycrcb[..., 1], ycrcb[..., 2]
    skin = ((cr > 135) & (cr < 180) & (cb > 85) & (cb < 135) & (ycrcb[..., 0] > 60)).astype(np.uint8)

    ring = cv2.dilate((alpha > 0).astype(np.uint8), np.ones((31, 31), np.uint8)) > 0
    ring &= ~(alpha > 0)
    n = int(ring.sum())
    if n == 0:
        return 0.0
    return float(skin[ring].sum()) / float(n)


def tissue_features(rgb: np.ndarray, alpha: np.ndarray) -> dict:
    """Color/texture statistics INSIDE the candidate tissue region."""
    m = alpha > 0
    n = int(m.sum())
    if n == 0:
        return {}
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0][m].astype(np.float32), hsv[..., 1][m].astype(np.float32), hsv[..., 2][m].astype(np.float32)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)[m].astype(np.float32)

    # Pink = low hue (0..25) or wraparound (155..179); distance to pink band:
    hue_dist = np.minimum(h, np.abs(h - 180.0))
    return {
        "coverage": n / alpha.size,
        "mean_h": float(h.mean()),
        "mean_s": float(s.mean()),
        "p25_s": float(np.percentile(s, 25)),
        "mean_v": float(v.mean()),
        "p10_v": float(np.percentile(v, 10)),
        "pink_frac": float(((hue_dist <= 25) & (v >= 100)).sum() / n),
        "specular_frac": float((v >= 245).sum() / n),
        "gray_std": float(gray.std()),
        "red_dom_frac": None,  # filled by caller if needed
    }


def analyze(rgb: np.ndarray) -> dict | None:
    alpha = _detect_conjunctiva_alpha(rgb)
    if alpha is None:
        return None
    feats = tissue_features(rgb, alpha)
    feats["skin_surround"] = skin_fraction_surround(rgb, alpha)
    return feats


def summarize(name: str, rows: list) -> None:
    if not rows:
        print(f"{name}: NO DETECTIONS")
        return
    def col(k):
        return np.array([r[k] for r in rows if r.get(k) is not None], dtype=np.float64)
    out = {"n": len(rows)}
    for k in ("coverage", "mean_s", "p25_s", "mean_v", "p10_v", "pink_frac",
              "specular_frac", "gray_std", "skin_surround"):
        c = col(k)
        if len(c):
            out[k] = {
                "min": round(float(c.min()), 4),
                "p05": round(float(np.percentile(c, 5)), 4),
                "p25": round(float(np.percentile(c, 25)), 4),
                "median": round(float(np.median(c)), 4),
                "max": round(float(c.max()), 4),
            }
    print(f"== {name} == {json.dumps(out)}")


def main() -> None:
    cache_path = BACKEND_ROOT / "probe_pos_features.json"
    if cache_path.exists():
        pos_rows = json.loads(cache_path.read_text())
        print(f"positives loaded from cache: {len(pos_rows)}")
    else:
        pos_rows = []
        files = sorted(POSITIVES_DIR.glob("*.jpg"))
        print(f"positives found: {len(files)}")
        for i, f in enumerate(files):
            rgb = _decode_exif_rgb(f.read_bytes())
            feats = analyze(rgb) if rgb is not None else None
            if feats:
                pos_rows.append(feats)
            if (i + 1) % 40 == 0:
                print(f"  ...{i+1}/{len(files)} processed ({len(pos_rows)} detected)")
        cache_path.write_text(json.dumps(pos_rows))
    summarize("POSITIVES(real conjunctiva)", pos_rows)

    # NOTE: negative generators return ARRAYS; encode to JPEG bytes first so
    # they traverse the exact same decode path as real uploads.
    neg_defs = {
        "weak_room(exploit)": lambda: _decode_exif_rgb(exploit._jpeg(exploit.build_weak_positive_room_photo())),
        "red_object": lambda: _decode_exif_rgb(base.img_red_object_on_table()),
        "skin_closeup": lambda: _decode_exif_rgb(base.img_skin_closeup()),
        "food_plate": lambda: _decode_exif_rgb(base.img_food_plate()),
        "room_scene": lambda: _decode_exif_rgb(base.img_room_scene()),
        "document": lambda: _decode_exif_rgb(base.img_document()),
        "hand": lambda: _decode_exif_rgb(base.img_hand()),
        "normal_open_eye": lambda: _decode_exif_rgb(base.img_normal_open_eye()),
        "lips_closeup": lambda: _decode_exif_rgb(base.img_lips_closeup()),
    }
    neg_rows = []
    for name, fn in neg_defs.items():
        rgb = fn()
        feats = analyze(rgb) if rgb is not None else None
        if feats:
            neg_rows.append({"name": name, **feats})
            print(f"NEG {name}: {json.dumps({k: (round(v,4) if isinstance(v,float) else v) for k,v in feats.items()})}")
        else:
            print(f"NEG {name}: rejected by current detector")
    summarize("NEGATIVES(detected subset)", neg_rows)


if __name__ == "__main__":
    main()
