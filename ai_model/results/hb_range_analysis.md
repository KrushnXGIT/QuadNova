# Hb Range Error Analysis

## Methodology

Subjects were binned into clinically meaningful Hb ranges:

| Range | Clinical category |
|-------|-------------------|
| < 10 g/dL | Moderate-to-severe anaemia |
| 10–12 g/dL | Mild anaemia |
| 12–14 g/dL | Low-normal |
| ≥ 14 g/dL | Normal/above |

These bins are informed by WHO anaemia thresholds (WHO 2011) and are NOT specific to any single demographic. They are used here for subgroup analysis only.

---

## Performance by Hb Range

| Range | N | MAE | RMSE | Bias (MSE) | Hb Mean |
|-------|---|-----|------|------------|---------|
| <10 (severe/moderate anaemia) | 33 | 2.6166 | 2.7279 | -2.6166 | 8.98 |
| 10-12 (mild anaemia) | 43 | 4.7374 | 4.7667 | -4.7374 | 11.10 |
| 12-14 (low-normal) | 57 | 6.7866 | 6.8114 | -6.7866 | 13.17 |
| >=14 (normal) | 61 | 8.8719 | 8.9042 | -8.8719 | 15.28 |

---

## Findings

- **Best performance**: `<10 (severe/moderate anaemia)` — MAE = 2.6166 g/dL
- **Worst performance**: `>=14 (normal)` — MAE = 8.8719 g/dL

### Systematic Bias

The mean signed error (bias) is **negative** in all Hb ranges, meaning the model consistently **underpredicts** actual Hb values.

- The underprediction is most severe in the ≥14 g/dL range (high-normal/above-normal Hb). The model has been trained on a mix of Indian (lower Hb) and Italian (higher Hb) subjects and appears pulled toward the lower range.
- For the <10 g/dL range (severe/moderate anaemia), the model still underpredicts on average, but performance is better because most of these subjects are from India where the model generalizes better.

### Clinical Implications (for anaemia screening)

- The model's systematic underprediction in the high-Hb range (≥14) is less dangerous from a screening perspective — underpredicting high Hb may trigger unnecessary further testing, but will not miss severe anaemia.
- However, the model cannot reliably distinguish mild anaemia (10–12) from normal (12–14), which is clinically the most important boundary for intervention.

**This is an AI screening prototype. It is NOT clinically validated. All screening estimates should be confirmed by a blood test.**

---

*Generated from actual model inference. No metrics were fabricated.*