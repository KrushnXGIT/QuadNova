import 'dart:io';

import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import '../core/report_strings.dart';
import '../services/report_pdf_service.dart';
import '../services/screening_history_service.dart';
import '../theme/app_theme.dart';

/// Displays a complete, user-friendly screening report for a single
/// historical [ScreeningRecord].
///
/// IMPORTANT:
/// – All values come from the stored [ScreeningRecord].
/// – No AI model is called. No Hb value is invented or recalculated.
/// – If [record.hasResult] is false the report shows "Screening not completed".
class ScreeningReportScreen extends StatefulWidget {
  final ScreeningRecord record;
  const ScreeningReportScreen({super.key, required this.record});

  @override
  State<ScreeningReportScreen> createState() => _ScreeningReportScreenState();
}

class _ScreeningReportScreenState extends State<ScreeningReportScreen> {
  bool _generatingPdf = false;

  // ── PDF generation ────────────────────────────────────────

  Future<void> _downloadReport({bool share = false}) async {
    if (_generatingPdf) return;
    setState(() => _generatingPdf = true);
    try {
      final File pdf =
          await ReportPdfService.generate(widget.record);
      if (!mounted) return;
      await Share.shareXFiles(
        [XFile(pdf.path)],
        subject: 'Anaemia Screening Report — ${widget.record.screeningId}',
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text(ReportStrings.pdfFailed),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) setState(() => _generatingPdf = false);
    }
  }

  // ── Build ─────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final record = widget.record;
    final dt = record.dateTime;

    final dateStr =
        '${_monthName(dt.month)} ${dt.day}, ${dt.year}';
    final timeStr =
        '${_pad(dt.hour)}:${_pad(dt.minute)} ${dt.hour < 12 ? "AM" : "PM"}';

