import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

/// Result screen shown after backend analysis completes.
class ResultScreen extends StatelessWidget {
  final PredictionResult result;

  const ResultScreen({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      appBar: AppBar(
        backgroundColor: AppTheme.cream,
        automaticallyImplyLeading: false,
        title: const Text('Screening Result'),
        actions: [
          IconButton(
            icon: const Icon(Icons.close_rounded),
            onPressed: () =>
                Navigator.pushNamedAndRemoveUntil(
                    context, '/main', (_) => false),
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
    switch (result.status) {
      case PredictionStatus.predictionComplete:
      case PredictionStatus.lowConfidence:
        return _SuccessBody(result: result);
      case PredictionStatus.imageQualityFailed:
      case PredictionStatus.roiFailed:
        return _StatusBody(
          icon: Icons.camera_alt_rounded,
          iconColor: AppTheme.terracotta,
          title: result.status == PredictionStatus.roiFailed
              ? 'Eye Region Not Detected'
              : 'Image Quality Insufficient',
          subtitle: result.message ??
              'The image did not meet quality requirements. Please retake.',
          canRetry: true,
        );
      case PredictionStatus.modelNotReady:
        return _StatusBody(
          icon: Icons.hourglass_bottom_rounded,
          iconColor: AppTheme.slateLight,
          title: 'AI Model Not Available',
          subtitle:
              'The screening model is not yet integrated. This will be enabled once the trained model is available.',
          canRetry: false,
        );
      case PredictionStatus.networkError:
        return _StatusBody(
          icon: Icons.wifi_off_rounded,
          iconColor: AppTheme.errorRed,
          title: 'Cannot Reach Server',
          subtitle: result.message ??
              'Make sure your phone and computer are on the same Wi-Fi network.',
          canRetry: true,
        );
      default:
        return _StatusBody(
          icon: Icons.error_outline_rounded,
          iconColor: AppTheme.errorRed,
          title: 'Something Went Wrong',
          subtitle: result.message ?? 'Please try again.',
          canRetry: true,
        );
    }
  }
}

// ── Success / Low Confidence body ─────────────────────────

class _SuccessBody extends StatelessWidget {
  final PredictionResult result;
  const _SuccessBody({required this.result});

  @override
  Widget build(BuildContext context) {
    final data = result.data!;
    final isLowConf =
        result.status == PredictionStatus.lowConfidence ||
            data.confidenceStatus == 'LOW_CONFIDENCE';
    final hb = data.estimatedHb;

    // Hb interpretation
    final String hbLabel;
    final Color hbColor;
    if (hb < 8.0) {
      hbLabel = 'Severely Low';
      hbColor = AppTheme.errorRed;
    } else if (hb < 11.0) {
      hbLabel = 'Low';
      hbColor = const Color(0xFFE07B2A);
    } else if (hb < 12.0) {
      hbLabel = 'Borderline';
      hbColor = AppTheme.terracotta;
    } else {
      hbLabel = 'Normal Range';
      hbColor = AppTheme.successGreen;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // ── Low confidence warning ──────────────
        if (isLowConf) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.peach,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: AppTheme.terracotta.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                Icon(Icons.warning_amber_rounded,
                    size: 18, color: AppTheme.terracotta),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text(
                    'Low confidence result — consider retaking.',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.terracottaDark,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
        ],

        // ── Hb value card ───────────────────────
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
              Text(
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
                    hb.toStringAsFixed(1),
                    style: TextStyle(
                      fontSize: 56,
                      fontWeight: FontWeight.w800,
                      color: hbColor,
                      letterSpacing: -2,
                      height: 1.0,
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8, left: 4),
                    child: Text(
                      data.unit,
                      style: TextStyle(
                          fontSize: 16,
                          color: AppTheme.slateMid,
                          fontWeight: FontWeight.w500),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: hbColor.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  hbLabel,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: hbColor,
                  ),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // ── Metrics row ─────────────────────────
        Row(
          children: [
            Expanded(
              child: _MetricCard(
                label: 'Confidence',
                value: data.confidenceStatus
                    .replaceAll('_', ' ')
                    .toLowerCase(),
                icon: Icons.verified_outlined,
                color: data.confidenceStatus == 'HIGH_CONFIDENCE'
                    ? AppTheme.successGreen
                    : AppTheme.terracotta,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _MetricCard(
                label: 'Image Quality',
                value: data.quality.status,
                icon: Icons.image_search_rounded,
                color: data.quality.status == 'GOOD'
                    ? AppTheme.successGreen
                    : AppTheme.terracotta,
              ),
            ),
          ],
        ),

        const SizedBox(height: 16),

        if (data.confidenceInterval95.length == 2) ...[
          _MetricCard(
            label: 'Uncertainty',
            value:
                '95% CI ${data.confidenceInterval95[0].toStringAsFixed(1)}-${data.confidenceInterval95[1].toStringAsFixed(1)} ${data.unit}',
            icon: Icons.query_stats_rounded,
            color: AppTheme.slateMid,
          ),
          const SizedBox(height: 16),
        ],

        // ── Recommendation ──────────────────────
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
                child: Text(
                  data.recommendation,
                  style: const TextStyle(
                      fontSize: 13,
                      color: AppTheme.slateMid,
                      height: 1.55),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        // ── Actions ─────────────────────────────
        ElevatedButton.icon(
          onPressed: () =>
              Navigator.pushNamedAndRemoveUntil(
                  context, '/camera', (r) => r.settings.name == '/main'),
          icon: const Icon(Icons.camera_alt_rounded, size: 18),
          label: const Text('Scan Again'),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: () =>
              Navigator.pushNamedAndRemoveUntil(
                  context, '/main', (_) => false),
          child: const Text('Back to Home'),
        ),

        const SizedBox(height: 24),

        // ── Disclaimer ──────────────────────────
        Text(
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

// ── Error / Status body ───────────────────────────────────

class _StatusBody extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final bool canRetry;

  const _StatusBody({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.canRetry,
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
          subtitle,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 14,
            color: AppTheme.slateMid,
            height: 1.6,
          ),
        ),
        const SizedBox(height: 36),
        if (canRetry)
          ElevatedButton.icon(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.refresh_rounded, size: 18),
            label: const Text('Try Again'),
          ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: () =>
              Navigator.pushNamedAndRemoveUntil(
                  context, '/main', (_) => false),
          child: const Text('Back to Home'),
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
