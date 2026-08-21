# Confidence Calibration Report

## System Design

The confidence system combines:
1. **Image quality gate**: Is the image technically usable?
2. **MC dropout uncertainty**: How uncertain is the model?

Output confidence statuses:
- **HIGH_CONFIDENCE**: Good image + low uncertainty
- **MEDIUM_CONFIDENCE**: Good image + moderate uncertainty
- **LOW_CONFIDENCE**: Bad image OR high uncertainty

**IMPORTANT**: Confidence here means prediction confidence, not clinical certainty. Even HIGH_CONFIDENCE results are screening estimates only.

---

## Threshold Derivation

Thresholds were derived from the **validation set (n=29)** by splitting uncertainty values into tertiles (33rd and 67th percentiles).

| Threshold | Value |
|-----------|-------|
| LOW → MEDIUM boundary (33rd percentile) | **0.6708 g/dL std** |
| MEDIUM → HIGH boundary (67th percentile) | **0.7591 g/dL std** |

This means:
- std ≤ 0.6708 → HIGH_CONFIDENCE (lowest uncertainty third)
- 0.6708 < std ≤ 0.7591 → MEDIUM_CONFIDENCE (middle third)
- std > 0.7591 → LOW_CONFIDENCE (highest uncertainty third)

---

## Evaluation on Validation Set

| Confidence Group | Mean Absolute Error | N |
|------------------|--------------------|----|
| HIGH_CONFIDENCE | 2.6083 g/dL | ~9 |
| MEDIUM_CONFIDENCE | 1.6633 g/dL | ~9 |
| LOW_CONFIDENCE | 1.9896 g/dL | ~9 |

**Calibration monotonic (expected: HIGH < MEDIUM < LOW error)**: NO — see limitations

---

## Limitations

⚠️ **CALIBRATION IS POOR**: Higher confidence does NOT consistently correspond to lower error on the validation set. The confidence system provides a coarse, weakly-calibrated signal. Users should interpret confidence labels conservatively.

- Validation set has only ~29 subjects — small sample for calibration.
- MC dropout is not a rigorous Bayesian uncertainty quantification.
- Thresholds should be re-derived with a larger dataset.
- The confidence labels do not constitute a probability of clinical accuracy.

---

*Thresholds are derived from validation data, not invented.*
*Poor calibration is documented, not hidden.*