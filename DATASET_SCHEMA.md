# Dataset Schema — Phase 1 (Sample-Verified)

Derived from `src/data_analysis.py` output on the 6-file sample in
`QuadNova__datazip.zip`. This is a **schema hypothesis confirmed on n=2 subjects**,
not a full-dataset schema — re-run `data_analysis.py` against the full dataset to
confirm it generalizes.

## File Naming Convention (confirmed)

```
{SUBJECT_ID}.jpg                          -> raw smartphone photo
{SUBJECT_ID}_forniceal.png                -> forniceal conjunctiva ROI mask (RGBA cutout)
{SUBJECT_ID}_palpebral.png                -> palpebral conjunctiva ROI mask (RGBA cutout)
{SUBJECT_ID}_forniceal_palpebral.png      -> union of the two masks above

SUBJECT_ID = YYYYMMDD_HHMMSS   (capture timestamp; also the subject key —
                                 no separate patient/subject ID field exists)
```

## Per-File Schema

### Raw photo (`{id}.jpg`)
| Field | Value (verified) |
|---|---|
| Format | JPEG |
| Dimensions | 3984 × 2988 (device-dependent — confirm across more samples) |
| Color mode | RGB, 3 channel |
| EXIF present | Yes — Make, Model, Orientation, DateTime, ExifImageWidth/Height |
| Orientation tag | Can be non-1 (e.g. `6` = rotate 90° CW) — **must be applied**, image data itself is not pre-rotated |

### Mask files (`{id}_forniceal.png`, `{id}_palpebral.png`, `{id}_forniceal_palpebral.png`)
| Field | Value (verified) |
|---|---|
| Format | PNG |
| Dimensions | 800 × 1067 (== raw photo rotated per EXIF, then downscaled ~3.735×) |
| Color mode | RGBA, 4 channel |
| Alpha channel semantics | 0 = outside ROI (transparent); >0 = inside ROI. NOT guaranteed binary — seen 2–3 levels in some files, 254–256 levels (soft/anti-aliased) in others |
| RGB-in-masked-region semantics | Actual cropped tissue pixel color (not a flat highlight color) |
| Known integrity defect | `iCCP` chunk fails CRC check in 100% of sampled masks (4/4). Plain `PIL.Image.open()` **cannot** open these files — use OpenCV (`cv2.imread(path, cv2.IMREAD_UNCHANGED)`) or strip/repair the `iCCP` chunk first |
| `forniceal_palpebral` vs. parts | Confirmed pixel-count union of `forniceal` + `palpebral` for the one subject where all 3 masks existed |

## IMAGE → SUBJECT → Hb Mapping

```
IMAGE (.jpg)  --[shares SUBJECT_ID prefix]-->  SUBJECT (= timestamp string)
SUBJECT       --[NOT PRESENT IN THIS SAMPLE]--> Hb value
```

**No file in this sample encodes Hb.** The Hb value must live in an external
metadata table (CSV/XLSX per the original Eyes-Defy-Anemia distribution, per its
IEEE DataPort documentation) that was not part of the uploaded sample. Until that
table is obtained, `SUBJECT_ID → Hb` cannot be resolved, and this schema doc should
be updated with its column names/types the moment it's available.

## Known Gaps / Open Items for Account 2

- [ ] Confirm image dimensions are constant across the full dataset or vary by device.
- [ ] Confirm the `iCCP` CRC defect rate across the full dataset (4/4 in this sample).
- [ ] Confirm mask alpha-channel style (binary vs. soft) is consistent or mixed at scale.
- [ ] Obtain and document the Hb metadata table schema (columns, types, join key).
- [ ] Confirm whether every subject has a raw photo (1 of 2 sampled subjects did not).
