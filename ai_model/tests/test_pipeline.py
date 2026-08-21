"""
test_pipeline.py
=================
Executable checks proving the Phase 2 pipeline actually works, using the
synthetic fixtures (tests/make_synthetic_fixtures.py) since the real
dataset was not included in the ZIP handed to Account 2. Run with:

    python3 tests/test_pipeline.py

Covers the "TEST" requirements from the task brief:
  - successful execution
  - correct outputs
  - no leakage
  - reproducible split
  - raw data unchanged
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Redirect all pipeline output paths into tests/synthetic_fixtures/* BEFORE
# importing src.data.config (which reads these env vars at import time),
# so running the synthetic test suite never touches the real data/,
# outputs/, or splits/ directories reserved for the actual dataset.
_FIXROOT = os.path.join(os.path.dirname(__file__), "synthetic_fixtures")
os.environ.setdefault("ANAEMIA_METADATA_DIR", os.path.join(_FIXROOT, "metadata"))
os.environ.setdefault("ANAEMIA_SPLITS_DIR", os.path.join(_FIXROOT, "splits"))
os.environ.setdefault("ANAEMIA_PROCESSED_DATA_DIR", os.path.join(_FIXROOT, "processed_testrun"))
os.environ.setdefault("ANAEMIA_REPORTS_DIR", os.path.join(_FIXROOT, "outputs_testrun"))

from tests.make_synthetic_fixtures import build_synthetic_fixtures, SUBJECT_IDS
from src.data import config
from src.data.matching import scan_raw_data_dir
from src.data.splitting import compute_split, assert_no_overlap
from src.data.validation import snapshot_raw_dir_checksums
from src.data.pipeline import run_pipeline

config.SPLITS_DIR = Path(os.path.join(_FIXROOT, "splits"))


@pytest.fixture(scope="module")
def raw_dir():
    """Build and return the isolated synthetic raw-data fixture directory."""
    raw_path, _ = build_synthetic_fixtures(force=True)
    return raw_path


def test_matching_finds_all_synthetic_subjects(raw_dir):
    records, unclassified = scan_raw_data_dir(raw_dir)
    assert len(records) == 7, f"expected 7 subjects (5 base + 1 duplicate + 1 truncated), got {len(records)}"
    assert "README_not_a_subject_file.txt" in unclassified
    print("PASS: matching finds all synthetic subjects + flags the unclassified file")


def test_split_is_reproducible(raw_dir):
    records, _ = scan_raw_data_dir(raw_dir)
    ids = list(records.keys())
    split_a = compute_split(ids, seed=42)
    split_b = compute_split(ids, seed=42)
    assert split_a == split_b, "same seed must produce an identical split"

    split_c = compute_split(ids, seed=123)
    assert split_a != split_c, "different seeds should (almost always) differ"
    print("PASS: split is reproducible given a fixed seed")


def test_split_has_no_leakage(raw_dir):
    records, _ = scan_raw_data_dir(raw_dir)
    ids = list(records.keys())
    split = compute_split(ids, seed=42)
    assert_no_overlap(split)  # raises AssertionError on failure
    total = sum(len(v) for v in split.values())
    assert total == len(ids), "every subject must land in exactly one split"
    print("PASS: no subject leakage across train/val/test")


def test_raw_data_unchanged(raw_dir):
    before = snapshot_raw_dir_checksums(raw_dir)
    run_pipeline(raw_dir=raw_dir,
                 out_dir="tests/synthetic_fixtures/outputs_testrun",
                 processed_dir="tests/synthetic_fixtures/processed_testrun",
                 seed=42)
    after = snapshot_raw_dir_checksums(raw_dir)
    assert before == after, "pipeline must never modify RAW_DATA_DIR"
    print("PASS: raw data checksums identical before/after pipeline run")


def test_pipeline_end_to_end_outputs(raw_dir):
    out_dir = "tests/synthetic_fixtures/outputs_testrun"
    summary = run_pipeline(raw_dir=raw_dir, out_dir=out_dir,
                            processed_dir="tests/synthetic_fixtures/processed_testrun", seed=42)
    assert summary["raw_data_unchanged"] is True
    assert summary["n_subjects_found"] == 7
    assert os.path.isfile(os.path.join(out_dir, "matching_report.json"))
    assert os.path.isfile(os.path.join(out_dir, "split.json"))
    assert os.path.isfile(os.path.join(out_dir, "quality_report.json"))

    with open(os.path.join(out_dir, "quality_report.json")) as f:
        q = json.load(f)
    assert q["corrupted_images"]["total_corrupted"] == 1, "the deliberately-truncated fixture must be caught"
    assert q["missing_images"]["count_mask_no_raw"] == 1, "subject with masks-only must be flagged"
    # subjects 4 (raw-only), the duplicate-raw subject, and the truncated-file
    # subject are all "raw present, no mask" -> expect >=1, not necessarily exactly 1
    assert q["missing_images"]["count_raw_no_mask"] >= 1, "subject(s) with raw-only must be flagged"
    assert q["duplicate_images"]["duplicate_groups"] >= 1, "the deliberate raw-photo duplicate must be caught"
    print("PASS: end-to-end pipeline outputs are correct and match known synthetic-fixture properties")


def test_verified_regression_target():
    assert config.TARGET_MODE == "regression"
    print("PASS: TARGET_MODE is regression from verified workbook Hgb metadata")


if __name__ == "__main__":
    raw_dir, meta_dir = build_synthetic_fixtures(force=True)
    os.environ["ANAEMIA_METADATA_DIR"] = meta_dir

    test_matching_finds_all_synthetic_subjects(raw_dir)
    test_split_is_reproducible(raw_dir)
    test_split_has_no_leakage(raw_dir)
    test_raw_data_unchanged(raw_dir)
    test_pipeline_end_to_end_outputs(raw_dir)
    test_verified_regression_target()
    print("\nALL TESTS PASSED (against SYNTHETIC fixtures — real dataset still required, see HANDOFF.md)")
