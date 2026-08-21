/// Runtime API configuration shared by the Flutter client.
class ApiConfig {
  ApiConfig._();

  /// Empty by default; ServerSetupScreen stores the developer's URL at runtime.
  static const String defaultBaseUrl = '';

  /// Android emulator loopback address for local backend development.
  static const String androidEmulatorBaseUrl = 'http://10.0.2.2:8000';
}
