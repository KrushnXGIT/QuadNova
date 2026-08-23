import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/screening_history_service.dart';
import '../core/report_strings.dart';
import '../theme/app_theme.dart';
import 'preview_screen.dart';

/// AI anaemia screening report.
///
/// Every displayed number comes from the REAL backend response. This screen
/// never computes, adjusts, or invents Hb values or medical classifications —
/// interpretation is limited to what the backend itself reports
/// (confidence status + recommendation).
class ResultScreen extends StatefulWidget {
  final PredictionResult result;

  /// Path of the analysed capture; enables "Retry" for transient failures
  /// without forcing a recapture.
  final String? imagePath;

  const ResultScreen({super.key, required this.result, this.imagePath});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  bool _historySaved = false;

  @override
  void initState() {
    super.initState();
    if (!_historySaved && widget.result.data != null) {
      _historySaved = true;
      // Fire-and-forget; history must never block or break the report.
      ScreeningHistoryService.instance.addFromResult(widget.result);
    }
  }

  // ── Navigation helpers ────────────────────────────────────

  void _newScreening() {
    Navigator.pushNamedAndRemoveUntil(
        context, '/camera', (r) => r.settings.name == '/main');
  }

  void _backHome() {
    Navigator.pushNamedAndRemoveUntil(context, '/main', (_) => false);
  }

  void _retryUpload() {
    final path = widget.imagePath;
    if (path == null) {
      _newScreening();
      return;
    }
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => PreviewScreen(imagePath: path)),
    );
  }
  // ── Build ─────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      appBar: AppBar(
        backgroundColor: AppTheme.cream,
        automaticallyImplyLeading: false,
        title: const Text('Screening Report'),
        actions: [
          IconButton(
            icon: const Icon(Icons.close_rounded),
            onPressed: _backHome,
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.all(24),
          child: _buildBody(context),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    switch (widget.result.status) {
      case PredictionStatus.predictionComplete:
      case PredictionStatus.lowConfidence:
        return _ReportBody(result: widget.result);

      case PredictionStatus.imageQualityFailed:
        return _FailureBody(
          icon: Icons.image_not_supported_outlined,
          iconColor: AppTheme.terracotta,
          title: 'Image Quality Insufficient',
          message: 'Image quality is not sufficient for screening.',
          detail: widget.result.message,
          reasons: widget.result.data?.quality.failureReasons ?? const [],
          primaryLabel: 'Retake Image',
          onPrimary: _newScreening,
        );

      case PredictionStatus.eyeNotDetected:
        return _FailureBody(
          icon: Icons.visibility_off_outlined,
          iconColor: AppTheme.terracotta,
          title: 'Eye Not Detected',
          message: 'Eye not detected. Please capture a clear image of your eye.',
          detail: widget.result.message,
          reasons: const [],
          primaryLabel: 'Retake Image',
          onPrimary: _newScreening,
        );

      case PredictionStatus.conjunctivaNotDetected:
        return _FailureBody(
          icon: Icons.visibility_outlined,
          iconColor: AppTheme.terracotta,
          title: 'Conjunctiva Not Detected',
          message: 'Please make sure the inner eyelid is clearly visible.',
          detail: widget.result.message,
          reasons: const [],
          primaryLabel: 'Retake Image',
          onPrimary: _newScreening,
        );

      case PredictionStatus.roiQualityFailed:
        return _FailureBody(
          icon: Icons.center_focus_weak_rounded,
          iconColor: AppTheme.terracotta,
          title: 'Image Quality Insufficient',
          message: 'Image quality is insufficient. Please retake the image.',
          detail: widget.result.message,
          reasons: const [],
          primaryLabel: 'Retake Image',
          onPrimary: _newScreening,
        );

      case PredictionStatus.roiFailed:
        return _FailureBody(
          icon: Icons.center_focus_weak_rounded,
          iconColor: AppTheme.terracotta,
          title: 'Required Region Not Found',
          message:
              'We could not reliably identify the required region '
              '(inner eyelid).',
          detail: widget.result.message,
          reasons: const [],
          primaryLabel: 'Retake Image',
          onPrimary: _newScreening,
        );

      case PredictionStatus.modelNotReady:
        return _FailureBody(
          icon: Icons.hourglass_bottom_rounded,
          iconColor: AppTheme.slateLight,
          title: 'Service Temporarily Unavailable',
          message: 'Screening service is temporarily unavailable.',
          detail: widget.result.message,
          reasons: const [],
          primaryLabel: null,
          onPrimary: null,
        );

      case PredictionStatus.networkError:
      case PredictionStatus.parseError:
      case PredictionStatus.inferenceError:
      case PredictionStatus.unknownError:
        return _FailureBody(
          icon: Icons.wifi_off_rounded,
          iconColor: AppTheme.errorRed,
          title: 'Analysis Could Not Complete',
          message: widget.result.message ??
              'Something went wrong while analysing the image.',
          detail: null,
          reasons: const [],
          primaryLabel: 'Retry',
          onPrimary: _retryUpload,
        );

      case PredictionStatus.validationError:
      case PredictionStatus.invalidImage:
        return _FailureBody(
          icon: Icons.error_outline_rounded,
          iconColor: AppTheme.errorRed,
          title: 'Image Rejected',
          message: widget.result.message ??
              'The captured image was rejected by the server.',
          detail: null,
          reasons: const [],
          primaryLabel: 'Retake Image',
          onPrimary: _newScreening,
        );

      case PredictionStatus.notConfigured:
        return _FailureBody(
          icon: Icons.dns_rounded,
          iconColor: AppTheme.errorRed,
          title: 'Server Not Configured',
          message: widget.result.message ??
              'Set your screening server address in Account → Server Settings.',
          detail: null,
          reasons: const [],
          primaryLabel: 'Back to Home',
          onPrimary: _backHome,
        );
    }
  }
}

