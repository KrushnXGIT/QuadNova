# Data Directory

This directory contains dataset-related files.

## Directory Structure

```text
data/
│
├── README.md
│
├── raw/
│   └── Original dataset files
│
├── metadata/
│   └── Dataset manifests and metadata
│
└── processed/
    └── Generated/processed data
```

---

## `raw/`

Place original datasets here when local storage is required and when their licence/access conditions permit it.

Raw data must not be modified.

Example:

```text
data/raw/
└── dataset_name/
```

Do not assume that a dataset should be committed to GitHub.

Large datasets should normally be stored outside normal Git unless an appropriate storage mechanism such as Git LFS is deliberately configured.

---

## `metadata/`

This directory may contain:

* dataset manifests;
* CSV files describing images;
* label mappings;
* participant mappings;
* dataset documentation;
* preprocessing configuration;
* data dictionaries.

Only metadata that is permitted by the dataset's licence/access terms should be stored.

---

## `processed/`

This directory contains generated datasets.

Examples:

* resized images;
* normalized images;
* cropped ocular regions;
* train/validation/test manifests;
* cleaned metadata.

Processed files should always be reproducible from the raw data and documented preprocessing code where possible.

---

## Data Integrity Rules

1. Never overwrite raw data.
2. Never fabricate labels.
3. Never silently remove records.
4. Document filtering criteria.
5. Record dataset versions where available.
6. Check for duplicate participants.
7. Check for duplicate images.
8. Prevent participant-level data leakage.
9. Respect dataset licences and access restrictions.
10. Do not commit secrets or private information.

---

## Dataset Verification

Before model development, document:

* dataset source;
* licence;
* number of participants;
* number of images;
* image format;
* image resolution;
* available labels;
* haemoglobin measurements;
* anaemia labels;
* demographic variables;
* missing data;
* participant/image relationships.

The actual dataset must be inspected before these values are recorded.
