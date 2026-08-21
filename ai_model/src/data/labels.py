"""
labels.py
=========
Loader for the external Hb metadata table.

STATUS: BLOCKED (documented, not fabricated).
Account 1's Phase 1 verification could not locate any Hb value, age, sex,
or subject-ID metadata table — see DATASET_VERIFICATION_REPORT.md §1, §8,
§10 and HANDOFF.md ("Blockers" #2). No file in the sample encodes Hb.
The IEEE DataPort distribution of Eyes-Defy-Anemia is documented (by the
dataset's own description, not verified by us) to ship such a table
separately from the image archive.

This module defines the EXPECTED schema so that:
  (a) the moment the real table is supplied, wiring it in is a one-line
      change (point ANAEMIA_METADATA_DIR / METADATA_FILENAME at it), and
  (b) nobody downstream accidentally invents Hb values to unblock
      themselves — calling load_labels() without a real file raises a
      loud, explicit error instead of returning fake data.

EXPECTED SCHEMA (join key = SUBJECT_ID, per DATASET_SCHEMA.md):
    SUBJECT_ID : str   e.g. "20200118_164733" — must match the raw-photo
                       filename stem exactly.
    Hb         : float — haemoglobin value in g/dL, if regression target.
    (optional) anaemia_class : str/int — categorical label, if
                       classification target is confirmed instead.
    (optional) age, sex, ... — any other covariates the real table ships.

Exactly one of {Hb, anaemia_class} determines config.TARGET_MODE. Do not
set TARGET_MODE until this file successfully loads real data and that
data has been cross-checked against DATASET_VERIFICATION_REPORT.md.
"""

import os

import pandas as pd

from . import config

METADATA_FILENAME_CANDIDATES = ("labels.csv", "metadata.csv", "hb_labels.csv")


class LabelsUnavailableError(Exception):
    pass


def find_metadata_file(metadata_dir=None):
    metadata_dir = str(metadata_dir or config.METADATA_DIR)
    if not os.path.isdir(metadata_dir):
        return None
    for fname in METADATA_FILENAME_CANDIDATES:
        candidate = os.path.join(metadata_dir, fname)
        if os.path.isfile(candidate):
            return candidate
    return None


def load_labels(metadata_dir=None):
    """
    Load the SUBJECT_ID -> Hb (or anaemia_class) table.

    Raises LabelsUnavailableError if no metadata file is present, rather
    than returning an empty/fabricated table. This is deliberate: silently
    returning nothing here would let a downstream script proceed as if
    "no labels" were a normal, expected case, when it is actually the
    #1 blocker flagged by Account 1.
    """
    path = find_metadata_file(metadata_dir)
    if path is None:
        raise LabelsUnavailableError(
            "No Hb/label metadata file found. This is a KNOWN, DOCUMENTED "
            "blocker (see HANDOFF.md Blocker #2 and DATASET_VERIFICATION_REPORT.md "
            "§10), not a bug. The image/mask pipeline in this phase runs and is "
            "tested WITHOUT labels; label-joining and target selection are "
            "intentionally left for whoever obtains the real metadata table. "
            "Do not invent Hb values to work around this."
        )

    df = pd.read_csv(path)
    if "SUBJECT_ID" not in df.columns:
        raise LabelsUnavailableError(
            f"Metadata file {path} is missing the required SUBJECT_ID join column. "
            f"Found columns: {list(df.columns)}"
        )
    df["SUBJECT_ID"] = df["SUBJECT_ID"].astype(str)
    return df


def labels_available(metadata_dir=None):
    return find_metadata_file(metadata_dir) is not None