    return Scaffold(
      backgroundColor: AppTheme.cream,
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceWhite,
        title: const Text(ReportStrings.reportTitle),
        actions: [
          IconButton(
            tooltip: 'Close',
            icon: const Icon(Icons.close_rounded),
            onPressed: () => Navigator.pop(context),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ── Header card ──────────────────────────────
              _HeaderCard(
                dateStr: dateStr,
                timeStr: timeStr,
                screeningId: record.screeningId,
              ),
              const SizedBox(height: 16),

              // ── Main result or failure ───────────────────
              if (!record.hasResult)
                _IncompleteCard()
              else ...[
                _HbCard(record: record),
                const SizedBox(height: 16),

                // ── What This Means ──────────────────────
                _SectionCard(
                  title: ReportStrings.whatThisMeans,
                  icon: Icons.lightbulb_outline_rounded,
                  child: _InterpretationText(record: record),
                ),
                const SizedBox(height: 16),

                // ── Next Step ────────────────────────────
                _SectionCard(
                  title: ReportStrings.nextStep,
                  icon: Icons.directions_walk_rounded,
                  child: Text(
                    record.recommendation.isEmpty
                        ? 'Consult a healthcare professional if you have any concerns.'
                        : record.recommendation,
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppTheme.slateMid,
                      height: 1.65,
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // ── Important ────────────────────────────
                _ImportantCard(),
                const SizedBox(height: 16),

                // ── Technical details (collapsed) ────────
                _TechnicalDetails(record: record),
                const SizedBox(height: 24),

                // ── Actions ──────────────────────────────
                _generatingPdf
                    ? const Center(
                        child: Padding(
                          padding: EdgeInsets.symmetric(vertical: 16),
                          child: CircularProgressIndicator(
                              color: AppTheme.terracotta),
                        ),
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          ElevatedButton.icon(
                            onPressed: _downloadReport,
                            style: ElevatedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(
                                  vertical: 16),
                            ),
                            icon: const Icon(Icons.download_rounded,
                                size: 20),
                            label: const Text(
                              ReportStrings.downloadReport,
                              style: TextStyle(fontSize: 16),
                            ),
                          ),
                          const SizedBox(height: 12),
                          OutlinedButton.icon(
                            onPressed: () => _downloadReport(share: true),
                            icon: const Icon(Icons.share_rounded, size: 18),
                            label: const Text(ReportStrings.shareReport),
                          ),
                        ],
                      ),
              ],

              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text(ReportStrings.backToHistory),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  static String _pad(int v) => v.toString().padLeft(2, '0');

  static String _monthName(int m) {
    const names = [
      '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    return names[m.clamp(1, 12)];
  }
}

// ─────────────────────────────────────────────────────────
// Header card
// ─────────────────────────────────────────────────────────

class _HeaderCard extends StatelessWidget {
  final String dateStr;
  final String timeStr;
  final String screeningId;

  const _HeaderCard({
    required this.dateStr,
    required this.timeStr,
    required this.screeningId,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        children: [
          // App name
          Text(
            ReportStrings.appName,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppTheme.slateLight,
              letterSpacing: 0.6,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            ReportStrings.reportTitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: AppTheme.slateInk,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 14),
          const Divider(color: AppTheme.divider),
          const SizedBox(height: 10),
          _InfoRow(label: ReportStrings.dateLabel, value: dateStr),
          const SizedBox(height: 6),
          _InfoRow(label: ReportStrings.timeLabel, value: timeStr),
          const SizedBox(height: 6),
          _InfoRow(
              label: ReportStrings.screeningIdLabel, value: screeningId),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: AppTheme.slateLight,
            fontWeight: FontWeight.w500,
          ),
        ),
        Text(
          value,
          style: const TextStyle(
            fontSize: 12,
            color: AppTheme.slateDeep,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────
// Main Hb result card
// ─────────────────────────────────────────────────────────

class _HbCard extends StatelessWidget {
  final ScreeningRecord record;
  const _HbCard({required this.record});

  @override
  Widget build(BuildContext context) {
    final conf = ReportStrings.confidenceDisplay(record.confidenceStatus);
    final qual = ReportStrings.qualityDisplay(record.imageQualityStatus);
    final isLow =
        record.confidenceStatus.toUpperCase() == 'LOW_CONFIDENCE';

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        children: [
          // Label
          const Text(
            ReportStrings.estimatedHb,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.slateLight,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 10),

          // Large Hb value — neutral colour, no traffic-light semantics
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                record.estimatedHb.toStringAsFixed(1),
                style: const TextStyle(
                  fontSize: 64,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.slateInk,
                  letterSpacing: -2,
                  height: 1.0,
                ),
              ),
              const Padding(
                padding: EdgeInsets.only(bottom: 9, left: 5),
                child: Text(
                  ReportStrings.unit,
                  style: TextStyle(
                    fontSize: 18,
                    color: AppTheme.slateMid,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            ReportStrings.screeningEstimate,
            style: TextStyle(fontSize: 11, color: AppTheme.slateLight),
          ),
          const SizedBox(height: 14),

          // Confidence + quality chips — muted, not traffic-light
          Wrap(
            spacing: 10,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: [
              _Chip(
                icon: isLow
                    ? Icons.warning_amber_rounded
                    : Icons.check_circle_outline_rounded,
                label:
                    '${ReportStrings.confidenceLabel}: $conf',
                color: isLow ? AppTheme.terracotta : AppTheme.slateMid,
              ),
              _Chip(
                icon: Icons.image_search_rounded,
                label: '${ReportStrings.imageQualityLabel}: $qual',
                color: AppTheme.slateMid,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  const _Chip(
      {required this.icon, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding:
          const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.15)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Interpretation text (plain language, non-clinical)
// ─────────────────────────────────────────────────────────

class _InterpretationText extends StatelessWidget {
  final ScreeningRecord record;
  const _InterpretationText({required this.record});

  @override
  Widget build(BuildContext context) {
    final lines = <String>[];

    // Sentence 1: what the result is
    lines.add(
        'Your estimated haemoglobin level is '
        '${record.estimatedHb.toStringAsFixed(1)} g/dL.');

    // Sentence 2: confidence context
    final cs = record.confidenceStatus.toUpperCase();
    if (cs == 'HIGH_CONFIDENCE') {
      lines.add(ReportStrings.interpHighConf);
    } else if (cs == 'MEDIUM_CONFIDENCE') {
      lines.add(ReportStrings.interpMedConf);
    } else {
      // LOW_CONFIDENCE or unknown
      lines.add(ReportStrings.interpLowConf);
    }

    // Sentence 3: unusually high uncertainty flag
    if (record.hbStd > 1.5) {
      lines.add(ReportStrings.interpHighUncertainty);
    }

    // Sentence 4: low Hb nudge (non-clinical — just a "may suggest" nudge)
    if (record.estimatedHb < 10.0 && cs != 'LOW_CONFIDENCE') {
      lines.add(ReportStrings.interpLowHb);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: lines
          .map(
            (line) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text(
                line,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.slateMid,
                  height: 1.65,
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Generic section card
// ─────────────────────────────────────────────────────────

class _SectionCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;
  const _SectionCard(
      {required this.title, required this.icon, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: AppTheme.terracotta),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.slateDeep,
                  letterSpacing: 0.1,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Important / disclaimer card
// ─────────────────────────────────────────────────────────

class _ImportantCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.peach,
        borderRadius: BorderRadius.circular(14),
        border:
            Border.all(color: AppTheme.terracotta.withValues(alpha: 0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline_rounded,
              size: 18, color: AppTheme.terracotta),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  ReportStrings.importantNote,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.terracottaDark,
                    letterSpacing: 0.3,
                  ),
                ),
                const SizedBox(height: 5),
                const Text(
                  ReportStrings.disclaimer,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.terracottaDark,
                    height: 1.6,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// Technical details (collapsed expansion tile)
// ─────────────────────────────────────────────────────────

class _TechnicalDetails extends StatelessWidget {
  final ScreeningRecord record;
  const _TechnicalDetails({required this.record});

  @override
  Widget build(BuildContext context) {
    final ci = record.confidenceInterval95;
    final rows = <_TechRow>[
      _TechRow(
          label: ReportStrings.screeningIdLabel,
          value: record.screeningId),
      if (record.modelName.isNotEmpty)
        _TechRow(
            label: ReportStrings.modelLabel,
            value: record.modelName),
      if (record.modelVersion.isNotEmpty)
        _TechRow(
            label: ReportStrings.modelVersionLabel,
            value: record.modelVersion),
      if (record.hbStd > 0)
        _TechRow(
            label: ReportStrings.uncertaintyLabel,
            value:
                '±${record.hbStd.toStringAsFixed(2)} ${ReportStrings.unit}'),
      if (ci.length == 2)
        _TechRow(
            label: ReportStrings.ciLabel,
            value:
                '${ci[0].toStringAsFixed(1)} – ${ci[1].toStringAsFixed(1)} '
                '${ReportStrings.unit}'),
      _TechRow(
          label: ReportStrings.confidenceLabel,
          value: ReportStrings.confidenceDisplay(record.confidenceStatus)),
      _TechRow(
          label: ReportStrings.imageQualityLabel,
          value: ReportStrings.qualityDisplay(record.imageQualityStatus)),
    ];

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.divider),
      ),
      clipBehavior: Clip.hardEdge,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding:
              const EdgeInsets.symmetric(horizontal: 18, vertical: 2),
          childrenPadding: const EdgeInsets.fromLTRB(18, 0, 18, 16),
          leading: const Icon(Icons.science_outlined,
              size: 18, color: AppTheme.slateLight),
          title: const Text(
            ReportStrings.technicalDetails,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.slateMid,
            ),
          ),
          children: [
            const Divider(color: AppTheme.divider),
            const SizedBox(height: 8),
            ...rows.map((r) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(r.label,
                          style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.slateLight)),
                      Flexible(
                        child: Text(r.value,
                            textAlign: TextAlign.end,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.slateDeep,
                            )),
                      ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }
}

class _TechRow {
  final String label;
  final String value;
  const _TechRow({required this.label, required this.value});
}

// ─────────────────────────────────────────────────────────
// Incomplete / failed screening placeholder
// ─────────────────────────────────────────────────────────

class _IncompleteCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: AppTheme.slateLight.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.block_rounded,
                size: 32, color: AppTheme.slateLight),
          ),
          const SizedBox(height: 16),
          const Text(
            ReportStrings.screeningNotCompleted,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: AppTheme.slateInk,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            ReportStrings.screeningNotCompletedDetail,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              color: AppTheme.slateMid,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }
}
