import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../core/config/api_config.dart';

/// HemoScan AI — backend API service.
///
/// The base URL is configured by the user at runtime and stored in
/// SharedPreferences. Works on any WiFi — no hardcoded IPs.
class ApiService {
  ApiService._();
  static final ApiService instance = ApiService._();

  static const String _prefKey = 'backend_url';
  static const String kDefaultUrl = ApiConfig.defaultBaseUrl;
  static const Duration _timeout = Duration(seconds: 30);

  // ── URL management ────────────────────────────────────────

  Future<String> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_prefKey) ?? '';
  }

  Future<void> setBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    final clean = url.trim().replaceAll(RegExp(r'/$'), '');
    await prefs.setString(_prefKey, clean);
  }

  Future<bool> isConfigured() async {
    final url = await getBaseUrl();
    return url.isNotEmpty;
  }

  Future<void> clearUrl() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefKey);
  }

  // ── Endpoints ─────────────────────────────────────────────

  /// POST /api/v1/predict — upload image and get Hb prediction.
  Future<PredictionResult> predict(File imageFile) async {
    final base = await getBaseUrl();
    if (base.isEmpty) return PredictionResult.notConfigured();

    final uri = Uri.parse('$base/api/v1/predict');
    try {
      final request = http.MultipartRequest('POST', uri)
        ..files.add(
          await http.MultipartFile.fromPath('image', imageFile.path),
        );
      final streamed = await request.send().timeout(_timeout);
      final body = await streamed.stream.bytesToString();
      final json = jsonDecode(body) as Map<String, dynamic>;
      return PredictionResult.fromJson(json);
    } on SocketException {
      return PredictionResult.networkError();
    } on HttpException {
      return PredictionResult.networkError();
    } on FormatException {
      return PredictionResult.parseError();
    } catch (_) {
      return PredictionResult.networkError();
    }
  }

  /// GET /health — returns true if server is reachable.
  Future<bool> checkHealth([String? overrideUrl]) async {
    final base = overrideUrl ?? await getBaseUrl();
    if (base.isEmpty) return false;
    try {
      final res = await http
          .get(Uri.parse('$base/health'))
          .timeout(const Duration(seconds: 6));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// GET /api/v1/model/status
  Future<ModelStatus> getModelStatus() async {
    final base = await getBaseUrl();
    if (base.isEmpty) {
      return const ModelStatus(available: false, status: 'NOT_CONFIGURED');
    }
    try {
      final res = await http
          .get(Uri.parse('$base/api/v1/model/status'))
          .timeout(const Duration(seconds: 6));
      final json = jsonDecode(res.body) as Map<String, dynamic>;
      return ModelStatus.fromJson(json);
    } catch (_) {
      return const ModelStatus(available: false, status: 'UNREACHABLE');
    }
  }
}

// ── Response models ───────────────────────────────────────

enum PredictionStatus {
  predictionComplete,
  lowConfidence,
  imageQualityFailed,
  roiFailed,
  modelNotReady,
  networkError,
  notConfigured,
  parseError,
  unknownError,
}

class QualityResult {
  final String status;
  final double score;
  const QualityResult({required this.status, required this.score});
  factory QualityResult.fromJson(Map<String, dynamic> j) => QualityResult(
        status: j['status'] as String? ?? '',
        score: (j['score'] as num?)?.toDouble() ?? 0.0,
      );
}

class PredictionData {
  final double estimatedHb;
  final String unit;
  final double hbStd;
  final List<double> confidenceInterval95;
  final String confidenceStatus;
  final QualityResult quality;
  final String recommendation;
  const PredictionData({
    required this.estimatedHb,
    required this.unit,
    required this.hbStd,
    required this.confidenceInterval95,
    required this.confidenceStatus,
    required this.quality,
    required this.recommendation,
  });
  factory PredictionData.fromJson(Map<String, dynamic> j) {
    final interval = (j['confidence_interval_95'] as List<dynamic>? ?? [])
        .whereType<num>()
        .map((v) => v.toDouble())
        .toList();
    return PredictionData(
      estimatedHb: (j['estimated_hb_g_dl'] as num).toDouble(),
      unit: 'g/dL',
      hbStd: (j['hb_std_g_dl'] as num?)?.toDouble() ?? 0.0,
      confidenceInterval95: interval,
      confidenceStatus: j['confidence_status'] as String? ?? 'UNKNOWN',
      quality: QualityResult.fromJson(
          j['image_quality'] as Map<String, dynamic>? ?? {}),
      recommendation: j['recommendation'] as String? ?? '',
    );
  }
}

class PredictionResult {
  final bool success;
  final PredictionStatus status;
  final PredictionData? data;
  final String? message;
  const PredictionResult({
    required this.success,
    required this.status,
    this.data,
    this.message,
  });

  factory PredictionResult.fromJson(Map<String, dynamic> j) {
    final raw = j['status'] as String? ?? '';
    final success = j['success'] as bool? ?? false;
    final data = j['data'] as Map<String, dynamic>?;
    return PredictionResult(
      success: success,
      status: _parseStatus(raw),
      data: success && data != null && data['estimated_hb_g_dl'] != null
          ? PredictionData.fromJson(data)
          : null,
      message: (j['message'] as String?) ?? (data?['message'] as String?),
    );
  }

  factory PredictionResult.networkError() => const PredictionResult(
        success: false,
        status: PredictionStatus.networkError,
        message:
            'Cannot reach the server. Make sure your phone and computer are on the same Wi-Fi network.',
      );

  factory PredictionResult.notConfigured() => const PredictionResult(
        success: false,
        status: PredictionStatus.notConfigured,
        message: 'Server URL not configured. Please set it in Account → Server Settings.',
      );

  factory PredictionResult.parseError() => const PredictionResult(
        success: false,
        status: PredictionStatus.parseError,
        message: 'Received an unexpected response from the server.',
      );

  static PredictionStatus _parseStatus(String s) {
    switch (s) {
      case 'PREDICTION_COMPLETE':
        return PredictionStatus.predictionComplete;
      case 'LOW_CONFIDENCE':
        return PredictionStatus.lowConfidence;
      case 'IMAGE_QUALITY_FAILED':
        return PredictionStatus.imageQualityFailed;
      case 'ROI_FAILED':
        return PredictionStatus.roiFailed;
      case 'MODEL_NOT_READY':
        return PredictionStatus.modelNotReady;
      default:
        return PredictionStatus.unknownError;
    }
  }
}

class ModelStatus {
  final bool available;
  final String status;
  const ModelStatus({required this.available, required this.status});
  factory ModelStatus.fromJson(Map<String, dynamic> j) => ModelStatus(
        available: j['available'] as bool? ?? false,
        status: j['status'] as String? ?? 'UNKNOWN',
      );
}
