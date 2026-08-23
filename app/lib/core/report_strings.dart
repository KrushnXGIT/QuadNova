/// All user-facing strings shown on the Screening Report screen and PDF.
///
/// Keeping them here makes future localisation (Hindi, Marathi, …) a
/// matter of adding a locale switch — without touching UI or PDF code.
///
/// Current default: English.
class ReportStrings {
  ReportStrings._();

  // ── Header ───────────────────────────────────────────────
  static const String appName     = 'Smartphone Anaemia Screening';
  static const String reportTitle = 'Screening Report';
  static const String dateLabel   = 'Date';
  static const String timeLabel   = 'Time';
  static const String screeningIdLabel = 'Screening ID';

  // ── Main result ──────────────────────────────────────────
  static const String estimatedHb       = 'Estimated Haemoglobin';
  static const String unit              = 'g/dL';
  static const String screeningEstimate =
      'Screening estimate — not a clinical diagnosis';

  // ── Confidence ───────────────────────────────────────────
  static const String confidenceLabel   = 'Screening confidence';
  static const String high              = 'High';
  static const String medium            = 'Medium';
  static const String low               = 'Low';
  static const String notAvailable      = 'Not available';
  static const String confidenceExplanation =
      'Confidence tells you how suitable the screening result was based on '
      'the image and system checks.';

  static String confidenceDisplay(String status) {
    switch (status.toUpperCase()) {
      case 'HIGH_CONFIDENCE':
        return high;
      case 'MEDIUM_CONFIDENCE':
        return medium;
      case 'LOW_CONFIDENCE':
        return low;
      default:
        return notAvailable;
    }
  }

  // ── Image quality ────────────────────────────────────────
  static const String imageQualityLabel = 'Image quality';
  static const String imageQualityGood  = 'Good';
  static const String imageQualityAcceptable = 'Acceptable';
  static const String imageQualityPoor  = 'Poor';

  static String qualityDisplay(String status) {
    switch (status.toUpperCase()) {
      case 'GOOD':
        return imageQualityGood;
      case 'ACCEPTABLE':
        return imageQualityAcceptable;
      case 'POOR':
        return imageQualityPoor;
      case 'PASSED':
        return imageQualityGood;
      case 'FAILED':
        return imageQualityPoor;
      default:
        return status.isEmpty ? notAvailable : status;
    }
  }

  // ── Sections ─────────────────────────────────────────────
  static const String resultLabel       = 'Result';
  static const String statusUnavailable = 'Clinical interpretation unavailable';
  static const String statusExplanation =
      'This screening system does not have enough information or a validated '
      'clinical reference rule to classify the estimate as low or within range.';
  static const String whatThisMeans  = 'What This Means';
  static const String nextStep       = 'Recommended next step';
  static const String importantNote  = 'Important';
    static const String disclaimer     =
      'This result is a screening estimate and does not replace a clinical '
      'blood test or medical diagnosis.';

  // ── Interpretation templates ──────────────────────────────
  static const String interpHighConf =
      'This estimate was produced with good image quality. '
      'It is still a screening estimate, not a clinical test.';

  static const String interpMedConf =
      'This is a screening estimate. '
      'If you have any concerns, please consult a healthcare professional.';

  static const String interpLowConf =
      'The system was not fully confident in this estimate. '
      'Consider repeating the screening with a clearer eye image.';

  static const String interpHighUncertainty =
      'The estimated uncertainty is relatively high for this reading.';

  static const String noClinicalInterpretation =
      'Clinical interpretation is not available from this screening alone.';
  static const String interpretationConfirmation =
      'Please consult a healthcare professional for interpretation and confirmation '
      'with an appropriate blood test.';

  /// Case 3: the app has no demographic inputs or validated clinical
  /// reference rule, so it must not classify an Hb estimate.
  static List<String> interpretationLines({
    required double estimatedHb,
    required String confidenceStatus,
    required double hbStd,
  }) {
    final cs = confidenceStatus.toUpperCase();
    final lines = <String>[
      'Estimated haemoglobin: ${estimatedHb.toStringAsFixed(1)} g/dL.',
      noClinicalInterpretation,
    ];

    if (cs == 'HIGH_CONFIDENCE') {
      lines.add(interpHighConf);
    } else if (cs == 'MEDIUM_CONFIDENCE') {
      lines.add(interpMedConf);
    } else {
      lines.add(interpLowConf);
    }
    lines.add(interpretationConfirmation);
    return lines;
  }

  // ── Failed / incomplete screening ────────────────────────
  static const String screeningNotCompleted = 'Screening not completed';
  static const String screeningNotCompletedDetail =
      'No haemoglobin estimate is available for this screening.\n'
      'This can happen when the eye image was not clear enough for analysis.';

  // ── Actions ──────────────────────────────────────────────
  static const String downloadReport = 'Download Report';
  static const String shareReport    = 'Share Report';
  static const String backToHistory  = 'Back to History';

  // ── Errors ───────────────────────────────────────────────
  static const String pdfFailed =
      'Could not create the report. Please try again.';
  static const String reportIncomplete =
      'Report data is incomplete.';

  // ── PDF footer ───────────────────────────────────────────
  static const String pdfFooterPrefix = 'Generated on';
  static const String pdfDisclaimer   =
      'This PDF is a screening estimate only. '
      'It is not a medical diagnosis and does not replace a clinical blood test. '
      'Consult a healthcare professional for any medical concerns.';
}
