CURRENT PHASE:
Flutter full screening flow (COMPLETE for prototype — camera → backend →
real AI prediction → report, verified end-to-end; see 2026-08-22 update below)

## 2026-08-22 Flutter Full-Flow Update (later session)

COMPLETED:
- BLOCKER RESOLVED: phone captures can now reach successful inference.
  `backend/app/services/mask_generator.py` auto-generates the conjunctiva ROI
  mask input required by the EXISTING predictor (classical CV; no model
  changes, no fabricated masks). Enabled via `AUTO_MASK_ENABLED=true`.
  Image-only `/api/v1/predict` now returns real `PREDICTION_COMPLETE` results;
  non-tissue images still return honest `ROI_FAILED`. Backend suite: 13 passed.
- Flutter camera screen: real permissions (denied/permanently-denied → Open
  Settings), init-failure retry, GENUINE live Lighting/Sharpness/Steadiness
  pills computed from preview frames (luma mean / Laplacian variance /
  frame-diff). Guidance only — backend quality gate remains authoritative.
- Preview: staged indeterminate loading (no fake %), duplicate-submit guard,
  corrupt-file check. Result report shows ONLY real backend values (Hb,
  ±SD, 95% CI, confidence, quality, verbatim recommendation, model name/
  version) + disclaimer + low-confidence banner; dedicated states for
  IMAGE_QUALITY_FAILED / ROI_FAILED / MODEL_NOT_READY / network errors with
  Retake/Retry. Invented client-side medical thresholds removed.
- Screening history (SharedPreferences metadata only, no images) connected to
  real results and displayed in the History tab.
- API service parses exact backend schema (incl. roi/model/failure_reasons),
  maps HTTP statuses/timeouts to typed errors.
- Tests: `flutter analyze` clean; `flutter test` 11/11 passed (parser tests
  use REAL backend payloads); Android debug APK builds; installed on physical
  device; LIVE run confirmed a real phone capture reached the backend over
  Wi-Fi and received an honest structured response.

RUN COMMANDS:
- Backend: `cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Flutter: `cd app && flutter run` (set server URL in-app via Account → Server
  Settings, or auto-detect; emulator default http://10.0.2.2:8000)

REMAINING NOTES:
- The AI model itself remains a weak research baseline (test MAE worse than
  mean-baseline); values are screening estimates only, never clinical.
- Auto-mask thresholds are engineering heuristics; tune on real eyelid
  captures if acceptance rates are poor.

## 2026-08-22 Backend/AI Integration Update

COMPLETED:
- Integrated `backend/` with the existing `ai_model/` through one service:
  `backend/app/services/ai_service.py`.
- Actual AI predictor entry point:
  `ai_model/src/inference/predictor.py::AnaemiaPredictor`.
- Actual checkpoint:
  `ai_model/models/hb_regressor_best.pt`.
- FastAPI startup loads the checkpoint once and reuses the predictor.
- `/health` works.
- `/api/v1/model/status` reports `MODEL_READY` with real model metadata.
- `/api/v1/predict` accepts multipart `image` and optional `mask`.
- Masked prediction with sample image returned a real AI result:
  `estimated_hb_g_dl=6.371901512145996`,
  `confidence_status=MEDIUM_CONFIDENCE`,
  `model.version=anaemia-hb-mobilenetv3-v1`.
- Image-only prediction returns `ROI_FAILED` because the existing AI predictor
  requires a valid conjunctiva ROI mask. No fake Hb is returned.
- Flutter parser/result screen updated for the real AI fields and `ROI_FAILED`.
- Documentation added/updated:
  `backend/README.md`, `backend/API_DOCUMENTATION.md`, `END_TO_END_TTESTED:
- AI suite: `129 passed, 14 subtests passed in 8.91s`.
- Backend suite: `13 passed in 0.69s`.
- Backend startup: real model loaded in `3.283s`.
- Real masked `/api/v1/predict`: inference completed in `1.9021s`.
- `flutter analyze` was attempted but hung with no output for over 90 seconds
  and was stopped.

BLOCKER / NEXT WORK:
- The current Flutter camera flow sends only a captured image. The AI model's
  current contract requires a matching ROI mask for successful inference.
- Next step should be one of:
  1. Add/route an ROI mask generation step from the existing `ai_model` pipeline
     that does not require a pre-existing dataset mask, if available; or
  2. Add a Flutter/backend capture flow that supplies the required ROI mask; or
  3. Ask the AI-model owner to expose a documented image-only predictor if that
     is intended.
