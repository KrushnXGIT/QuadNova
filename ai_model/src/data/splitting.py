"""
splitting.py
============
Subject-level train/validation/test split.

SUBJECT_ID (the capture-timestamp filename prefix — confirmed in
DATASET_SCHEMA.md to be the only subject key available; there is no
separate patient-ID field) is the split unit. All files belonging to a
subject (raw photo + all mask variants) always land in the same split.
This is done at the subject level even though no Hb label is available
yet, because leakage prevention is a property of the IMAGE data, not of
the label — it must be correct before labels are ever joined in.

Split is deterministic: same input file list + same seed -> same split,
every time (verified by test_split_reproducibility in the test suite).
"""

import json
import os
import random

from . import config


def compute_split(subject_ids, ratios=None, seed=None):
    """
    Deterministically assign each subject_id to train/val/test.

    Uses a seeded shuffle over the SORTED subject-id list (sorting first
    removes any dependency on filesystem iteration order, which is not
    guaranteed stable across OSes/runs).
    """
    ratios = ratios or config.SPLIT_RATIOS
    seed = config.RANDOM_SEED if seed is None else seed

    assert abs(sum(ratios.values()) - 1.0) < 1e-6, f"split ratios must sum to 1.0, got {ratios}"

    ids = sorted(set(subject_ids))
    rng = random.Random(seed)
    rng.shuffle(ids)

    n = len(ids)
    n_train = round(n * ratios["train"])
    n_val = round(n * ratios["val"])
    # test gets the remainder so rounding never drops/duplicates a subject
    n_test = n - n_train - n_val

    train_ids = ids[:n_train]
    val_ids = ids[n_train:n_train + n_val]
    test_ids = ids[n_train + n_val:]
    assert len(train_ids) == n_train
    assert len(val_ids) == n_val
    assert len(test_ids) == n_test

    return {"train": train_ids, "val": val_ids, "test": test_ids}


def assert_no_overlap(split):
    train, val, test = set(split["train"]), set(split["val"]), set(split["test"])
    overlaps = {
        "train_val": sorted(train & val),
        "train_test": sorted(train & test),
        "val_test": sorted(val & test),
    }
    bad = {k: v for k, v in overlaps.items() if v}
    if bad:
        raise AssertionError(f"Subject leakage across splits detected: {bad}")
    return True


def save_split(split, out_path=None, ratios=None, seed=None):
    out_path = str(out_path or (config.SPLITS_DIR / "split.json"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = {
        "seed": config.RANDOM_SEED if seed is None else seed,
        "ratios": ratios or config.SPLIT_RATIOS,
        "counts": {k: len(v) for k, v in split.items()},
        "split": split,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    return out_path


def load_split(path=None):
    path = str(path or (config.SPLITS_DIR / "split.json"))
    with open(path) as f:
        return json.load(f)
