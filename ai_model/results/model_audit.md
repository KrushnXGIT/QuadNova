# Model audit: current Hb regression system

## Scope

This audit documents the current implementation as it exists in the repository before any additional optimization work. The purpose is to establish the current architecture, preprocessing path, evaluation setup, and known limitations using actual code and actual project outputs.

This is not a success report. The current promoted model does not outperform the mean-Hb baseline and should therefore be treated as a research prototype rather than a validated clinical model.

## 1. Current model architecture

The active model is a MobileNetV3-small regression network defined in `src/model/model.py`.

Current architecture:
- Backbone: `torchvision.models.mobilenet_v3_small`
- Pretrained weights: enabled only when `pretrained=True`
- Feature extractor: `backbone.features`
- Pooling: `nn.AdaptiveAvgPool2d(1)`
- Regression head:
  - Flatten
  - Linear(576, 128)
  - Hardswish
  - Dropout(0.2)
  - Linear(128, 1)
- Output: scalar Hb prediction per image, shaped as `(N,)`

Key file:
- `src/model/model.py`

Model summary:
- lightweight CNN suitable for prototype / future mobile deployment
- not a medical diagnostic system
- no claim of clinical validity is made by the project

## 2. Current input size and data contract

Configured in `src/model/config.py`:
- `INPUT_SIZE = (224, 224)`
- `BATCH_SIZE = 8`
- `LEARNING_RATE = 1e-4`
- `MAX_EPOCHS = 30`
- `PATIENCE = 5`
- `RANDOM_SEED = 42`

The training pipeline processes ROI tensors produced by the CV pipeline:
- processed ROI is resized or extracted to `224x224`
- ROI tensor is passed as `(C, H, W)` for training
- model input is standard RGB ROI image with a combined conjunctiva mask

## 3. Current preprocessing pipeline

The active system preprocesses images in the CV pipeline:
- `src/vision/pipeline.py`
- `src/vision/roi.py`
- `src/vision/quality.py`
- `src/vision/color_normalization.py`

Pipeline stages:
1. Load raw photo and apply EXIF orientation correction
2. Raw image quality assessment
3. Conjunctiva ROI extraction using the mask files
4. ROI quality assessment
5. Color / illumination normalization
6. Resize to model input size
7. Feed ROI tensor into Hb regressor

Current normalization choice:
- default method: `clahe`
- configured in `src/model/config.py` as `NORM_METHOD = "clahe"`

Current training override:
- `QUALITY_OVERRIDES = {"blur_threshold": 10.0}`
- This override was set to keep more real-data subjects for training after dataset-specific quality calibration; it is a model-training specific override and not a general medical threshold claim.

## 4. Current ROI method

The ROI extraction is mask-guided and uses the combined conjunctiva mask preferred by the pipeline:
- `forniceal_palpebral` is preferred
- fallback to `forniceal` and `palpebral` if needed

Implementation:
- `src/vision/roi.py`
- `extract_conjunctiva_roi(...)`
- `extract_best_roi(...)`

Important details:
- The ROI uses the alpha mask to determine valid pixels
- Transparent pixels are filled with the mean RGB value of the valid ROI pixels
- This avoids a simple black background artifact
- The pipeline keeps the raw image + mask pair as the primary contract

## 5. Current image quality assessment

Image and ROI quality checks are implemented in `src/vision/quality.py`.

Checks include:
- minimum dimension
- blur via Laplacian variance
- darkness threshold (`mean_L` lower bound)
- brightness threshold (`mean_L` upper bound)
- ROI coverage fraction check

Important caveat:
- These thresholds are heuristic, not clinically validated
- They are guard rails to reject unusable images, not medical certainty metrics

## 6. Current augmentation strategy

Current training does not use meaningful augmentation for the final model path.

Evidence:
- `src/model/train.py` builds a `TensorDataset` from accepted ROI tensors
- no augmentation transforms are applied in the training loop
- validation and test data are not augmented for model selection or evaluation

This is a deliberate minimal baseline, but it also means the model currently has little explicit robustness augmentation.

## 7. Current train / validation / test split

The project uses subject-level splitting to prevent leakage.

Evidence:
- `src/data/splitting.py`
- `assert_no_overlap(...)` rejects any subject appearing in multiple splits

Current split counts from the real labeled dataset:
- train: 136
- validation: 29
- test: 30

