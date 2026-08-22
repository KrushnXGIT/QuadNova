import 'package:flutter_test/flutter_test.dart';
import 'package:anaemia_screening_app/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('App renders splash screen on launch',
      (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const HemoScanApp());

    // Splash branding is visible. The app name is rendered as two
    // RichText spans ('HemoScan' + ' AI'), so match the plain-text
    // widgets that actually exist on screen.
    expect(find.text('by QuadNova'), findsOneWidget);
    expect(find.text('Non-Invasive Haemoglobin Estimation'), findsOneWidget);

    // Advance past the splash's 2.4s auto-navigation timer so no timers
    // remain pending when the test ends, then let the auth screen settle.
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    expect(find.text('Send OTP'), findsOneWidget);
  });
}