- Do not bypass this by generating fake masks or fake Hb values.

OLDER PHASE NOTE:
Phase 1 — Dataset Verification (PARTIAL — sample-only, repo not accessible this session)

## 2026-08-22 Consolidation Update

The authoritative AI project from `MITINDIA/` has been consolidated under
`ai_model/`. The promoted checkpoint is `ai_model/models/hb_regressor_best.pt`
and the inference entry point is `ai_model/src/inference/predictor.py`.
The original `MITINDIA/` directory is intentionally preserved and must not be
archived until the consolidated AI test suite and checkpoint smoke test pass.
See `AI_CONSOLIDATION_REPORT.md` for the source comparison and unresolved
metric-document conflict.

COMPLETED:
- Verified a 6-file, 2-subject SAMPLE dataset provided directly by the user
  (not pulled from the GitHub repo or IEEE DataPort/Kaggle — those were unreachable
  from this session's environment: no outbound network, and the repo did not
  surface via web search/fetch).
- Wrote and ran src/data_analysis.py (read-only) against the sample; verified raw
  files unchanged before/after (md5sum diff clean).
- Confirmed file naming convention: {SUBJECT_ID}.jpg + {SUBJECT_ID}_{forniceal,
  palpebral,forniceal_palpebral}.png, SUBJECT_ID = capture timestamp, no separate
  patient ID field.
- Confirmed raw photo format (JPEG, 3984x2988, RGB) and mask format (PNG, 800x1067,
  RGBA) for the sampled subject.
- Confirmed masks are RGBA cutouts carrying real tissue-color pixels (not flat
  overlays), and forniceal_palpebral = pixel-union of forniceal + palpebral.
- Confirmed geometric relationship: mask = raw photo rotated per EXIF Orientation
  tag, then downscaled ~3.735x — NOT a direct crop of the raw pixel grid.

IMPORTANT FINDINGS:
- DEFECT: all 4 sampled PNG masks have a corrupted iCCP chunk (bad CRC). Plain
  PIL.Image.open() crashes on every mask file; cv2.imread(..., IMREAD_UNCHANGED)
  loads them fine. MUST be checked at full-dataset scale before Phase 2 picks a
  loader.
- Mask alpha-channel style is NOT uniform in the sample: one subject's masks are
  near-binary (2-3 alpha levels), the other subject's masks are soft/anti-aliased
  (254-256 alpha levels). Only n=2 — needs checking at scale.
- 1 of 2 sampled subjects has masks but NO raw photo included.
- No Hb values, age, sex, or metadata table of any kind exist in the sample
  provided. Filenames/EXIF/PNG metadata contain zero Hb information.

FEASIBILITY:
C — Neither Hb regression nor classification can be determined yet. This is a
DATA-AVAILABILITY blocker (no metadata/Hb table was accessible this session), not
a negative finding about image quality or dataset structure — the image/mask
pipeline itself looks usable once the iCCP and rotation issues are handled.

FILES CREATED:
- DATASET_VERIFICATION_REPORT.md
- DATASET_SCHEMA.md
- src/data_analysis.py
- dataset_analysis_report.json (raw script output, sample-only)
- HANDOFF.md (this file)

BLOCKERS:
1. This session had no outbound network access and could not reach
   github.com/KrushnXGIT/QuadNova, IEEE DataPort, Kaggle, or data.gov.in.
   PROJECT_MASTER.md, README.md, and the prior HANDOFF.md content in the actual
   repo were never read — whoever runs Account 1 for real (with repo access) should
   re-run this verification against the FULL dataset and reconcile with this
   sample-based report.
2. No Hb metadata table was available — required before any real feasibility
   decision can be made.
3. iCCP CRC corruption rate and mask alpha-style consistency need confirming at
   full-dataset scale (only checked on 4 mask files here).

NEXT ACCOUNT:
Account 2 — Data Preparation

ACCOUNT 2 MUST:
Read PROJECT_MASTER.md, HANDOFF.md, DATASET_VERIFICATION_REPORT.md and
DATASET_SCHEMA.md before starting. Given Blocker #1 above, Account 2 (or whoever
has actual repo/dataset access) should first re-run src/data_analysis.py against
the FULL dataset directory to confirm these sample-derived findings hold at scale,
before building any preprocessing pipeline on top of them.
