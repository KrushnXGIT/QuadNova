import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../core/report_strings.dart';
import 'screening_history_service.dart';

/// Generates a structured PDF for a single [ScreeningRecord].
///
/// IMPORTANT:
/// – Uses only data stored in [record]. No API call, no AI re-run.
/// – Saves to the device's temporary directory (no storage permission needed
///   on Android 10+ when combined with share_plus).
/// – Filename: `Anaemia_Screening_Report_<screeningId>.pdf`
class ReportPdfService {
  ReportPdfService._();

  static Future<File> generate(ScreeningRecord record) async {
    final doc = pw.Document(
      title: '${ReportStrings.reportTitle} — ${record.screeningId}',
      author: ReportStrings.appName,
    );

    doc.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(36),
        header: (_) => _buildPageHeader(),
        footer: (ctx) => _buildPageFooter(ctx),
        build: (ctx) => [
          _sectionSpacer(),
          _buildReportHeader(record),
          _sectionSpacer(),
          _divider(),
          _sectionSpacer(),
          if (!record.hasResult)
            _buildIncomplete()
          else ...[
            _buildHbSection(record),
            _sectionSpacer(),
            _divider(),
            _sectionSpacer(),
            _buildWhatThisMeans(record),
            _sectionSpacer(),
            _divider(),
            _sectionSpacer(),
            _buildNextStep(record),
            _sectionSpacer(),
            _divider(),
            _sectionSpacer(),
            _buildImportant(),
            _sectionSpacer(),
            _divider(),
            _sectionSpacer(),
            _buildTechnicalDetails(record),
          ],
          _sectionSpacer(),
        ],
      ),
    );

    final dir = await getTemporaryDirectory();
    final filename =
        'Anaemia_Screening_Report_${record.screeningId}.pdf';
    final file = File('${dir.path}/$filename');
    await file.writeAsBytes(await doc.save());
    return file;
  }

  // ── Page header / footer ──────────────────────────────────

  static pw.Widget _buildPageHeader() {
    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.stretch,
      children: [
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Text(
              ReportStrings.appName,
              style: pw.TextStyle(
                fontSize: 9,
                color: PdfColors.grey600,
                fontWeight: pw.FontWeight.bold,
              ),
            ),
            pw.Text(
              'SCREENING ESTIMATE ONLY',
              style: const pw.TextStyle(
                fontSize: 8,
                color: PdfColors.grey500,
              ),
            ),
          ],
        ),
        pw.SizedBox(height: 4),
        pw.Divider(color: PdfColors.grey300, thickness: 0.5),
      ],
    );
  }

  static pw.Widget _buildPageFooter(pw.Context ctx) {
    final now = DateTime.now();
    final dateStr =
        '${now.day.toString().padLeft(2, '0')}/'
        '${now.month.toString().padLeft(2, '0')}/'
        '${now.year}';
    return pw.Column(
      children: [
        pw.Divider(color: PdfColors.grey300, thickness: 0.5),
        pw.SizedBox(height: 4),
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Text(
              '${ReportStrings.pdfFooterPrefix} $dateStr',
              style: const pw.TextStyle(
                  fontSize: 8, color: PdfColors.grey500),
            ),
            pw.Text(
              'Page ${ctx.pageNumber} of ${ctx.pagesCount}',
              style: const pw.TextStyle(
                  fontSize: 8, color: PdfColors.grey500),
            ),
          ],
        ),
      ],
    );
  }

  // ── Report header section ─────────────────────────────────

  static pw.Widget _buildReportHeader(ScreeningRecord record) {
    final dt = record.dateTime;
    final dateStr =
        '${dt.day.toString().padLeft(2, '0')}/'
        '${dt.month.toString().padLeft(2, '0')}/'
        '${dt.year}';
    final hour = dt.hour;
    final timeStr =
        '${hour.toString().padLeft(2, '0')}:'
        '${dt.minute.toString().padLeft(2, '0')} '
        '${hour < 12 ? "AM" : "PM"}';

    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.center,
      children: [
        pw.Text(
          ReportStrings.reportTitle.toUpperCase(),
          textAlign: pw.TextAlign.center,
          style: pw.TextStyle(
            fontSize: 18,
            fontWeight: pw.FontWeight.bold,
            color: PdfColors.grey800,
          ),
        ),
        pw.SizedBox(height: 12),
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.center,
          children: [
            _labelValue(ReportStrings.dateLabel, dateStr),
            pw.SizedBox(width: 24),
            _labelValue(ReportStrings.timeLabel, timeStr),
            pw.SizedBox(width: 24),
            _labelValue(
                ReportStrings.screeningIdLabel, record.screeningId),
          ],
        ),
      ],
    );
  }

  // ── Hb result section ─────────────────────────────────────

  static pw.Widget _buildHbSection(ScreeningRecord record) {
    final conf = ReportStrings.confidenceDisplay(record.confidenceStatus);
    final qual =
        ReportStrings.qualityDisplay(record.imageQualityStatus);

    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.center,
      children: [
        pw.Text(
          ReportStrings.estimatedHb.toUpperCase(),
          style: const pw.TextStyle(
            fontSize: 10,
            color: PdfColors.grey600,
          ),
        ),
        pw.SizedBox(height: 8),
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.center,
          crossAxisAlignment: pw.CrossAxisAlignment.end,
          children: [
            pw.Text(
              record.estimatedHb.toStringAsFixed(1),
              style: pw.TextStyle(
                fontSize: 52,
                fontWeight: pw.FontWeight.bold,
                color: PdfColors.grey900,
              ),
            ),
            pw.Padding(
              padding: const pw.EdgeInsets.only(bottom: 8, left: 4),
              child: pw.Text(
                ReportStrings.unit,
                style: pw.TextStyle(
                  fontSize: 18,
                  fontWeight: pw.FontWeight.bold,
                  color: PdfColors.grey600,
                ),
              ),
            ),
          ],
        ),
        pw.SizedBox(height: 4),
        pw.Text(
          ReportStrings.screeningEstimate,
          style: const pw.TextStyle(
              fontSize: 9, color: PdfColors.grey500),
        ),
        pw.SizedBox(height: 12),
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.center,
          children: [
            _chip(
                '${ReportStrings.confidenceLabel}: $conf'),
            pw.SizedBox(width: 12),
            _chip(
                '${ReportStrings.imageQualityLabel}: $qual'),
          ],
        ),
      ],
    );
  }

  // ── What This Means ───────────────────────────────────────

  static pw.Widget _buildWhatThisMeans(ScreeningRecord record) {
    final cs = record.confidenceStatus.toUpperCase();
    final lines = <String>[
      'Your estimated haemoglobin level is '
          '${record.estimatedHb.toStringAsFixed(1)} g/dL.',
    ];

    if (cs == 'HIGH_CONFIDENCE') {
      lines.add(ReportStrings.interpHighConf);
    } else if (cs == 'MEDIUM_CONFIDENCE') {
      lines.add(ReportStrings.interpMedConf);
    } else {
      lines.add(ReportStrings.interpLowConf);
    }
    if (record.hbStd > 1.5) {
      lines.add(ReportStrings.interpHighUncertainty);
    }
    if (record.estimatedHb < 10.0 && cs != 'LOW_CONFIDENCE') {
      lines.add(ReportStrings.interpLowHb);
    }

    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.start,
      children: [
        _sectionTitle(ReportStrings.whatThisMeans),
        pw.SizedBox(height: 6),
        ...lines.map(
          (l) => pw.Padding(
            padding: const pw.EdgeInsets.only(bottom: 6),
            child: pw.Text(l,
                style: const pw.TextStyle(
                    fontSize: 11, color: PdfColors.grey700, lineSpacing: 2)),
          ),
        ),
      ],
    );
  }

  // ── Next step ─────────────────────────────────────────────

  static pw.Widget _buildNextStep(ScreeningRecord record) {
    final rec = record.recommendation.isEmpty
        ? 'Consult a healthcare professional if you have any concerns.'
        : record.recommendation;
    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.start,
      children: [
        _sectionTitle(ReportStrings.nextStep),
        pw.SizedBox(height: 6),
        pw.Text(rec,
            style: const pw.TextStyle(
                fontSize: 11, color: PdfColors.grey700, lineSpacing: 2)),
      ],
    );
  }

  // ── Important disclaimer ──────────────────────────────────

  static pw.Widget _buildImportant() {
    return pw.Container(
      padding: const pw.EdgeInsets.all(12),
      decoration: pw.BoxDecoration(
        border: pw.Border.all(color: PdfColors.orange200),
        borderRadius: const pw.BorderRadius.all(pw.Radius.circular(6)),
        color: PdfColors.orange50,
      ),
      child: pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.start,
        children: [
          pw.Text(
            ReportStrings.importantNote.toUpperCase(),
            style: pw.TextStyle(
              fontSize: 9,
              fontWeight: pw.FontWeight.bold,
              color: PdfColors.orange800,
            ),
          ),
          pw.SizedBox(height: 4),
          pw.Text(
            ReportStrings.pdfDisclaimer,
            style: const pw.TextStyle(
                fontSize: 10, color: PdfColors.orange900, lineSpacing: 2),
          ),
        ],
      ),
    );
  }

  // ── Technical details ─────────────────────────────────────

  static pw.Widget _buildTechnicalDetails(ScreeningRecord record) {
    final ci = record.confidenceInterval95;
    final rows = <List<String>>[
      [ReportStrings.screeningIdLabel, record.screeningId],
      if (record.modelName.isNotEmpty)
        [ReportStrings.modelLabel, record.modelName],
      if (record.modelVersion.isNotEmpty)
        [ReportStrings.modelVersionLabel, record.modelVersion],
      if (record.hbStd > 0)
        [
          ReportStrings.uncertaintyLabel,
          '±${record.hbStd.toStringAsFixed(2)} ${ReportStrings.unit}'
        ],
      if (ci.length == 2)
        [
          ReportStrings.ciLabel,
          '${ci[0].toStringAsFixed(1)} – ${ci[1].toStringAsFixed(1)} ${ReportStrings.unit}'
        ],
      [
        ReportStrings.confidenceLabel,
        ReportStrings.confidenceDisplay(record.confidenceStatus)
      ],
      [
        ReportStrings.imageQualityLabel,
        ReportStrings.qualityDisplay(record.imageQualityStatus)
      ],
    ];

    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.start,
      children: [
        _sectionTitle(ReportStrings.technicalDetails),
        pw.SizedBox(height: 6),
        pw.Table(
          border: pw.TableBorder.all(color: PdfColors.grey200, width: 0.5),
          children: rows
              .map(
                (row) => pw.TableRow(
                  children: [
                    pw.Padding(
                      padding: const pw.EdgeInsets.all(6),
                      child: pw.Text(row[0],
                          style: const pw.TextStyle(
                              fontSize: 9, color: PdfColors.grey600)),
                    ),
                    pw.Padding(
                      padding: const pw.EdgeInsets.all(6),
                      child: pw.Text(row[1],
                          style: pw.TextStyle(
                            fontSize: 9,
                            fontWeight: pw.FontWeight.bold,
                            color: PdfColors.grey800,
                          )),
                    ),
                  ],
                ),
              )
              .toList(),
        ),
      ],
    );
  }

  // ── Incomplete screening ──────────────────────────────────

  static pw.Widget _buildIncomplete() {
    return pw.Center(
      child: pw.Column(
        children: [
          pw.SizedBox(height: 24),
          pw.Text(
            ReportStrings.screeningNotCompleted,
            style: pw.TextStyle(
              fontSize: 16,
              fontWeight: pw.FontWeight.bold,
              color: PdfColors.grey700,
            ),
          ),
          pw.SizedBox(height: 8),
          pw.Text(
            ReportStrings.screeningNotCompletedDetail,
            textAlign: pw.TextAlign.center,
            style: const pw.TextStyle(
                fontSize: 11, color: PdfColors.grey600, lineSpacing: 2),
          ),
        ],
      ),
    );
  }

  // ── Shared helpers ────────────────────────────────────────

  static pw.Widget _sectionTitle(String text) => pw.Text(
        text.toUpperCase(),
        style: pw.TextStyle(
          fontSize: 10,
          fontWeight: pw.FontWeight.bold,
          color: PdfColors.grey700,
          letterSpacing: 0.5,
        ),
      );

  static pw.Widget _labelValue(String label, String value) => pw.Column(
        children: [
          pw.Text(label,
              style: const pw.TextStyle(
                  fontSize: 8, color: PdfColors.grey500)),
          pw.SizedBox(height: 2),
          pw.Text(value,
              style: pw.TextStyle(
                fontSize: 10,
                fontWeight: pw.FontWeight.bold,
                color: PdfColors.grey800,
              )),
        ],
      );

  static pw.Widget _chip(String label) => pw.Container(
        padding:
            const pw.EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: pw.BoxDecoration(
          border:
              pw.Border.all(color: PdfColors.grey300, width: 0.5),
          borderRadius:
              const pw.BorderRadius.all(pw.Radius.circular(10)),
          color: PdfColors.grey100,
        ),
        child: pw.Text(label,
            style: const pw.TextStyle(
                fontSize: 9, color: PdfColors.grey700)),
      );

  static pw.Widget _divider() =>
      pw.Divider(color: PdfColors.grey200, thickness: 0.5);

  static pw.Widget _sectionSpacer() => pw.SizedBox(height: 14);
}
