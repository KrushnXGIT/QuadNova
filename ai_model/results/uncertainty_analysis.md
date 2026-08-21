# Uncertainty Analysis Report

## Method

MC dropout inference with 25 forward passes per image.
The model's dropout layer remains active during inference (training mode).
Each forward pass produces a different output due to random dropout.
The mean of the MC samples is the prediction; the std is the uncertainty estimate.

**Limitation**: MC dropout approximates Bayesian uncertainty in the model weights. It does NOT capture aleatoric (data/measurement) uncertainty. On a small dataset, the resulting uncertainty estimates may be poorly calibrated.

---

## Results

### 95% Prediction Interval Coverage

A well-calibrated 95% CI should contain the true value in ~95% of cases.

| Split | N | Coverage |
|-------|---|----------|
| All | 194 | 0.3814 (38.1%) |
| Validation | 29 | 0.3448 (34.5%) |
| Test | 29 | 0.4483 (44.8%) |

⚠️ **Coverage far from 95%**: The prediction intervals are not well-calibrated. See calibration notes below.

### Uncertainty vs Error Correlation

Pearson correlation (all subjects): **-0.0868**
Pearson correlation (val only): **-0.2944**

The correlation between MC dropout uncertainty and prediction error is **weak**. Higher uncertainty does not reliably predict higher error on this dataset. This is a known limitation of MC dropout on small datasets with limited diversity.

---

## Calibration Summary

Calibration was derived from the **validation set (n=29)**.

| Tertile | Mean Absolute Error |
|---------|---------------------|
| Low uncertainty (≤0.6708) | 2.6083 g/dL |
| Medium uncertainty | 1.6633 g/dL |
| High uncertainty (>0.7591) | 1.9896 g/dL |

**Calibration monotonic**: NO (see notes)

### Calibration Notes

- CALIBRATION POOR: Higher uncertainty does NOT correspond to higher error on the validation set (low_err=2.6083, high_err=1.9896). MC dropout uncertainty is weakly calibrated on this dataset. Confidence thresholds should be interpreted with caution.

---

## Limitations

1. MC dropout uncertainty is a proxy, not a true Bayesian posterior.
2. The validation set has only ~29 subjects — threshold derivation is fragile.
3. Uncertainty estimates are not interpretable as probability of clinical significance.
4. The calibration should be re-evaluated with a larger dataset.

---

*Generated from actual MC dropout inference. No metrics were fabricated.*
*If calibration is poor, this is documented, not hidden.*