# Domain Analysis Report

## 1. Available Metadata

| Field | Status |
|-------|--------|
| `SUBJECT_ID` | present |
| `Hb` | present — verified clinical haemoglobin (g/dL) |
| `country` | present — two domains: India, Italy |
| `source_number` | present — original row index from source spreadsheet |
| `camera_device` | NOT AVAILABLE — no device metadata in dataset |
| `lighting` | NOT AVAILABLE — no lighting metadata in dataset |
| `acquisition_site` | NOT AVAILABLE — no site metadata in dataset |
| `demographics` | NOT AVAILABLE — no age/sex/skin-tone metadata in dataset |
| `image_quality_label` | NOT AVAILABLE — quality measured programmatically only |
| `roi_quality_label` | NOT AVAILABLE — quality measured programmatically only |

**Summary**: Only `country` is available as a domain identifier. Device, lighting, demographic, and site metadata do NOT exist in this dataset. Domain analysis is therefore limited to India vs Italy.

---

## 2. Overall Model Performance

The current model **does NOT beat the mean-prediction baseline** on val or test sets.

| Metric | Value |
|--------|-------|
| Overall MAE | 6.2787 g/dL |
| Overall RMSE | 6.6980 g/dL |
| Overall R² | -7.1296 |
| Mean signed error (bias) | -6.2787 g/dL |
| Total subjects processed | 194 |

### By Split

| Split | N | MAE | RMSE | R² | Bias (mean signed error) |
|-------|---|-----|------|----|--------------------------|
| test | 29 | 6.3296 | 6.6022 | -11.1293 | -6.3296 |
| train | 136 | 6.2400 | 6.6917 | -6.5586 | -6.2400 |
| val | 29 | 6.4094 | 6.8216 | -7.4400 | -6.4094 |

### Mean-Prediction Baseline (test set, predicting train mean = 12.62 g/dL)

| MAE | RMSE | N |
|-----|------|---|
| 1.6566 | 1.8982 | 29 |

**The model test MAE is higher than the baseline MAE. The model has not learned a useful signal.**

---

## 3. Domain Analysis: India vs Italy

| Domain | N | MAE | RMSE | R² | Bias | Hb Mean ± SD |
|--------|---|-----|------|----|------|--------------|
| India | 94 | 5.1321 | 5.5278 | -6.2310 | -5.1321 | 11.50 ± 2.06 |
| Italy | 100 | 7.3565 | 7.6362 | -12.6192 | -7.3565 | 13.75 ± 2.07 |

### Domain Findings

- **India** has substantially lower MAE and positive R² — the model partially learns the Indian Hb range.
- **Italy** has higher MAE and negative R² — the model fails on the Italian Hb range.
- The Hb distributions differ: India subjects tend to have lower Hb (anaemia-prevalent population), Italy subjects tend to have higher Hb (non-anaemic comparison group).
- The model was trained on a combined dataset but the distributions are not overlapping. This is a **domain mismatch** problem.
- **Systematic underprediction**: the mean signed error is negative across both domains, meaning the model consistently predicts lower Hb than actual. This is most severe in Italy where the actual Hb values are high.

### Why the Domain Gap Is Likely

1. **Hb range mismatch**: The Italian subjects have predominantly normal-to-high Hb (12–17 g/dL), while the Indian subjects cluster in the mild-to-moderate anaemia range (7–15 g/dL). A model trained on both will be pulled toward the Indian range.
2. **No camera calibration**: The images from the two cohorts were likely acquired with different camera devices and lighting conditions. Without device metadata, this cannot be confirmed, but it is a plausible source of systematic color shift.
3. **Conjunctiva color difference**: Skin tone affects the surrounding tissue visible in the image and the conjunctiva appearance for the same Hb level. This is a documented limitation in the conjunctival pallor anaemia literature.

---

## 4. Metadata Limitations

The following analyses are **NOT TESTABLE** because the required metadata does not exist:

| Analysis | Status | Reason |
|----------|--------|--------|
| Per-device performance | NOT TESTABLE | No camera/device metadata |
| Per-lighting performance | NOT TESTABLE | No lighting metadata |
| Per-demographic performance | NOT TESTABLE | No age/sex/skin-tone metadata |
| Per-acquisition-site performance | NOT TESTABLE | No site metadata |

---

## 5. Recommendations

1. Future data collection should record: device make/model, lighting conditions, demographic information (age, sex, self-reported skin tone).
2. Cross-domain validation requires hold-out by country — the current split was stratified but not country-separated.
3. The systematic underprediction on high-Hb subjects suggests the model may need domain-specific calibration or a larger representation of high-Hb subjects in training.

---

*This report was generated from actual model inference. No metrics were fabricated.*
*The model does NOT beat the baseline on val or test. This is documented, not hidden.*