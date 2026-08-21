# AI Model Consolidation Report

Date: 2026-08-22

## Source of truth

`MITINDIA/` was the source of truth for the AI implementation. It contains the
working CV pipeline, MobileNetV3-small regressor, predictor, uncertainty and
decision layers, checkpoint reload tests, and model documentation.

The previous `smartphone-anaemia-screening/ai_model/` contained only scaffolding
and compatibility-document placeholders. Those files were preserved under
`ai_model/docs/legacy_scaffold/` before the authoritative documentation was
copied in.

## Consolidated location

The authoritative implementation is now under `smartphone-anaemia-screening/ai_model/`:

- Source: `ai_model/src/`
- Predictor entry point: `ai_model/src/inference/predictor.py`
- Public predictor: `AnaemiaPredictor`
- Convenience package: `ai_model/predictor.py`, `ai_model/preprocessing.py`,
  `ai_model/decision.py`, and `ai_model/schemas.py`
- Model architecture: `ai_model/src/model/model.py`
- CV pipeline: `ai_model/src/vision/pipeline.py`
- ROI extraction: `ai_model/src/vision/roi.py`
- Quality gate: `ai_model/src/vision/quality_gate.py`
- Normalization: `ai_model/src/vision/color_normalization.py`
- Training: `ai_model/src/model/train.py`
- Uncertainty: `ai_model/src/model/confidence.py` and MC-dropout in the predictor
- Decision layer: `ai_model/src/model/decision.py`
- Promoted checkpoint: `ai_model/models/hb_regressor_best.pt`
- Calibration parameters: `ai_model/models/confidence_calibration_params.json`

Only the promoted checkpoint was copied. MITINDIA's two experiment checkpoints
remain in place and were not duplicated or deleted.

## Preserved files

- Existing Flutter project under `app/`
- Existing FastAPI backend under `backend/`
- Project-level data and dataset reports under `data/`
- Existing research `src/`, `models/`, `results/`, and `tests/` placeholders
- Original `MITINDIA/` project, unchanged and available for comparison/archive
- MITINDIA results and notebooks boundary where present

Training datasets and metadata were not copied into Flutter or duplicated into
the consolidated model tree.

## Documentation conflict

Two existing MITINDIA documents report different metric sets:

- `MODEL_TRAINING.md` and `docs/BACKEND_INTEGRATION.md` describe the promoted
  checkpoint as Train MAE 1.2952, Validation MAE 1.9387, Test MAE 2.0454,
  with test baseline MAE 1.9324.
- `MODEL_CARD.md` describes Train MAE 6.2400, Validation MAE 6.4094, Test MAE
  6.3296, with baseline MAE 1.6566.

Both records were preserved. This conflict must be resolved by checking the
checkpoint provenance before backend integration. No metric was changed or
presented as newly verified during restructuring.

## Test status

- AI suite: **129 tests passed, 14 subtests passed** from `ai_model/` using the
  consolidated checkpoint and installed CPU PyTorch runtime. A relative dataset
  path resolution defect found during testing was fixed in
  `ai_model/src/data/validate_metadata.py`.
- Flutter analysis: previously passed before this consolidation; rerun required.
- Flutter tests: existing splash widget test was previously failing because the
  brand is rendered as separate text spans; no test expectation was changed.
- Backend tests: previously 13 passed; rerun required.

## Archive decision

`MITINDIA/` must not yet be archived or removed. The consolidated tree has now
passed the AI suite, but the metric-document conflict and the existing Flutter
test failure remain. Archive only after those project-level issues are resolved
and the backend is integrated against the model contract.
