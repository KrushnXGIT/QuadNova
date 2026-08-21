# Project Master Document

## Project

**Smartphone-Based Anaemia Screening**

## Purpose

This document is the long-term source of truth for the project.

Every development account or contributor should read this document before modifying the repository.

---

# 1. Problem Statement

Anaemia is a major health problem, and haemoglobin measurement traditionally requires a blood sample or laboratory-based measurement.

This project investigates whether smartphone-acquired ocular images can provide useful visual information for estimating haemoglobin-related measurements or screening for possible anaemia.

The project is intended to investigate the feasibility of a non-invasive computer-vision approach.

---

# 2. Primary Objective

Develop and evaluate a reproducible research pipeline that investigates the relationship between smartphone ocular images and haemoglobin/anaemia-related labels.

The final system should only make claims supported by experimental evidence.

---

# 3. Important Limitation

The project is a research prototype.

It is not automatically a medical diagnostic device.

No output should be described as a definitive diagnosis of anaemia.

If future development produces a prediction interface, the interface must clearly communicate the research/experimental nature of the system.

---

# 4. Research Questions

The project should investigate questions such as:

1. Are suitable ocular-image datasets available?
2. Do the datasets contain reliable haemoglobin or anaemia labels?
3. What image regions contain useful information?
4. What preprocessing is required?
5. Can baseline computer-vision models learn a meaningful relationship?
6. How well do models generalise to unseen participants?
7. How sensitive is performance to image quality?
8. Does performance vary across demographic or geographic groups?
9. Can the approach provide useful screening information?
10. What limitations prevent clinical deployment?

---

# 5. Dataset Strategy

Potential datasets may include:

* Eyes-Defy-Anemia or equivalent ocular-image datasets.
* NFHS-5 or other population-level datasets where relevant.

Datasets must not be treated as interchangeable.

For every dataset, document:

* source
* licence
* access conditions
* number of participants
* number of images
* image type
* image dimensions
* available labels
* haemoglobin measurement availability
* anaemia definition
* demographic information
* geographic information
* missing values
* duplicate records
* participant/image relationships
* train/test leakage risks

Do not assume that NFHS-5 contains ocular images.

Population datasets may instead be useful for contextual, demographic, prevalence, or epidemiological analysis depending on the actual variables available.

---

# 6. Data Integrity Rules

Raw data must never be modified directly.

Use:

```text
data/raw/
```

for original data.

Use:

```text
data/processed/
```

for generated datasets.

Use:

```text
data/metadata/
```

for dataset documentation, mappings, manifests, and metadata that are legally permissible to store.

---

# 7. Machine Learning Rules

The project must avoid data leakage.

If multiple images belong to one participant:

* participant-level splitting should be considered;
* images from the same participant must not unintentionally appear in both training and test sets.

Preprocessing parameters must be fitted using training data where appropriate.

Test data must remain isolated until evaluation.

---

# 8. Evaluation

Depending on the task formulation, possible metrics include:

## Regression

* MAE
* RMSE
* R²
* Pearson correlation
* Spearman correlation
* Bland–Altman analysis where appropriate

## Classification

* Accuracy
* Precision
* Recall
* Specificity
* F1
* ROC-AUC
* PR-AUC
* Sensitivity at relevant operating points

The final metric selection must be justified by the actual research question and class distribution.

---

# 9. Experimental Reproducibility

Experiments should record:

* dataset version
* preprocessing configuration
* random seed
* model configuration
* training configuration
* evaluation configuration
* software dependencies
* results
* timestamp/version where useful

Do not report an experiment as successful without reproducible evidence.

---

# 10. Software Architecture

The intended architecture is:

```text
Raw Dataset
     │
     ▼
Dataset Verification
     │
     ▼
Metadata / Manifest
     │
     ▼
Image Quality Control
     │
     ▼
Preprocessing
     │
     ▼
Train / Validation / Test Split
     │
     ▼
Baseline Models
     │
     ▼
Model Training
     │
     ▼
Evaluation
     │
     ▼
Bias / Generalisation Analysis
     │
     ▼
Prototype Interface
```

---

# 11. Repository Responsibilities

## `src/data/`

Dataset loading, validation, manifests, splitting, and preprocessing.

## `src/vision/`

Image-quality analysis, ocular-region processing, cropping, segmentation, and related computer-vision utilities.

## `src/model/`

Model definitions, training utilities, inference code, and model configuration.

## `src/evaluation/`

Metrics, evaluation reports, plots, subgroup analysis, and validation utilities.

## `src/utils/`

General reusable utilities.

---

# 12. Development Phases

## Phase 1 — Dataset Verification

Determine:

* what datasets actually exist;
* what files they contain;
* what labels exist;
* how images map to participants;
* whether haemoglobin measurements exist;
* whether the data can legally be used;
* whether the data are suitable for the research question.

Deliverable:

Dataset Verification Report.

---

## Phase 2 — Data Preparation

Create:

* dataset manifest;
* metadata schema;
* image validation;
* preprocessing pipeline;
* participant-level split strategy.

Deliverable:

Reproducible dataset pipeline.

---

## Phase 3 — Baseline Models

Implement simple baselines before complex deep-learning models.

Potential approaches:

* linear regression;
* logistic regression;
* random forest;
* gradient boosting;
* simple CNN baseline.

Deliverable:

Baseline experiment report.

---

## Phase 4 — Advanced Vision Models

Investigate appropriate deep-learning architectures.

Possible directions:

* CNNs;
* transfer learning;
* image encoders;
* attention mechanisms;
* multimodal models where justified.

Do not introduce complexity without evidence that it is useful.

---

## Phase 5 — Evaluation and Robustness

Investigate:

* generalisation;
* image quality;
* subgroup performance;
* calibration;
* dataset shift;
* sensitivity to acquisition conditions.

Deliverable:

Robustness and generalisation report.

---

## Phase 6 — Prototype

Only after the research pipeline is sufficiently validated should a user-facing prototype be developed.

Possible prototype:

```text
Smartphone Image
       ↓
Image Quality Check
       ↓
Ocular Region Detection
       ↓
Model
       ↓
Estimated Haemoglobin / Risk Score
       ↓
Research Disclaimer
```

---

# 13. Multi-Account Development Protocol

Multiple development accounts may work sequentially on the repository.

Every account must:

1. Read `PROJECT_MASTER.md`.
2. Read `HANDOFF.md`.
3. Inspect the current Git state.
4. Inspect existing code before modifying it.
5. Avoid duplicating existing work.
6. Complete only the assigned phase.
7. Test changes.
8. Update documentation.
9. Update `HANDOFF.md`.
10. Update `CHANGELOG.md`.
11. Commit changes.

The repository is the source of truth.

---

# 14. Never Do These Things

Do not:

* fabricate dataset statistics;
* invent labels;
* invent model performance;
* claim clinical accuracy without validation;
* modify raw data;
* leak test data into training;
* upload secrets;
* upload restricted datasets without checking permission;
* delete previous experimental evidence without documentation;
* silently change project objectives.

---

# 15. Definition of Done

A phase is complete only when:

* implementation exists;
* implementation has been tested;
* results are recorded;
* important decisions are documented;
* limitations are documented;
* `HANDOFF.md` is updated;
* `CHANGELOG.md` is updated;
* repository state is clean enough for the next account to continue.

---

# 16. Current Status

Current phase:

**Phase 1 — Dataset Verification and Project Reconnaissance**

Next objective:

Inspect the actual datasets and determine exactly what information is available before deciding the final modelling formulation.