// ── Success / low-confidence report ───────────────────────

class _ReportBody extends StatelessWidget {
  final PredictionResult result;
  const _ReportBody({required this.result});

  String _prettyStatus(String s) =>
      s.isEmpty ? 'Unknown' : s.replaceAll('_', ' ').toLowerCase();

  Color _confidenceColor(String status) {
    switch (status.toUpperCase()) {
      case 'HIGH_CONFIDENCE':
        return AppTheme.successGreen;
      case 'MEDIUM_CONFIDENCE':
        return AppTheme.terracotta;
      default:
        return AppTheme.errorRed;
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = result.data!;
    final isLowConf = result.status == PredictionStatus.lowConfidence ||
        data.confidenceStatus.toUpperCase() == 'LOW_CONFIDENCE';
    final confColor = _confidenceColor(data.confidenceStatus);
    final qualityGood = data.quality.status.toUpperCase() == 'GOOD';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // ── Low-confidence warning banner ────────
        if (isLowConf) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.peach,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: AppTheme.terracotta.withValues(alpha: 0.3)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.warning_amber_rounded,
                        size: 18, color: AppTheme.terracotta),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Text(
                        'Low-confidence screening estimate',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.terracottaDark,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                const Padding(
                  padding: EdgeInsets.only(left: 28),
                  child: Text(
                    'The image/model result is uncertain. Consider '
                    'confirmatory blood testing.',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.terracottaDark,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],

        // ── Estimated Hb card (real model value) ──
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 32),
          decoration: BoxDecoration(
            color: AppTheme.surfaceWhite,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppTheme.divider),
          ),
          child: Column(
            children: [
              const Text(
                'Estimated Haemoglobin',
                style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.slateLight,
                    letterSpacing: 0.3),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    data.estimatedHb.toStringAsFixed(1),
                    style: const TextStyle(
                      fontSize: 56,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.slateInk,
                      letterSpacing: -2,
                      height: 1.0,
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8, left: 4),
                    child: Text(
                      data.unit,
                      style: const TextStyle(
                          fontSize: 16,
                          color: AppTheme.slateMid,
                          fontWeight: FontWeight.w500),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: confColor.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  'Confidence: ${_prettyStatus(data.confidenceStatus)}',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: confColor,
                  ),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // ── Simple screening checks ─────────────────
        Row(
          children: [
            Expanded(
              child: _MetricCard(
                label: ReportStrings.confidenceLabel,
                value: ReportStrings.confidenceDisplay(data.confidenceStatus),
                icon: Icons.check_circle_outline_rounded,
                color: confColor,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _MetricCard(
                label: 'Image Quality',
                value: data.quality.status.isEmpty
                    ? 'Unknown'
                    : _prettyStatus(data.quality.status),
                icon: Icons.image_search_rounded,
                color: qualityGood
                    ? AppTheme.successGreen
                    : AppTheme.terracotta,
              ),
            ),
          ],
        ),

        const SizedBox(height: 16),

        const Text(
          'Screening confidence tells you how suitable the result was based '
          'on the image and system checks.',
          style: TextStyle(
            fontSize: 12,
            color: AppTheme.slateLight,
            height: 1.5,
          ),
        ),

        const SizedBox(height: 16),

        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceWhite,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.divider),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: ReportStrings.interpretationLines(
              estimatedHb: data.estimatedHb,
              confidenceStatus: data.confidenceStatus,
              hbStd: data.hbStd,
            ).map(
              (line) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Text(
                  line,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.slateMid,
                    height: 1.55,
                  ),
                ),
              ),
            ).toList(),
          ),
        ),

        const SizedBox(height: 16),

        // ── Recommendation (verbatim from backend) ─
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfacePaper,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.divider),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline_rounded,
                  size: 16, color: AppTheme.terracotta),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Recommendation',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.slateLight,
                        letterSpacing: 0.4,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      data.recommendation.isEmpty
                          ? 'No recommendation returned by the server.'
                          : data.recommendation,
                      style: const TextStyle(
                          fontSize: 13,
                          color: AppTheme.slateMid,
                          height: 1.55),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        const SizedBox(height: 24),

        // ── Actions ─────────────────────────────
        ElevatedButton.icon(
          onPressed: () {
            Navigator.pushNamedAndRemoveUntil(
                context, '/camera', (r) => r.settings.name == '/main');
          },
          icon: const Icon(Icons.camera_alt_rounded, size: 18),
          label: const Text('New Screening'),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: () {
            Navigator.pushNamedAndRemoveUntil(context, '/main', (_) => false);
          },
          child: const Text('Back to Home'),
        ),

        const SizedBox(height: 24),

        // ── Disclaimer ──────────────────────────
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppTheme.surfaceWhite,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.divider),
          ),
          child: const Text(
            'This is an AI-based screening estimate for research/prototype '
            'use. It is not a clinical diagnosis or a replacement for '
            'confirmatory blood testing.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 11,
              color: AppTheme.slateLight,
              height: 1.55,
            ),
          ),
        ),
      ],
    );
  }
}