The public decision rule is:
- train is for optimization
- validation is for model selection
- test is for final evaluation only

This rule was followed for the promoted checkpoint selection process.

## 8. Current loss and optimizer

From `src/model/train.py`:
- loss: `nn.MSELoss()`
- optimizer: `torch.optim.Adam`
- learning rate: `1e-4`
- early stopping: validation-loss patience = 5
- max epochs: 30

This is a standard low-risk baseline for a small regression prototype.

## 9. Current learning-rate strategy

The active configuration is a fixed learning rate:
- `LEARNING_RATE = 1e-4`

No advanced scheduler is implemented in the current production model path.

This is a simple and reproducible baseline, but it is not an optimized curriculum or schedule.

## 10. Current uncertainty implementation

The model includes uncertainty output in `src/model/predict.py`.

Current implementation:
- Monte Carlo-style predictive sampling with dropout enabled during inference pass
- returns mean prediction and standard deviation across samples
- also returns 95% interval estimate

Current behavior:
- `estimated_hb_g_dl`
- `hb_std_g_dl`
- `confidence_interval_95`
- `mc_samples`

Important caveat:
- This is not a clinically validated confidence metric
- Uncertainty quality is still a research question, not a proven medical safety layer

## 11. Current inference pipeline

Inference flow:
1. `src.model.predict.predict(...)`
2. run `process_subject(...)` on raw image + mask
3. reject if CV quality gate fails
4. load checkpoint
5. run the model on extracted ROI tensor
6. transform output using target normalization values if present
7. return prediction + uncertainty + quality report

Current code path:
- `src/model/predict.py`

This is reproducible and structured, but the quality and uncertainty outputs remain heuristic and should be treated as prototype evidence only.

## 12. Current tests

Automated tests are in `tests/`.

Current validated suite:
- 57 passed
- 14 subtests passed

Areas covered:
- model output shape
- regression metric calculations
- subject leakage rejection
- checkpoint reload
- missing-label training block
- synthetic CV pipeline validation
- inference smoke tests

These tests validate code correctness and pipeline behavior, but they do not validate clinical accuracy or robustness under real-world clinical conditions.

## 13. Dataset composition and available metadata

The verified dataset metadata includes columns in `data/metadata/labels.csv`:
- `SUBJECT_ID`
- `Hb`
- `country`
- `source_number`

The project therefore has country metadata for the labeled subjects.

This is useful for domain analysis and subgroup evaluation.

Metadata does not currently show a reliable device or camera model field at the project level, so true cross-device validation is limited unless additional metadata is supplied.

## 14. Country/domain signal already observed

The project contains a documented country difference in the error analysis:
- India: better performance
- Italy: worse performance, especially for high-Hb subjects

This is a major clue that the underperformance is not purely a model-capacity issue and may be related to domain, lighting, color, and/or acquisition differences.

## 15. Known project performance

Current metrics from `results/metrics.json`:
- Train MAE: 1.2952
- Validation MAE: 1.9387
- Test MAE: 2.0454
- Baseline MAE: 1.9324
- Test R²: -0.3272

Current status:
- the model does not outperform the mean-Hb baseline
- the model is therefore not a validated improvement over baseline on the current dataset
- the system remains a research prototype with known limitations

## 16. Key limitations

The current pipeline and model face several known issues:
- country/domain mismatch
- possible acquisition / illumination differences
- ROI quality and blur threshold sensitivity
- color and lighting normalization limitations
- lack of fully validated cross-device robustness
- no clear clinical calibration or uncertainty validation
- current model performance is below baseline

## 17. Recommended next investigation order

The highest value next steps are:
1. Domain analysis by country / site / acquisition characteristics
2. ROI quality analysis and correlation with error
3. Image-quality gate review and pre-inference filtering
4. Normalization comparison under identical split conditions
5. Robustness tests under brightness / contrast / color shifts
6. Model-quality experiments using a documented experiment matrix
7. Cross-validation for stability assessment
8. Uncertainty calibration and low-confidence decision logic

## 18. Conclusion

The current implementation is a valid codebase and pipeline baseline, but it is not a successful Hb regression model by the project’s own evaluation standard. It is best described as a prototype that still requires serious data-domain investigation and model improvement work before it can be considered a better-than-baseline anaemia screening system.

The most important fact is not that the code works; it is that the current model fails to beat the baseline and therefore must be improved or documented honestly rather than presented as a success.
