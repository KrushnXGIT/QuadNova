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
├── src/
│   ├── data/
│   ├── vision/
│   ├── model/
│   ├── evaluation/
│   └── utils/
│
├── notebooks/
├── models/
├── results/
├── tests/
└── docs/
```

## Current Development Phase

**Phase 1 — Dataset Verification and Project Reconnaissance**

The first phase focuses on understanding the actual available datasets before implementing a machine-learning pipeline.

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

Phase 1 is being prepared for dataset verification.
