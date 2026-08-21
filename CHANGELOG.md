## AI model consolidation — 2026-08-22

- Consolidated the verified MITINDIA AI source, tests, results, scripts, and
  promoted `hb_regressor_best.pt` checkpoint under `ai_model/`.
- Preserved the original MITINDIA project, experiment checkpoints, and prior
  scaffold documents; nothing was deleted.
- Documented the actual predictor entry point and the conflicting metric sets
  that require provenance resolution before backend integration.

# Changelog

## FastAPI backend + existing AI model integration — 2026-08-22

- Integrated FastAPI with the existing `ai_model` source of truth through
  `backend/app/services/ai_service.py`.
- Real predictor entry point:
  `ai_model/src/inference/predictor.py::AnaemiaPredictor`.
- Real checkpoint path: `ai_model/models/hb_regressor_best.pt`; the checkpoint
  remains in `ai_model/` and is not copied into `backend/`.
- Removed stale placeholder backend model/preprocessing modules so the backend no
  longer duplicates ROI extraction, normalization, Hb regression, uncertainty, or
  confidence logic.
- Updated `/api/v1/model/status` to report actual readiness and model metadata.
- Updated `/api/v1/predict` to accept `image` plus optional `mask` and return the
  AI predictor's real JSON payload.
- Updated Flutter response parsing/display for `estimated_hb_g_dl`,
  `hb_std_g_dl`, `confidence_interval_95`, `confidence_status`, `image_quality`,
  and `ROI_FAILED`.
- Added `backend/README.md`, `backend/API_DOCUMENTATION.md`, and
  `END_TO_END_TEST.md`.
- Verified AI tests: `129 passed, 14 subtests passed`.
- Verified backend tests: `13 passed`.
- Verified real masked prediction returned `PREDICTION_COMPLETE` with actual Hb,
  uncertainty, confidence, image quality, ROI status, and model version.
- Known limitation: current Flutter camera sends only `image`; the current AI
  model requires an ROI `mask`, so phone-only prediction correctly returns
  `ROI_FAILED` until ROI mask generation/capture is added.

## Backend continuation — Image ingest hardening

- Reviewed FastAPI backend structure, safety contract, model adapter, validation,
  prediction flow, and tests.
- Hardened `backend/app/utils/validation.py` so upload decoding first uses Pillow
  with EXIF orientation handling, then falls back to OpenCV when Pillow fails.
  This directly addresses the sample dataset finding that some PNG files contain
  malformed ancillary chunks that break plain `PIL.Image.open()`.
- Added a backend regression test that simulates Pillow decode failure and confirms
  OpenCV fallback still returns an RGB `uint8` image without inventing predictions.
- Could not run backend tests in this environment because neither `python`, `py`,
  nor `pytest` is available on PATH.

## Phase 1 — Dataset Verification (sample-based)

- Added `src/data_analysis.py`: read-only, reproducible verifier for
  Eyes-Defy-Anemia-style image/mask folders (format, dimensions, EXIF, PNG CRC
  integrity, mask alpha statistics, raw-to-mask geometry, union-of-parts check).
- Added `DATASET_VERIFICATION_REPORT.md`: findings from a 6-file, 2-subject sample
  (this session had no access to the real repo or the full public datasets —
  see report §1 for scope).
- Added `DATASET_SCHEMA.md`: file naming convention and per-file schema, confirmed
  against the sample.
- Updated `HANDOFF.md`: Phase 1 marked partial/sample-only; feasibility = C
  (blocked on missing Hb metadata table, not on image quality).
- Confirmed defect: all sampled PNG masks have a corrupted `iCCP` chunk (bad CRC),
  breaking plain `PIL.Image.open()`; OpenCV loads them fine.
- Confirmed masks are EXIF-rotated + ~3.735x downscaled relative to the raw photo,
  not a direct-pixel crop.
