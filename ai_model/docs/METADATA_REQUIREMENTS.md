# Hb Metadata Requirements

## Status

The current project contains image and mask files but no verified clinical Hb metadata. Supervised training remains blocked. Do not create values from image colour, population prevalence, or any other proxy.

## Required File

Place the verified clinical metadata at:

```text
data/metadata/labels.csv
```

The accepted minimum schema is:

```csv
SUBJECT_ID,Hb
```

`SUBJECT_ID` must be the exact timestamp identifier from the image filename, for example `20200118_164733`. `Hb` must be the supplied clinical haemoglobin measurement in g/dL. Excel (`.xls`/`.xlsx`) and JSON are supported by the validator, but CSV is the default project location.

Illustrative format only, not training data:

```csv
SUBJECT_ID,Hb
20200118_164733,11.2
```

The illustrative value must be replaced by the verified clinical value before use.

## Image Mapping

The existing naming contract is:

```text
{SUBJECT_ID}.jpg                         -> raw smartphone image
{SUBJECT_ID}_forniceal.png               -> forniceal mask
{SUBJECT_ID}_palpebral.png                -> palpebral mask
{SUBJECT_ID}_forniceal_palpebral.png     -> combined mask
```

The mapping is:

```text
raw image filename -> SUBJECT_ID prefix -> labels.csv SUBJECT_ID -> Hb
```

Masks are not separate subjects and do not receive separate Hb labels. If a subject has multiple raw images, the validator reports that condition for an explicit dataset decision; the current model pipeline expects one raw photo per subject record.

## Validation Rules

Before training, run:

```powershell
python -m src.data.validate_metadata data/metadata/labels.csv --raw-dir data/raw --report outputs/metadata_validation.json
```

The validator rejects:

- Missing `SUBJECT_ID` or `Hb` columns
- Empty metadata rows
- Missing subject IDs or Hb values
- Non-numeric, non-finite, zero, or negative Hb values
- Hb values at or above the integrity bound of 30 g/dL
- Invalid timestamp subject-ID format
- Duplicate subject IDs
- Metadata subjects with no matching raw image
- Raw-image subjects with no metadata row
- Multiple raw images for one subject

The positive Hb and `<30` checks are data-integrity guards, not anaemia thresholds and not clinical validation.

## Prohibited Sources

NFHS-5 population-level prevalence data must not be converted into image-level Hb labels. Do not infer Hb from pixel colour, use synthetic values, or fill missing clinical measurements.

## After Validation

Once the real file passes validation:

1. Run the Phase 2 data pipeline on the complete raw dataset.
2. Confirm the authoritative subject-level split has non-empty train, validation, and test groups with no overlap.
3. Run the Phase 4 training command:

```powershell
python -m src.model.train --raw-dir data/raw --metadata-dir data/metadata --split data/splits/split.json
```

Only then may MAE, RMSE, R2, baseline comparison, plots, and a reloadable checkpoint be reported.

This project is a research prototype for non-invasive anaemia screening. It is not a medical diagnosis, a replacement for a blood test, clinically validated, or guaranteed to provide accurate Hb values.