// ── Failure / status body ─────────────────────────────────

class _FailureBody extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String message;
  final String? detail;
  final List<String> reasons;
  final String? primaryLabel;
  final VoidCallback? onPrimary;

  const _FailureBody({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.message,
    required this.detail,
    required this.reasons,
    required this.primaryLabel,
    required this.onPrimary,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 40),
        Center(
          child: Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 38, color: iconColor),
          ),
        ),
        const SizedBox(height: 24),
        Text(
          title,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w800,
            color: AppTheme.slateInk,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 14,
            color: AppTheme.slateMid,
            height: 1.6,
          ),
        ),
        if (detail != null &&
            detail!.isNotEmpty &&
            detail != message) ...[
          const SizedBox(height: 8),
          Text(
            detail!,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 13,
              color: AppTheme.slateLight,
              height: 1.5,
            ),
          ),
        ],
        if (reasons.isNotEmpty) ...[
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.surfacePaper,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.divider),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Reported issues',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.slateLight,
                    letterSpacing: 0.4,
                  ),
                ),
                const SizedBox(height: 6),
                ...reasons.map(
                  (r) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ',
                            style: TextStyle(
                                fontSize: 13, color: AppTheme.slateMid)),
                        Expanded(
                          child: Text(
                            r,
                            style: const TextStyle(
                                fontSize: 13,
                                color: AppTheme.slateMid,
                                height: 1.45),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 36),
        if (primaryLabel != null && onPrimary != null)
          ElevatedButton.icon(
            onPressed: onPrimary,
            icon: Icon(
              primaryLabel == 'Retry'
                  ? Icons.refresh_rounded
                  : Icons.camera_alt_rounded,
              size: 18,
            ),
            label: Text(primaryLabel!),
          ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: () {
            Navigator.pushNamedAndRemoveUntil(context, '/main', (_) => false);
          },
          child: const Text('Back to Home'),
        ),
        const SizedBox(height: 24),
        const Text(
          'SCREENING ESTIMATE ONLY — NOT FOR CLINICAL DIAGNOSIS',
          textAlign: TextAlign.center,
          style: TextStyle(
              fontSize: 10,
              color: AppTheme.slateLight,
              letterSpacing: 0.5,
              fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

// ── Metric card ───────────────────────────────────────────

class _MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _MetricCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w800,
              color: color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              color: AppTheme.slateLight,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}