"""Tests for clinical metadata validation."""

import pandas as pd
import pytest

from src.data.validate_metadata import MetadataValidationError, validate_metadata


def write_metadata(path, rows):
    pd.DataFrame(rows, columns=["SUBJECT_ID", "Hb"]).to_csv(path, index=False)


def test_empty_template_is_rejected(tmp_path):
    path = tmp_path / "template.csv"
    path.write_text("SUBJECT_ID,Hb\n# example only\n", encoding="utf-8")
    with pytest.raises(MetadataValidationError, match="no data rows"):
        validate_metadata(path)


def test_valid_metadata_without_image_matching(tmp_path):
    path = tmp_path / "labels.csv"
    write_metadata(path, [["20200118_164733", 11.2]])
    report = validate_metadata(path)
    assert report["valid"] is True
    assert report["metadata_rows"] == 1


@pytest.mark.parametrize(
    "rows, message",
    [
        ([["20200118_164733", None]], "Missing or non-numeric Hb"),
        ([["20200118_164733", -1]], "Invalid Hb values"),
        ([["bad-subject", 11.2]], "Invalid SUBJECT_ID format"),
        ([
            ["20200118_164733", 11.2],
            ["20200118_164733", 12.0],
        ], "Duplicate SUBJECT_ID"),
    ],
)
def test_invalid_metadata_is_rejected(tmp_path, rows, message):
    path = tmp_path / "labels.csv"
    write_metadata(path, rows)
    with pytest.raises(MetadataValidationError, match=message):
        validate_metadata(path)


def test_image_matching_rejects_unmatched_subject(tmp_path):
    path = tmp_path / "labels.csv"
    write_metadata(path, [["20200203_091841", 11.2]])
    with pytest.raises(MetadataValidationError, match="unmatched"):
        validate_metadata(path, "data/raw/sample_dataset")
