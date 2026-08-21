# Model Card: Anaemia Hb Screening Prototype

## Model name
MobileNetV3-small Hb regressor

## Architecture
- Backbone: MobileNetV3-small
- Head: adaptive global average pooling + 128-unit Hardswish regression head + 1-value output
- Input size: 224x224 RGB
- Output: continuous Hb estimate in g/dL

## Purpose
This model is a prototype screening system to estimate haemoglobin from smartphone conjunctiva images. It is intended for research and screening support only.

## Input
- RGB image of the conjunctiva region
- Mask or ROI path supplied by the project pipeline
- Quality checks are applied before inference

## Output
- `estimated_hb_g_dl`
- `hb_std_g_dl`
- `confidence_interval_95`
- `confidence_status`
- `image_quality` summary
- `roi` summary
- `recommendation`
- `model` metadata

## Training data
The current model was trained on the verified project dataset with subject-level split and real Hb labels. The project record shows a leakage-free split with 136 train, 29 validation, and 30 test subjects.

## Known dataset limitations
- Country/domain differences are present
- The current dataset is small and not broad enough to establish clinical validity
- Domain shift between India and Italy is a likely source of performance limitation
- ROI/quality thresholds are heuristic and data dependent

## Current metrics
- Train MAE: 6.2400
- Validation MAE: 6.4094
- Test MAE: 6.3296
- Baseline MAE: 1.6566
- R²: -11.1293

## Baseline metrics
Mean-Hb baseline on the same test split: MAE 1.6566, R² -0.0026.

## Uncertainty method
The prediction pipeline uses the existing Monte Carlo dropout-style uncertainty estimate from the current model implementation. This is engineering uncertainty, not clinically validated uncertainty.

## Confidence limitations
Confidence is only a conservative screening heuristic. The model uncertainty is not yet clinically calibrated and should be treated as experimental.

## Known domain limitations
- The model does not reliably beat the mean-Hb baseline
- Generalization may be poor across country or acquisition differences
- High-Hb subjects and some acquisition groups may be systematically underpredicted

## Known image-quality limitations
- Image quality gate is heuristic
- Blur, exposure, brightness and ROI coverage are used as technical filters, not clinical safety checks
- Low-quality images should trigger retake prompts

## Intended use
- Research prototype
- AI screening support only
- Internal validation and backend integration prototyping

## Not intended use
- Diagnosis of anaemia
- Blood-test replacement
- Treatment or clinical decision-making without confirmatory testing

## Clinical disclaimer
This model is not a clinical diagnostic device and has not been clinically validated. All estimates are provisional and should be confirmed with laboratory testing when a clinical decision is required.
