# Clinical interpretation

## Active behavior: Case 3

The app currently collects an eye image only for a screening request. It does
not collect age, sex, pregnancy status, or another user category required for a
category-specific clinical reference standard.

The project also has no validated/configured clinical Hb interpretation rule.
The available uncertainty thresholds are model-confidence thresholds, not
clinical Hb thresholds. Hb range analysis in the AI project is for subgroup
analysis only and is not an app classification rule.

Therefore the app uses Case 3 from the clinical safety requirement:

- It displays `Estimated haemoglobin: X.X g/dL`.
- It states that clinical interpretation is not available from this screening alone.
- It does not display `Normal`, `Anaemia`, or another definitive clinical class.
- It recommends consultation with a healthcare professional and confirmation
  with an appropriate blood test.
- It separately explains model confidence and image quality without presenting
  either as clinical certainty.

The shared `ReportStrings.interpretationLines` helper is used by the live result,
history report, and downloadable PDF so the same screening record receives the
same interpretation everywhere.
