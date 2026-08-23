import 'package:flutter_test/flutter_test.dart';
import 'package:anaemia_screening_app/core/report_strings.dart';

void main() {
  test('uses Case 3 wording for a low estimate without classifying it', () {
    final lines = ReportStrings.interpretationLines(
      estimatedHb: 9.1,
      confidenceStatus: 'HIGH_CONFIDENCE',
      hbStd: 0.4,
    ).join(' ');

    expect(lines, contains('Estimated haemoglobin: 9.1 g/dL.'));
    expect(lines, contains(ReportStrings.noClinicalInterpretation));
    expect(lines, contains(ReportStrings.interpretationConfirmation));
    expect(lines.toLowerCase(), isNot(contains('anaemia')));
    expect(lines.toLowerCase(), isNot(contains('normal')));
  });

  test('does not turn a higher estimate into a clinical classification', () {
    final lines = ReportStrings.interpretationLines(
      estimatedHb: 13.2,
      confidenceStatus: 'MEDIUM_CONFIDENCE',
      hbStd: 0.7,
    ).join(' ');

    expect(lines, contains('Estimated haemoglobin: 13.2 g/dL.'));
    expect(lines, contains(ReportStrings.noClinicalInterpretation));
    expect(lines.toLowerCase(), isNot(contains('anaemia')));
    expect(lines.toLowerCase(), isNot(contains('normal')));
  });
}
