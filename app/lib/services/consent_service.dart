import 'package:shared_preferences/shared_preferences.dart';

import '../core/consent_strings.dart';

/// Stores acknowledgement for the current authenticated login session.
class ConsentService {
  ConsentService._();
  static final ConsentService instance = ConsentService._();

  static const String _givenKey = 'consent_given';
  static const String _versionKey = 'consent_version';
  static const String _timestampKey = 'consent_timestamp';

  Future<void> resetForLogin() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_givenKey, false);
    await prefs.remove(_versionKey);
    await prefs.remove(_timestampKey);
  }

  Future<void> clearForLogout() => resetForLogin();

  Future<ConsentGrant?> getCurrentConsent() async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_givenKey) != true ||
        prefs.getString(_versionKey) != ConsentStrings.version) {
      return null;
    }

    final rawTimestamp = prefs.getString(_timestampKey);
    final timestamp = rawTimestamp == null
        ? null
        : DateTime.tryParse(rawTimestamp);
    if (timestamp == null) return null;

    return ConsentGrant(
      version: ConsentStrings.version,
      timestamp: timestamp,
    );
  }

  Future<ConsentGrant> saveCurrentConsent() async {
    final timestamp = DateTime.now();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_givenKey, true);
    await prefs.setString(_versionKey, ConsentStrings.version);
    await prefs.setString(_timestampKey, timestamp.toIso8601String());
    return ConsentGrant(version: ConsentStrings.version, timestamp: timestamp);
  }
}

class ConsentGrant {
  final String version;
  final DateTime timestamp;

  const ConsentGrant({required this.version, required this.timestamp});
}
