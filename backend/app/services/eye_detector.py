"""MediaPipe eye localization for the fail-closed screening pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import cv2

from .mask_generator import _detect_conjunctiva_alpha


LEFT_EYE = (33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246)
RIGHT_EYE = (362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398)
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "vision" / "face_landmarker.task"


@dataclass(frozen=True)
class EyeDetectionResult:
    detected: bool
    confidence: float
    bbox: Optional[tuple[int, int, int, int]]
    eye_crop: Optional[np.ndarray]
    eye: Optional[str] = None
    reason: Optional[str] = None


class EyeDetector:
    """Face-landmark eye detector; face presence alone never counts as success."""

    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        if not model_path.is_file():
            raise FileNotFoundError(f"Eye landmark model not found: {model_path}")
        options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
        )
        self._mp = mp
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)

    def close(self) -> None:
        self._landmarker.close()

    def detect(self, rgb: np.ndarray) -> EyeDetectionResult:
        if not isinstance(rgb, np.ndarray) or rgb.ndim != 3 or rgb.shape[2] != 3:
            return EyeDetectionResult(False, 0.0, None, None, reason="invalid_image_shape")

        original_h, original_w = rgb.shape[:2]
        scale = min(1.0, 1024.0 / max(original_h, original_w))
        if scale < 1.0:
            detect_rgb = cv2.resize(
                rgb,
                (int(round(original_w * scale)), int(round(original_h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            detect_rgb = rgb
        h, w = detect_rgb.shape[:2]
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(detect_rgb),
        )
        result = self._landmarker.detect(image)
        if not result.face_landmarks:
            return EyeDetectionResult(False, 0.0, None, None, reason="no_face_detected")

        landmarks = result.face_landmarks[0]
        candidates = []
        for name, indices in (("left", LEFT_EYE), ("right", RIGHT_EYE)):
            xs = np.array([landmarks[i].x * w for i in indices], dtype=float)
            ys = np.array([landmarks[i].y * h for i in indices], dtype=float)
            x0, x1 = max(0, int(np.floor(xs.min()))), min(w, int(np.ceil(xs.max())))
            y0, y1 = max(0, int(np.floor(ys.min()))), min(h, int(np.ceil(ys.max())))
            width, height = x1 - x0, y1 - y0
            if width < 12 or height < 8:
                continue
            area_fraction = (width * height) / float(w * h)
            if not 0.0008 <= area_fraction <= 0.35:
                continue
            pad_x, pad_y = max(4, int(width * 0.35)), max(4, int(height * 0.8))
            bx0, bx1 = max(0, x0 - pad_x), min(w, x1 + pad_x)
            by0, by1 = max(0, y0 - pad_y), min(h, y1 + pad_y)
            candidates.append((width * height, name, (
                int(bx0 / scale), int(by0 / scale),
                int(bx1 / scale), int(by1 / scale),
            )))

        if not candidates:
            return EyeDetectionResult(False, 0.0, None, None, reason="eye_landmarks_invalid")

        area, name, bbox = max(candidates)
        x0, y0, x1, y1 = bbox
        confidence = min(1.0, max(0.0, area / float(w * h) / 0.08))
        return EyeDetectionResult(True, confidence, bbox, rgb[y0:y1, x0:x1].copy(), eye=name)


_detector: Optional[EyeDetector] = None


def detect_eye(rgb: np.ndarray) -> EyeDetectionResult:
    """Detect and crop one eye, supporting both face and close-up captures.

    MediaPipe handles ordinary face images. Close-up conjunctiva captures do
    not contain a detectable face, so their eye localization uses the existing
    candidate mask plus its local eye-context check. Conjunctiva tissue
    evidence and ROI quality are still evaluated by the next gate; this branch
    never authorizes Hb inference by itself.
    """
    global _detector
    try:
        if _detector is None:
            _detector = EyeDetector()
        result = _detector.detect(rgb)
        if result.detected:
            return result

        # Close-up captures intentionally omit the face. The candidate mask's
        # morphology and local dark eye context provide the crop boundary.
        candidate = _detect_conjunctiva_alpha(rgb)
        if candidate is None:
            return EyeDetectionResult(False, 0.0, None, None, reason=result.reason)
        ys, xs = np.where(candidate > 0)
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        pad_x = max(12, int((x1 - x0) * 0.12))
        pad_y = max(12, int((y1 - y0) * 0.20))
        x0, x1 = max(0, x0 - pad_x), min(rgb.shape[1], x1 + pad_x)
        y0, y1 = max(0, y0 - pad_y), min(rgb.shape[0], y1 + pad_y)
        crop = rgb[y0:y1, x0:x1].copy()
        if crop.size == 0:
            return EyeDetectionResult(False, 0.0, None, None, reason="empty_eye_crop")
        confidence = min(1.0, max(0.0, float((candidate > 0).mean()) / 0.25))
        return EyeDetectionResult(
            True, confidence, (x0, y0, x1, y1), crop,
            eye="close_up", reason="close_up_anatomical_candidate",
        )
    except Exception as exc:
        return EyeDetectionResult(False, 0.0, None, None, reason=f"detector_unavailable:{type(exc).__name__}")
