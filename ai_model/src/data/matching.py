"""
matching.py
===========
Image/Label (raw photo <-> mask) matching, keyed by SUBJECT_ID.

Groups every file in the raw data directory by SUBJECT_ID (per the naming
convention confirmed in DATASET_SCHEMA.md) and reports, per subject, which
of the 4 possible files exist. This is a read-only scan — it never touches
files in RAW_DATA_DIR.
"""

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field

from . import config


SUBJECT_RE = re.compile(config.SUBJECT_ID_PATTERN)


@dataclass
class SubjectRecord:
    subject_id: str
    raw_photo: str = None
    mask_forniceal: str = None
    mask_palpebral: str = None
    mask_forniceal_palpebral: str = None
    unclassified: list = field(default_factory=list)

    @property
    def has_raw(self):
        return self.raw_photo is not None

    @property
    def has_any_mask(self):
        return any([self.mask_forniceal, self.mask_palpebral, self.mask_forniceal_palpebral])

    @property
    def is_complete_quad(self):
        """All 4 files present, matching the fullest pattern seen in the sample."""
        return all([self.raw_photo, self.mask_forniceal, self.mask_palpebral, self.mask_forniceal_palpebral])

    def available_roles(self):
        roles = []
        if self.raw_photo:
            roles.append("raw_photo")
        if self.mask_forniceal:
            roles.append("mask_forniceal")
        if self.mask_palpebral:
            roles.append("mask_palpebral")
        if self.mask_forniceal_palpebral:
            roles.append("mask_forniceal_palpebral")
        return roles


def classify_file(filename):
    """Return (subject_id, role) or (subject_id, None) if unclassifiable."""
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    m = SUBJECT_RE.match(name)
    if m:
        subject_id = m.group("subject_id")
        remainder = name[len(subject_id):]
        if remainder not in ("", *config.MASK_SUFFIXES.values()):
            subject_id = name
            remainder = ""
            for suffix in sorted(config.MASK_SUFFIXES.values(), key=len, reverse=True):
                if name.endswith(suffix):
                    subject_id = name[:-len(suffix)]
                    remainder = suffix
                    break
    else:
        remainder = ""
        subject_id = name
        for suffix in sorted(config.MASK_SUFFIXES.values(), key=len, reverse=True):
            if name.endswith(suffix):
                subject_id = name[:-len(suffix)]
                remainder = suffix
                break
        if not subject_id or not subject_id.replace("_", "").replace("-", "").isalnum():
            return None, None

    if ext in config.RAW_EXTS and remainder == "":
        return subject_id, "raw_photo"
    if ext in config.MASK_EXTS:
        for role_key, suffix in config.MASK_SUFFIXES.items():
            if remainder == suffix:
                return subject_id, f"mask_{role_key}"
    return subject_id, None


def scan_raw_data_dir(raw_data_dir=None):
    """
    Scan raw_data_dir and return (subjects: dict[str, SubjectRecord], unclassified_files: list[str]).
    Read-only: does not open, move, or modify any file.
    """
    raw_data_dir = str(raw_data_dir or config.RAW_DATA_DIR)
    if not os.path.isdir(raw_data_dir):
        raise FileNotFoundError(
            f"RAW_DATA_DIR does not exist: {raw_data_dir}\n"
            "This pipeline does not fabricate data — point ANAEMIA_RAW_DATA_DIR "
            "at the actual dataset directory before running."
        )

    subjects = defaultdict(lambda: None)
    records = {}
    unclassified_files = []

    for fname in sorted(os.listdir(raw_data_dir)):
        fpath = os.path.join(raw_data_dir, fname)
        if not os.path.isfile(fpath):
            continue
        subject_id, role = classify_file(fname)
        if subject_id is None or role is None:
            unclassified_files.append(fname)
            continue

        rec = records.setdefault(subject_id, SubjectRecord(subject_id=subject_id))
        if getattr(rec, role) is not None:
            # Duplicate role for same subject (e.g. two raw photos) — surface, don't silently overwrite
            rec.unclassified.append(fname)
        else:
            setattr(rec, role, fname)

    return records, unclassified_files


def matching_report(raw_data_dir=None):
    """Human/JSON-friendly summary of image/mask matching completeness."""
    records, unclassified = scan_raw_data_dir(raw_data_dir)

    n = len(records)
    n_with_raw = sum(1 for r in records.values() if r.has_raw)
    n_with_any_mask = sum(1 for r in records.values() if r.has_any_mask)
    n_complete_quad = sum(1 for r in records.values() if r.is_complete_quad)
    n_raw_no_mask = sum(1 for r in records.values() if r.has_raw and not r.has_any_mask)
    n_mask_no_raw = sum(1 for r in records.values() if r.has_any_mask and not r.has_raw)

    return {
        "total_subjects": n,
        "subjects_with_raw_photo": n_with_raw,
        "subjects_with_any_mask": n_with_any_mask,
        "subjects_with_complete_quad": n_complete_quad,
        "subjects_raw_only_no_mask": n_raw_no_mask,
        "subjects_mask_only_no_raw": n_mask_no_raw,
        "unclassified_files": unclassified,
        "per_subject": {
            sid: {
                "available_roles": rec.available_roles(),
                "duplicate_or_unclassified_extra_files": rec.unclassified,
            }
            for sid, rec in sorted(records.items())
        },
    }
