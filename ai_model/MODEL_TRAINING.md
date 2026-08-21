# Phase 4 - Hb Regression Model

## Status

**COMPLETED WITH POOR BASELINE PERFORMANCE.** The verified Eyes-Defy-Anemia
release includes Hgb measurements in the India and Italy workbooks. A derived
195-subject labeled set was prepared, trained, evaluated, and saved.

The implementation is ready for the verified metadata table with columns:

```text
SUBJECT_ID,Hb
```

`SUBJECT_ID` must exactly match the image filename prefix and `Hb` must be the supplied clinical haemoglobin value in g/dL. The existing subject-level split is authoritative; the training script never creates an image-level split.

The final split is leakage-free: `train=136`, `val=29`, and `test=30`. One
subject was rejected because its ROI blur score was 6.84 below the calibrated
training threshold of 10.0.

## Model

The baseline is MobileNetV3-small with ImageNet weights disabled by default, adaptive global average pooling, a 128-unit Hardswish regression head, dropout, and one continuous output. It is lightweight for a research prototype and possible later mobile deployment. `--pretrained` can be used when network/model weights are available.

Training uses Adam (`1e-4`), MSE loss, batch size 8, seed 42, at most 30 epochs, and validation-loss early stopping with patience 5. The existing Phase 3 pipeline supplies the combined conjunctiva ROI, quality checks, CLAHE normalization, and 224x224 input. No augmentation is applied to validation or test data.

## Commands

After placing the verified labels file under `data/metadata/labels.csv` and generating `data/splits/split.json` from the real dataset:

```powershell
python -m src.data.validate_metadata data/metadata/labels.csv --raw-dir data/raw --report outputs/metadata_validation.json
python -m src.model.train --raw-dir data/raw --metadata-dir data/metadata
```

Training caches accepted ROI tensors under `data/processed/model_cache` by
default. This avoids repeating CV extraction on later runs. To rebuild the
cache, provide a different directory or remove the cache directory; cache
keys include subject paths, input size, normalization, and quality settings.

Training automatically repeats metadata validation when an accepted metadata
file is present and stops before loading labels if validation fails.

The best validation checkpoint is written to `models/hb_regressor_best.pt`; metrics and plots are written under `results/`.

Inference:

```powershell
python -m src.model.predict --image data/raw/<SUBJECT_ID>.jpg --mask data/raw/<SUBJECT_ID>_forniceal_palpebral.png --model models/hb_regressor_best.pt --subject-id <SUBJECT_ID>
```

For GPU inference, append `--device cuda`. See
`docs/BACKEND_INTEGRATION.md` for integrating the checkpoint into another
system without changing the preprocessing/model contract.

The inference response contains quality status and, only for an accepted image and a real checkpoint, `estimated_hb_g_dl`.

## Actual Results

| Split | MAE | RMSE | R2 |
|---|---:|---:|---:|
| Train | 1.2952 | 1.6315 | 0.5185 |
| Validation | 1.9387 | 2.5549 | -0.0585 |
| Test | 2.0454 | 2.5106 | -0.3272 |

The mean-training-Hb test baseline produced MAE=1.9324, RMSE=2.2017,
R2=-0.0207. The pretrained CNN improved substantially over the scratch CNN,
but remains slightly worse than the mean-Hb baseline.

An additional frozen-backbone plus target-normalization experiment produced
validation MAE=2.1528 and test MAE=1.9166. It was not promoted because its
validation performance was worse than the promoted model's validation MAE of
1.9387; selecting it from the test result would leak test information.

## Error analysis

The generated `results/error_analysis.json` and
`results/error_analysis_samples.csv` show a strong country difference. Across
all accepted subjects, India has MAE=1.0171 and R2=0.5325, while Italy has
MAE=1.9683 and R2=-0.2893. Several of the largest residuals are Italian
high-Hb subjects and are underpredicted. This points to domain/color or
acquisition differences as the next improvement target, not a reason to tune
on the test set.

## Model smoke demo

To demonstrate the existing CV pipeline feeding the regression architecture
without inventing Hb labels:

```powershell
python -m src.model.demo
```

This uses an accepted synthetic ROI and reports an `untrained_forward_output`.
That number is a tensor smoke value, not an Hb estimate.

## Medical limitation

This is a prototype for non-invasive anaemia screening research. It is not a medical diagnosis, a replacement for a blood test, clinically validated, or guaranteed to provide accurate Hb values.
