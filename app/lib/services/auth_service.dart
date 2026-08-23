import 'package:shared_preferences/shared_preferences.dart';
import 'consent_service.dart';

/// Mock OTP authentication service.
///
/// Accepts `123456` as the valid OTP for any phone number.
/// Persists login state via SharedPreferences.
/// Drop-in replaceable with Firebase Auth later.
class AuthService {
  static const String _kLoggedIn = 'is_logged_in';
  static const String _kPhoneNumber = 'phone_number';
  static const String _mockOtp = '123456';

  /// Simulate sending OTP. Always succeeds.
  Future<bool> sendOtp(String phoneNumber) async {
    // In production, this would call Firebase or an SMS gateway.
    await Future.delayed(const Duration(seconds: 1));
    return true;
  }

  /// Verify the OTP. Accepts `123456`.
  Future<bool> verifyOtp(String phoneNumber, String otp) async {
    await Future.delayed(const Duration(milliseconds: 800));
    if (otp == _mockOtp) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_kLoggedIn, true);
      await prefs.setString(_kPhoneNumber, phoneNumber);
      await ConsentService.instance.resetForLogin();
      return true;
    }
    return false;
  }

  /// Check if user is already logged in.
  Future<bool> isLoggedIn() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_kLoggedIn) ?? false;
  }

  /// Get stored phone number.
  Future<String?> getPhoneNumber() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_kPhoneNumber);
  }

  /// Log out.
  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kLoggedIn);
    await prefs.remove(_kPhoneNumber);
    await ConsentService.instance.clearForLogout();
  }
}
