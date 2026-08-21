# Flutter and AI Model Structure Validation

> Superseded for AI contents by [AI_CONSOLIDATION_REPORT.md](AI_CONSOLIDATION_REPORT.md).
> The original Flutter/backend validation below remains historical.

Date: 2026-08-22

## Before

- Flutter application root: `app/`
- Flutter source: `app/lib/`
- Existing screens, widgets, camera flow, and services were already present.
- Existing API client: `app/lib/services/api_service.dart`
- Backend already existed at `backend/`; it was not created or modified in this step.
- Root `src/` and `models/` directories contained empty research placeholders.
- No AI checkpoint, predictor, model card, or model API contract was present.
- No `app/assets/` directory was present.

## After

```text
smartphone-anaemia-screening/
├── app/
│   ├── lib/
│   │   ├── core/config/api_config.dart
│   │   ├── screens/
│   │   ├── services/
│   │   ├── theme/
│   │   └── widgets/
│   ├── assets/images/
│   ├── assets/icons/
│   ├── test/
│   └── pubspec.yaml
├── ai_model/
│   ├── src/{model,vision,inference,data}/
│   ├── models/
│   ├── tests/
│   ├── results/
│   ├── MODEL_CARD.md
│   ├── MODEL_API_CONTRACT.md
│   ├── BACKEND_MODEL_INTEGRATION.md
│   └── requirements.txt
├── backend/                 # Existing; unchanged in this step
├── PROJECT_MASTER.md
├── README.md
└── STRUCTURE_VALIDATION_REPORT.md
```

## Changes

- Added the isolated `ai_model/` boundary and tracked empty subdirectories.
- Added model status, contract, and backend integration documentation.
- Added Flutter asset directories and registered them in `app/pubspec.yaml`.
- Added `app/lib/core/config/api_config.dart`.
- Removed the developer-specific LAN IP from `ApiService`; runtime URL storage
  remains the source of truth, with the generic Android emulator URL documented.
- Preserved existing Flutter screens, navigation, services, and dependencies.
- No Python files were moved into Flutter, no model files were duplicated, and
  no backend implementation was added.

## Verification

- `flutter analyze`: passed, no issues found.
- `flutter test`: failed in the existing splash widget test. The test searches
  for a single `HemoScan AI` text node, but the splash renders `HemoScan` and
  ` AI` as separate `TextSpan`s. This is unrelated to the structure changes and
  was not changed because test expectations must not be altered only to pass.
- Backend tests: passed, 13 tests.
- AI model tests: not runnable; no AI model test files exist.

## Model artifacts

- Checkpoint: missing.
- Predictor/inference entry point: missing.
- Model framework dependencies: not documented because the checkpoint format is
  unknown.
- Model API contract: documented in `ai_model/MODEL_API_CONTRACT.md`.
- Backend integration status: documented in
  `ai_model/BACKEND_MODEL_INTEGRATION.md`.

## Before backend/model integration

1. Resolve the existing splash widget test.
2. Supply the validated checkpoint and provenance.
3. Add the model runtime dependencies and inference entry point.
4. Confirm training-compatible ROI and normalization.
5. Add model-path tests and held-out inference tests.
