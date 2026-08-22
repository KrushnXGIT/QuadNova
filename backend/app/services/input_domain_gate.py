"""
input_domain_gate.py
====================
THE SINGLE MANDATORY INFERENCE FIREWALL between image upload and the Hb model.

WHY THIS EXISTS (root-cause fix)
--------------------------------
Two proven failure paths allowed UNRELATED images to reach the Hb regressor:

  1. AUTO-MASK PATH (the shipping Flutter app path): the classical red/pink
     chroma detector accepted ANY reddish blob near ANY dark region (a red mug
     beside a shadow, lips near the dark mouth line, ...). The tight bbox crop
     of such a blob passed the downstream quality gates, and the Hb model ran
     on those unrelated pixels -> fabricated Hb report for a random photo.
     MEASURED: unrelated "room photo + small red patch" returned
     estimated_hb_g_dl = 6.34 through predict_upload(image only).

  2. CLIENT-SUPPLIED MASK BYPASS: when a client sent `image` + `mask`, the
     server only checked that SOME plausible tissue existed somewhere in the
     image and then extracted the ROI using the RAW CLIENT MASK verbatim.
     An attacker could send an unrelated photo with one small red patch plus
     a FULL-FRAME mask -> Hb prediction on the entire unrelated image.
     MEASURED: full-frame-mask attack returned estimated_hb_g_dl = 6.34.

CONTRACT (fail-closed)
----------------------
    result = validate_conjunctiva_input(image_bytes, mask_bytes=None)

    if result.valid:
        # ONLY the mask carried by this result may reach the predictor.
        run_hb_model(validated_mask=result.validated_mask_png)
    else:
        reject(result.status, result.error)  # NO prediction, NO fallback

Level A - ANATOMICAL/DOMAIN validation:
    An independent server-side conjunctiva-candidate detection must succeed on
    THIS image (chroma signature + morphology + coverage sanity bounds + local
    dark eye-context). A client-supplied mask is NOT proof of anatomy; it is
    trusted ONLY when it substantially overlaps the independently-detected
    region (measured locally: real annotated masks overlap >= 0.99;
    full-frame attacks <= ~0.31; threshold 0.60 separates them with margin).

Level B - ROI QUALITY validation:
    The pixels inside the validated ROI must pass the existing ROI quality
    checks (sharpness, exposure, resolution, usable coverage) BEFORE any
    inference is allowed.

All thresholds are engineering heuristics calibrated against the local
dataset (see ai_model/validation/) - NOT clinically validated cut-offs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import cv2
import numpy as np

from .mask_generator import (
    _decode_exif_rgb as decode_exif_rgb,
    _detect_conjunctiva_alpha as detect_conjunctiva_alpha,
)
from .eye_detector import detect_eye
from .debug_visualization import write_debug_artifacts

logger = logging.getLogger(__name__)

# ── Firewall thresholds (documented heuristics, see module docstring) ───────
# Fraction of a client-supplied mask's pixels that must lie INSIDE the
# independently-detected conjunctiva region for that mask to be trusted.
OVERLAP_MIN_FRACTION = 0.60

# ── LEVEL A v2: conjunctiva TISSUE-EVIDENCE thresholds ──────────────────────
# Derived by MEASUREMENT on the local dataset (see ai_model/validation/):
#   positives = 167 real conjunctiva images where the detector fired
#     pink_frac >= 0.505 | mean_saturation <= 120.05 | mean_value >= 123.37
#     | luma_std >= 20.10
#   adversarial negatives that pass chroma detection (red patch on furniture,
#   red food/objects, lips+dark mouth, normal eye canthus+pupil) violate ALL
#   FOUR simultaneously (measured exploit example: pink 0.02, S 129.6,
#   V 92.3, std 7.6). Thresholds sit between the two populations with margin.
# These are engineering heuristics calibrated on local data, NOT clinical cut-offs.
TISSUE_MIN_PINK_FRACTION = 0.35   # fraction of ROI pixels that are bright pink/red
TISSUE_MAX_MEAN_SATURATION = 125.0  # conjunctiva is MODERATELY saturated
TISSUE_MIN_MEAN_VALUE = 110.0     # mucosa is well-lit / bright
TISSUE_MIN_LUMA_STD = 14.0        # living tissue has shading structure, not flat


def assess_tissue_evidence(rgb: np.ndarray, alpha: np.ndarray) -> dict:
    """
    LEVEL A v2 - verify the detected candidate actually looks like
    conjunctiva tissue (bright, moderately-saturated, textured pink),
    rather than an arbitrary red/orange object near a dark region.

    Returns {"passed": bool, "metrics": {...}, "reasons": [...]}.
    """
    m = alpha > 0
    n = int(m.sum())
    if n == 0:
        return {"passed": False, "metrics": {}, "reasons": ["empty_region"]}

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h = hsv[..., 0][m].astype(np.float32)
    s = hsv[..., 1][m].astype(np.float32)
    v = hsv[..., 2][m].astype(np.float32)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)[m].astype(np.float32)

    hue_dist = np.minimum(h, np.abs(h - 180.0))  # wraparound distance to red hue
    pink_frac = float(((hue_dist <= 25.0) & (v >= 100.0)).sum() / n)
    mean_s = float(s.mean())
    mean_v = float(v.mean())
    luma_std = float(gray.std())

    reasons: list[str] = []
    if pink_frac < TISSUE_MIN_PINK_FRACTION:
        reasons.append(f"not_pink_enough(pink_frac={pink_frac:.3f})")
    if mean_s > TISSUE_MAX_MEAN_SATURATION:
        reasons.append(f"over_saturated(mean_s={mean_s:.1f})")
    if mean_v < TISSUE_MIN_MEAN_VALUE:
        reasons.append(f"too_dark(mean_v={mean_v:.1f})")
    if luma_std < TISSUE_MIN_LUMA_STD:
        reasons.append(f"flat_texture(luma_std={luma_std:.1f})")

    return {
        "passed": not reasons,
        "metrics": {
            "pink_fraction": round(pink_frac, 4),
            "mean_saturation": round(mean_s, 2),
            "mean_value": round(mean_v, 2),
            "luma_std": round(luma_std, 2),
        },
        "reasons": reasons,
    }



@dataclass(frozen=True)
class DomainGateResult:
    """Structured outcome of the mandatory input-domain firewall."""

    valid: bool
    status: str                                  # "VALIDATED" | rejection status
    error: Optional[dict] = None                 # {"code","message","retryable"}
    validated_mask_png: Optional[bytes] = None   # server-authoritative ROI mask
    validation: dict = field(default_factory=dict)

    @property
    def error_code(self) -> Optional[str]:
        return (self.error or {}).get("code")


def _reject(
    status: str,
    code: str,
    message: str,
    validation: dict,
    retryable: bool = True,
) -> DomainGateResult:
    logger.info("DOMAIN GATE REJECT | status=%s | code=%s", status, code)
    return DomainGateResult(
        valid=False,
        status=status,
        error={"code": code, "message": message, "retryable": retryable},
        validated_mask_png=None,
        validation=validation,
    )


def _load_client_alpha(mask_bytes: bytes) -> Optional[np.ndarray]:
    """Decode uploaded mask bytes to an alpha channel array (or None)."""
    try:
        decoded = cv2.imdecode(
            np.frombuffer(mask_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED
        )
    except Exception:
        return None
    if decoded is None:
        return None
    if decoded.ndim == 2:
        return decoded
    if decoded.ndim == 3 and decoded.shape[2] == 4:
        return decoded[:, :, 3]
    return None


def _encode_rgba_mask_png(rgb: np.ndarray, alpha: np.ndarray) -> Optional[bytes]:
    """Encode RGB + alpha into an RGBA PNG (the predictor's mask format)."""
    try:
        rgba = np.dstack([rgb, alpha])
        bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        ok, buf = cv2.imencode(".png", bgra)
        return buf.tobytes() if ok else None
    except Exception:
        logger.warning("Domain gate: RGBA mask encoding failed", exc_info=True)
        return None



def _roi_quality_check(rgb: np.ndarray, alpha_full_res: np.ndarray) -> tuple:
    """
    LEVEL B - ROI quality validation on the actual validated ROI pixels.

    Uses the existing pipeline ROI-quality checks so the firewall cannot
    drift from what the predictor enforces later. Returns (passed, evidence).
    """
    # Lazy import: ai_model root is added to sys.path by AIService.initialize()
    # before any request is served. Fail CLOSED if unavailable. The gate MUST
    # use the SAME calibrated thresholds as the predictor's own pipeline
    # (QUALITY_OVERRIDES) so it cannot drift from what inference enforces.
    try:
        import sys
        from pathlib import Path
        ai_model_root = Path(__file__).resolve().parents[3] / "ai_model"
        if str(ai_model_root) not in sys.path:
            sys.path.insert(0, str(ai_model_root))
        from src.vision.quality import check_roi_quality  # type: ignore
        from src.model.config import QUALITY_OVERRIDES  # type: ignore
    except Exception:
        logger.error("Domain gate: cannot import ROI quality checks", exc_info=True)
        return False, {"quality_status": "UNAVAILABLE", "quality_reason": "unavailable"}

    ys, xs = np.where(alpha_full_res > 0)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    roi_rgb = rgb[y0:y1, x0:x1]
    coverage_fraction = float(np.count_nonzero(alpha_full_res > 0)) / alpha_full_res.size

    allowed = (
        "blur_threshold", "dark_threshold", "bright_threshold",
        "min_dimension", "min_roi_coverage",
    )
    overrides = {k: v for k, v in (QUALITY_OVERRIDES or {}).items() if k in allowed}
    quality = check_roi_quality(roi_rgb, coverage_fraction, **overrides)
    evidence = {
        "quality_status": "ACCEPTED" if quality.passed else "REJECTED",
        "quality_reason": quality.reason,
        "metrics": {
            k: (float(v) if isinstance(v, (int, float)) else v)
            for k, v in quality.metrics.items()
        },
        "checks": {k: bool(v) for k, v in quality.checks.items()},
        "roi_bbox": [y0, y1, x0, x1],
    }
    return bool(quality.passed), evidence


def validate_conjunctiva_input(
    image_bytes: bytes,
    mask_bytes: Optional[bytes] = None,
) -> DomainGateResult:
    """
    THE mandatory pre-inference checkpoint. Every /predict request MUST pass
    through this function; the Hb predictor must only ever receive the mask
    attached to a VALID result.

    Args:
        image_bytes: raw uploaded image bytes.
        mask_bytes:  optional client-supplied ROI mask. NEVER trusted blindly -
                     must overlap the independently-detected region (Level A).

    Returns:
        DomainGateResult. On success, validated_mask_png carries the ONLY mask
        that may be used for ROI extraction and Hb inference.
    """
    validation: dict = {
        "domain": None,
        "mask_source": None,
        "roi_quality": None,
        "image": {"height": None, "width": None, "orientation": "exif_normalized"},
    }

    # Step 0: decode.
    rgb = decode_exif_rgb(image_bytes)
    if rgb is None:
        return _reject(
            "INVALID_INPUT", "IMAGE_UNREADABLE",
            "The image could not be decoded.", validation, retryable=False,
        )
    validation["image"] = {
        "height": int(rgb.shape[0]),
        "width": int(rgb.shape[1]),
        "orientation": "exif_normalized",
    }
    logger.info("IMAGE SIZE=%sx%s | ORIENTATION=EXIF_NORMALIZED", rgb.shape[1], rgb.shape[0])

    # Step 1: genuine eye localization. Face presence alone is insufficient.
    eye_result = detect_eye(rgb)
    validation["eye_detection"] = {
        "detected": eye_result.detected,
        "confidence": round(eye_result.confidence, 4),
        "bbox": list(eye_result.bbox) if eye_result.bbox else None,
        "eye": eye_result.eye,
        "reason": eye_result.reason,
    }
    if not eye_result.detected or eye_result.eye_crop is None:
        logger.info("EYE DETECTION=FAIL | reason=%s | HB MODEL=BLOCKED", eye_result.reason)
        return _reject(
            "EYE_NOT_DETECTED", "EYE_NOT_DETECTED",
            "Eye not detected. Please capture a clear image of your eye.",
            validation,
        )
    logger.info(
        "EYE DETECTION=PASS | confidence=%.4f | bbox=%s | crop=%sx%s",
        eye_result.confidence, eye_result.bbox,
        eye_result.eye_crop.shape[1], eye_result.eye_crop.shape[0],
    )

    # Conjunctiva detection is explicitly scoped to the detected eye crop.
    detected_crop = detect_conjunctiva_alpha(eye_result.eye_crop)
    detected = np.zeros(rgb.shape[:2], dtype=np.uint8)
    x0, y0, x1, y1 = eye_result.bbox  # type: ignore[misc]
    if detected_crop is not None:
        detected[y0:y1, x0:x1] = cv2.resize(
            detected_crop, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST
        )
    validation["conjunctiva_detection"] = {
        "detected": detected_crop is not None,
        "bbox": [x0, y0, x1, y1] if detected_crop is not None else None,
    }
    logger.info(
        "CONJUNCTIVA DETECTION=%s | bbox=%s",
        "PASS" if detected_crop is not None else "FAIL",
        validation["conjunctiva_detection"]["bbox"],
    )
    if detected_crop is None:
        validation["domain"] = "INVALID"
        return _reject(
            "CONJUNCTIVA_NOT_DETECTED", "CONJUNCTIVA_NOT_DETECTED",
            "No valid conjunctiva region was detected.", validation,
        )
    tissue = assess_tissue_evidence(rgb, detected)
    validation["domain"] = "VALID" if tissue["passed"] else "INVALID"
    validation["tissue_evidence"] = tissue
    if not tissue["passed"]:
        logger.info(
            "DOMAIN GATE | DOMAIN RESULT=INVALID | tissue=%s",
            ",".join(tissue["reasons"]),
        )
        return _reject(
            "INVALID_INPUT", "CONJUNCTIVA_NOT_DETECTED",
            "No valid conjunctiva region was detected.", validation,
        )
    logger.info(
        "CONJUNCTIVA CONFIDENCE=evidence | metrics=%s | ROI CREATED=%s",
        tissue["metrics"], bool(np.any(detected > 0)),
    )
    write_debug_artifacts(
        rgb, eye_result.bbox, eye_result.eye_crop, detected, validation,
    )


    # Step 2: decide which mask may be used.
    if mask_bytes is not None:
        client_alpha = _load_client_alpha(mask_bytes)
        if client_alpha is None or not np.count_nonzero(client_alpha):
            return _reject(
                "INVALID_INPUT", "ROI_MASK_INVALID",
                "The supplied ROI mask could not be used.",
                validation, retryable=False,
            )
        # Client masks may arrive at a different native resolution; align to
        # the raw frame the same way the pipeline aligns dataset masks.
        client_full = cv2.resize(
            client_alpha, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR
        )
        inter = np.logical_and(client_full > 0, detected > 0).sum()
        denom = max(int(np.count_nonzero(client_full > 0)), 1)
        overlap_fraction = float(inter) / float(denom)
        validation["mask_source"] = "client"
        validation["mask_overlap_fraction"] = round(overlap_fraction, 4)
        if overlap_fraction < OVERLAP_MIN_FRACTION:
            logger.info(
                "DOMAIN GATE | client mask rejected: overlap=%.4f < %.2f",
                overlap_fraction, OVERLAP_MIN_FRACTION,
            )
            return _reject(
                "CONJUNCTIVA_NOT_DETECTED", "CONJUNCTIVA_NOT_DETECTED",
                "No valid conjunctiva region was detected.", validation,
            )
        validated_mask_png: Optional[bytes] = mask_bytes
        validated_alpha = client_full
    else:
        validation["mask_source"] = "server_detected"
        validated_mask_png = _encode_rgba_mask_png(rgb, detected)
        if validated_mask_png is None:
            return _reject(
                "INVALID_INPUT", "ROI_MASK_ENCODING_FAILED",
                "The detected region could not be prepared for analysis.",
                validation, retryable=False,
            )
        validated_alpha = detected

    # Step 3: LEVEL B - ROI quality validation on the validated ROI pixels.
    passed, roi_evidence = _roi_quality_check(rgb, validated_alpha)
    validation["roi_quality"] = roi_evidence
    logger.info(
        "DOMAIN GATE | ROI RESULT=VALID QUALITY RESULT=%s",
        roi_evidence.get("quality_status"),
    )
    logger.info(
        "ROI QUALITY=%s | score=%s | blur=%s | brightness=%s | contrast=%s",
        roi_evidence.get("quality_status"),
        roi_evidence.get("metrics", {}).get("roi_quality_score", "heuristic"),
        roi_evidence.get("metrics", {}).get("blur_score"),
        roi_evidence.get("metrics", {}).get("mean_luminance"),
        roi_evidence.get("metrics", {}).get("std_luminance"),
    )
    if not passed:
        return _reject(
            "ROI_QUALITY_FAILED", "ROI_QUALITY_FAILED",
            "The detected region is not usable for screening "
            "(sharpness/exposure/resolution).",
            validation,
        )

    logger.info("DOMAIN GATE | VALIDATION COMPLETE => VALID")
    return DomainGateResult(
        valid=True,
        status="VALIDATED",
        error=None,
        validated_mask_png=validated_mask_png,
        validation=validation,
    )


def build_rejection_payload(result: DomainGateResult) -> dict:
    """Build the API rejection payload from a failed gate result.

    Guarantees: success=false, structured error block, validation evidence,
    and NO prediction fields of any kind (no Hb, no CI, no recommendation).
    """
    return {
        "success": False,
        "status": result.status,
        "error": dict(result.error or {}),
        "validation": result.validation,
        "data": {
            "retry": bool((result.error or {}).get("retryable", True)),
            "message": (result.error or {}).get("message", ""),
        },
    }

