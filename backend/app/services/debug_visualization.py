"""Development-only visual artifacts for inspecting the validation pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def write_debug_artifacts(
    rgb: np.ndarray,
    eye_bbox: Optional[tuple[int, int, int, int]],
    eye_crop: Optional[np.ndarray],
    conjunctiva_alpha: Optional[np.ndarray],
    validation: dict,
) -> None:
    """Write validation images only when HEMOSCAN_DEBUG_DIR is configured."""
    root_value = os.getenv("HEMOSCAN_DEBUG_DIR", "").strip()
    if not root_value:
        return

    root = Path(root_value)
    root.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(root / "01_original.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    if eye_bbox is not None:
        x0, y0, x1, y1 = eye_bbox
        overlay = rgb.copy()
        cv2.rectangle(overlay, (x0, y0), (x1, y1), (217, 119, 87), 12)
        cv2.imwrite(str(root / "02_eye_bbox.png"), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    if eye_crop is not None:
        cv2.imwrite(str(root / "03_eye_crop.png"), cv2.cvtColor(eye_crop, cv2.COLOR_RGB2BGR))

    if conjunctiva_alpha is not None and np.any(conjunctiva_alpha > 0):
        overlay = rgb.copy()
        mask = conjunctiva_alpha > 0
        overlay[mask] = (0.55 * overlay[mask] + 0.45 * np.array([61, 153, 112])).astype(np.uint8)
        cv2.imwrite(str(root / "04_conjunctiva_overlay.png"), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        ys, xs = np.where(mask)
        roi = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        cv2.imwrite(str(root / "05_final_roi.png"), cv2.cvtColor(roi, cv2.COLOR_RGB2BGR))

    (root / "validation.json").write_text(json.dumps(validation, indent=2, default=str), encoding="utf-8")
