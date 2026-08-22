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
  static const String confidenceLabel   = 'How sure the system is';
  static const String high              = 'High';
  static const String medium            = 'Medium';
  static const String low               = 'Low';
  static const String notAvailable      = 'Not available';

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

  // ── Technical details ────────────────────────────────────
  static const String technicalDetails  = 'Technical details';
  static const String modelLabel        = 'Model';
  static const String modelVersionLabel = 'Version';
  static const String uncertaintyLabel  = 'Estimated uncertainty';
  static const String ciLabel           = 'Estimated range (95%)';

  // ── Sections ─────────────────────────────────────────────
  static const String whatThisMeans  = 'What This Means';
  static const String nextStep       = 'Recommended next step';
  static const String importantNote  = 'Important';
  static const String disclaimer     =
      'This report does not replace a blood test or a medical diagnosis. '
      'It is a screening estimate only.';

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

  static const String interpLowHb =
      'This result may suggest your haemoglobin level could be lower than expected. '
      'Please consult a healthcare professional and consider a confirmatory blood test.';

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
