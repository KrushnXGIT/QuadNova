import 'package:flutter_test/flutter_test.dart';
import 'package:anaemia_screening_app/main.dart';

void main() {
  testWidgets('App renders splash screen on launch',
      (WidgetTester tester) async {
    await tester.pumpWidget(const HemoScanApp());

    // Splash branding is visible.
    expect(find.text('HemoScan AI'), findsOneWidget);
    expect(find.text('by QuadNova'), findsOneWidget);
  });
}
