import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../core/config/api_config.dart';

/// HemoScan AI — backend API service.
///
/// The base URL is configured by the user at runtime and stored in
/// SharedPreferences. Works on any WiFi — no hardcoded IPs.
///
/// Responsibilities:
///   - upload the captured image to POST /api/v1/predict (multipart/form-data)
///   - parse the REAL backend response into typed models
///   - map transport/HTTP failures to user-friendly typed results
///
/// No Hb value is ever computed or invented here — every number displayed in
/// the UI comes from the backend's AI model response.
class ApiService {
  ApiService._();
  static final ApiService instance = ApiService._();

  static const String _prefKey = 'backend_url';
  static const String kDefaultUrl = ApiConfig.defaultBaseUrl;
  static const Duration _timeout = Duration(seconds: 60);

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

  /// POST /api/v1/predict — upload image and get the real Hb prediction.
  ///
  /// Sends only the captured image; the backend runs the actual AI pipeline.
  Future<PredictionResult> predict(File imageFile) async {
    final base = await getBaseUrl();
    if (base.isEmpty) return PredictionResult.notConfigured();

    // Basic client-side sanity check before spending bandwidth. The
    // authoritative quality check remains on the backend/AI side.
    if (!imageFile.existsSync() || imageFile.lengthSync() < 1024) {
      return const PredictionResult(
        success: false,
        status: PredictionStatus.invalidImage,
        message: 'The captured image is not usable. Please retake it.',
      );
    }

    final uri = Uri.parse('$base/api/v1/predict');
    try {
      final request = http.MultipartRequest('POST', uri)
        ..files.add(
          await http.MultipartFile.fromPath('image', imageFile.path),
        );
      final streamed = await request.send().timeout(_timeout);
      final body = await streamed.stream.bytesToString();

      Map<String, dynamic> json;
      try {
        final decoded = jsonDecode(body);
        if (decoded is! Map<String, dynamic>) throw const FormatException();
        json = decoded;
      } on FormatException {
        // Non-JSON body (proxy error page, HTML, empty body…)
        return PredictionResult.parseError(
          httpStatus: streamed.statusCode,
        );
      }

      return PredictionResult.fromJson(json, httpStatus: streamed.statusCode);
    } on TimeoutException {
      return const PredictionResult(
        success: false,
        status: PredictionStatus.networkError,
        message:
            'The server took too long to respond. Check your connection '
            'and try again.',
      );
    } on SocketException {
      return PredictionResult.networkError();
    } on HttpException {
      return PredictionResult.networkError();
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

// ── Response models (match backend/API_DOCUMENTATION.md exactly) ──────────

enum PredictionStatus {
  predictionComplete,
  lowConfidence,
  imageQualityFailed,
  eyeNotDetected,
  conjunctivaNotDetected,
  roiQualityFailed,
  roiFailed,
  modelNotReady,
  inferenceError,
  validationError,
  networkError,
  notConfigured,
  invalidImage,
  parseError,
  unknownError,
}

class QualityResult {
  final String status;
  final double score;
  final List<String> failureReasons;
  const QualityResult({
    required this.status,
    required this.score,
    this.failureReasons = const [],
  });
  factory QualityResult.fromJson(Map<String, dynamic>? j) => QualityResult(
        status: j?['status'] as String? ?? '',
        score: (j?['score'] as num?)?.toDouble() ?? 0.0,
        failureReasons: (j?['failure_reasons'] as List<dynamic>? ?? [])
            .whereType<String>()
            .toList(),
      );
}

class ModelInfo {
  final String name;
  final String version;
  const ModelInfo({required this.name, required this.version});
  factory ModelInfo.fromJson(Map<String, dynamic>? j) => ModelInfo(
        name: j?['name'] as String? ?? '',
        version: j?['version'] as String? ?? '',
      );
}

class PredictionData {
  final double estimatedHb;
  final String unit;
  final double hbStd;
  final List<double> confidenceInterval95;
  final String confidenceStatus;
  final QualityResult quality;
  final String roiStatus;
  final String recommendation;
  final ModelInfo model;
  const PredictionData({
    required this.estimatedHb,
    required this.unit,
    required this.hbStd,
    required this.confidenceInterval95,
    required this.confidenceStatus,
    required this.quality,
    required this.roiStatus,
    required this.recommendation,
    required this.model,
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
          j['image_quality'] as Map<String, dynamic>?),
      roiStatus:
          ((j['roi'] as Map<String, dynamic>?)?['status']) as String? ?? '',
      recommendation: j['recommendation'] as String? ?? '',
      model: ModelInfo.fromJson(j['model'] as Map<String, dynamic>?),
    );
  }
}

class PredictionResult {
  final bool success;
  final PredictionStatus status;
  final PredictionData? data;
  final String? message;

  /// True when the user can simply re-run the analysis (e.g. transient
  /// network/server errors) instead of recapturing the image.
  final bool canRetryUpload;

  const PredictionResult({
    required this.success,
    required this.status,
    this.data,
    this.message,
    this.canRetryUpload = false,
  });

  factory PredictionResult.fromJson(
    Map<String, dynamic> j, {
    int httpStatus = 200,
  }) {
    final raw = j['status'] as String? ?? '';
    final errorCode = (j['error'] as Map<String, dynamic>?)?['code'] as String?;
    final success = j['success'] as bool? ?? false;
    final data = j['data'] as Map<String, dynamic>?;

    final parsedData =
        success && data != null && data['estimated_hb_g_dl'] != null
            ? PredictionData.fromJson(data)
            : null;

    return PredictionResult(
      success: success,
      status: _parseStatus(raw, errorCode),
      data: parsedData,
      message: (j['message'] as String?) ??
          (data?['message'] as String?) ??
          _fallbackMessageFor(raw, success, parsedData != null),
      canRetryUpload: _isRetryable(raw, success, parsedData != null),
    );
  }

  static String? _fallbackMessageFor(
      String status, bool success, bool hasData) {
    if (success && hasData) return null;
    switch (status) {
      case 'IMAGE_QUALITY_FAILED':
        return 'Image quality is not sufficient for screening.';
      case 'EYE_NOT_DETECTED':
        return 'Eye not detected. Please capture a clear image of your eye.';
      case 'CONJUNCTIVA_NOT_DETECTED':
        return 'Conjunctiva not detected. Please make sure the inner eyelid is clearly visible.';
      case 'ROI_QUALITY_FAILED':
        return 'Image quality is insufficient. Please retake the image.';
      case 'ROI_FAILED':
        return 'We could not reliably identify the required region.';
      case 'MODEL_NOT_READY':
        return 'Screening service is temporarily unavailable.';
      case 'INFERENCE_ERROR':
        return 'Analysis failed on the server. Please try again.';
      case 'VALIDATION_ERROR':
        return 'The uploaded image was rejected. Please retake it.';
      case 'INTERNAL_ERROR':
        return 'An unexpected server error occurred. Please try again.';
      default:
        return success ? null : 'Unexpected response from the server.';
    }
  }

  static bool _isRetryable(String status, bool success, bool hasData) {
    if (success && hasData) return false;
    switch (status) {
      case 'INFERENCE_ERROR':
      case 'INTERNAL_ERROR':
        return true;
      default:
        return false;
    }
  }

  factory PredictionResult.networkError() => const PredictionResult(
        success: false,
        status: PredictionStatus.networkError,
        canRetryUpload: true,
        message:
            'Cannot reach the server. Make sure your phone and computer are '
            'on the same Wi-Fi network.',
      );

  factory PredictionResult.notConfigured() => const PredictionResult(
        success: false,
        status: PredictionStatus.notConfigured,
        message:
            'Server URL not configured. Please set it in Account → Server '
            'Settings.',
      );

  factory PredictionResult.parseError({int httpStatus = 0}) =>
      PredictionResult(
        success: false,
        status: PredictionStatus.parseError,
        canRetryUpload: true,
        message: httpStatus > 0
            ? 'Received an unexpected response from the server (HTTP '
                '$httpStatus).'
            : 'Received an unexpected response from the server.',
      );

  static PredictionStatus _parseStatus(String s, [String? errorCode]) {
    final effective = errorCode ?? s;
    switch (s) {
      case 'PREDICTION_COMPLETE':
        return PredictionStatus.predictionComplete;
      case 'LOW_CONFIDENCE':
        return PredictionStatus.lowConfidence;
      case 'IMAGE_QUALITY_FAILED':
        return PredictionStatus.imageQualityFailed;
      case 'EYE_NOT_DETECTED':
        return PredictionStatus.eyeNotDetected;
      case 'CONJUNCTIVA_NOT_DETECTED':
        return PredictionStatus.conjunctivaNotDetected;
      case 'ROI_QUALITY_FAILED':
        return PredictionStatus.roiQualityFailed;
      case 'ROI_FAILED':
        return PredictionStatus.roiFailed;
      case 'MODEL_NOT_READY':
        return PredictionStatus.modelNotReady;
      case 'INFERENCE_ERROR':
        return PredictionStatus.inferenceError;
      case 'VALIDATION_ERROR':
        return PredictionStatus.validationError;
      case 'INTERNAL_ERROR':
        return PredictionStatus.unknownError;
      default:
        switch (effective) {
          case 'EYE_NOT_DETECTED':
            return PredictionStatus.eyeNotDetected;
          case 'CONJUNCTIVA_NOT_DETECTED':
            return PredictionStatus.conjunctivaNotDetected;
          case 'ROI_QUALITY_FAILED':
            return PredictionStatus.roiQualityFailed;
          default:
            return PredictionStatus.unknownError;
        }
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