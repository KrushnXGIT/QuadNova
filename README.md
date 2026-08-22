# Smartphone-Based Anaemia Screening

A research-oriented project for investigating whether smartphone-captured ocular images can be used to estimate haemoglobin-related anaemia risk.

## Objective

The project investigates a computer-vision pipeline using smartphone images of the eye/ocular region, together with appropriate demographic or contextual information where justified, to explore non-invasive estimation or screening of anaemia.

The system is intended as a **research prototype**, not a medical diagnostic device.

## Project Goals

* Identify and verify suitable datasets.
* Understand image and label availability.
* Build a reproducible data-processing pipeline.
* Investigate image-quality and preprocessing requirements.
* Develop baseline computer-vision/ML models.
* Evaluate model performance using appropriate metrics.
* Investigate generalisation and possible demographic/geographic bias.
* Build an eventual prototype interface only after the research pipeline is validated.

## Repository Structure

```text
smartphone-anaemia-screening/
│
├── README.md
├── PROJECT_MASTER.md
├── HANDOFF.md
├── CHANGELOG.md
├── .gitignore
├── requirements.txt
│
├── data/
│   ├── README.md
│   ├── raw/
│   ├── metadata/
│   └── processed/
│
├── app/                         # Flutter application root
│   ├── lib/
│   │   ├── core/config/
│   │   ├── models/
│   │   ├── screens/
│   │   ├── services/
│   │   └── widgets/
│   ├── assets/images/
│   ├── assets/icons/
│   ├── test/
│   └── pubspec.yaml
├── ai_model/                    # Consolidated MITINDIA AI source of truth
│   ├── src/{model,vision,inference,data}/
│   ├── models/hb_regressor_best.pt
│   ├── tests/
│   ├── results/
│   ├── notebooks/
│   └── MODEL_*.md
├── backend/                     # Existing FastAPI implementation
├── models/                      # Legacy empty research placeholder
│
├── notebooks/
├── results/
├── tests/
└── docs/
```

## Current Development Phase

**FastAPI backend + existing AI model integration**

The application architecture is separated as Flutter (`app/`) -> HTTP ->
FastAPI (`backend/`) -> existing Python model (`ai_model/`). Flutter does not
execute the Python model directly.

The backend now loads the existing `ai_model/models/hb_regressor_best.pt`
checkpoint through `ai_model/src/inference/predictor.py::AnaemiaPredictor`.
Phone uploads pass through a mandatory server-side input-domain gate before
regression:

```text
image -> conjunctiva candidate detection -> ROI quality gate
	-> ROI-only normalization -> Hb regression -> uncertainty/confidence
```

The automatic detector uses conservative classical-CV chroma, connected
component, coverage, and local eye-context checks. It is an input-domain guard,
not true adversarial/OOD detection and is not clinically validated. If no valid
conjunctiva region is detected, the backend returns `ROI_FAILED` with
`error.code=CONJUNCTIVA_NOT_DETECTED`; no Hb value is returned and the
regression predictor is not called.

## Development Philosophy

The project follows these principles:

1. Do not assume dataset structure without inspecting the data.
2. Do not fabricate labels, measurements, or experimental results.
3. Keep raw data unchanged.
4. Separate exploratory analysis from production code.
5. Record important decisions in the repository.
6. Make every phase reproducible.
7. Do not claim clinical validity without appropriate evidence.
8. Preserve dataset licensing and usage restrictions.

## Dataset Policy

The repository should contain dataset metadata and processing instructions.

Large or restricted datasets should not automatically be committed to the repository. Follow the original dataset's licence, terms of use, and redistribution restrictions.

## Research Disclaimer

This project is experimental research software.

It must not be represented as a clinically validated diagnostic system unless appropriate clinical validation, regulatory review, and other required evidence have been completed.

## Development Workflow

Each development phase should:

1. Read `PROJECT_MASTER.md`.
2. Read `HANDOFF.md`.
3. Inspect the current repository state.
4. Verify the actual available inputs.
5. Implement only the assigned phase.
6. Test the implementation.
7. Update documentation.
8. Update `HANDOFF.md`.
9. Update `CHANGELOG.md`.
10. Commit the completed work.

## Status

Backend-to-AI inference and Flutter response parsing are working and tested.
Flutter displays backend ROI/quality failures as a retake flow; the camera guide
is guidance only and the backend remains authoritative.
