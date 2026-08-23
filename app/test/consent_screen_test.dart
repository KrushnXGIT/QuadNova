import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:anaemia_screening_app/screens/consent_screen.dart';
import 'package:anaemia_screening_app/services/auth_service.dart';
import 'package:anaemia_screening_app/services/consent_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('Continue is disabled until consent is checked', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ConsentScreen()));

    final continueButton = tester.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Continue'),
    );
    expect(continueButton.onPressed, isNull);

    await tester.tap(find.byType(Checkbox));
    await tester.pump();

    final enabledButton = tester.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Continue'),
    );
    expect(enabledButton.onPressed, isNotNull);
  });

  test('successful login starts a new consent session', () async {
    SharedPreferences.setMockInitialValues({});
    final service = ConsentService.instance;
    await service.saveCurrentConsent();
    expect(await service.getCurrentConsent(), isNotNull);

    expect(await AuthService().verifyOtp('+911234567890', '123456'), isTrue);
    expect(await service.getCurrentConsent(), isNull);
  });

  test('logout clears consent without removing other local data', () async {
    SharedPreferences.setMockInitialValues({'screening_history': 'retained'});
    final service = ConsentService.instance;
    await service.saveCurrentConsent();

    await AuthService().logout();
    expect(await service.getCurrentConsent(), isNull);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('screening_history'), 'retained');
  });
}