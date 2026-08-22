import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

/// Lightweight screening history backed by SharedPreferences (JSON list).
///
/// Stores only the real backend result metadata — never raw camera images.
/// Fields kept: timestamp, estimated Hb, uncertainty, confidence, image
/// quality, recommendation, model version.
class ScreeningHistoryService {
  ScreeningHistoryService._();
  static final ScreeningHistoryService instance = ScreeningHistoryService._();

  static const String _prefKey = 'screening_history';
  static const int _maxEntries = 50;

  Future<List<ScreeningRecord>> getAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefKey);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list
          .whereType<Map<String, dynamic>>()
          .map(ScreeningRecord.fromJson)
          .toList()
        ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
    } catch (_) {
      return [];
    }
  }

  /// Persist a completed (or low-confidence) real screening result.
  Future<void> addFromResult(PredictionResult result) async {
    final data = result.data;
    if (data == null) return;
    final record = ScreeningRecord(
      timestamp: DateTime.now().toIso8601String(),
      estimatedHb: data.estimatedHb,
      hbStd: data.hbStd,
      confidenceInterval95: data.confidenceInterval95,
      confidenceStatus: data.confidenceStatus,
      imageQualityStatus: data.quality.status,
      recommendation: data.recommendation,
      modelName: data.model.name,
      modelVersion: data.model.version,
    );
    await add(record);
  }

  Future<void> add(ScreeningRecord record) async {
    final prefs = await SharedPreferences.getInstance();
    final entries = await getAll();
    entries.insert(0, record);
    final trimmed = entries.take(_maxEntries).map((e) => e.toJson()).toList();
    await prefs.setString(_prefKey, jsonEncode(trimmed));
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefKey);
  }
}

class ScreeningRecord {
  final String timestamp;
  final double estimatedHb;
  final double hbStd;
  final List<double> confidenceInterval95;
  final String confidenceStatus;
  final String imageQualityStatus;
  final String recommendation;
  final String modelName;
  final String modelVersion;

  const ScreeningRecord({
    required this.timestamp,
    required this.estimatedHb,
    required this.hbStd,
    required this.confidenceInterval95,
    required this.confidenceStatus,
    required this.imageQualityStatus,
    required this.recommendation,
    required this.modelName,
    required this.modelVersion,
  });

  DateTime get dateTime => DateTime.tryParse(timestamp) ?? DateTime.now();

  factory ScreeningRecord.fromJson(Map<String, dynamic> j) => ScreeningRecord(
        timestamp: j['timestamp'] as String? ?? '',
        estimatedHb: (j['estimatedHb'] as num?)?.toDouble() ?? 0.0,
        hbStd: (j['hbStd'] as num?)?.toDouble() ?? 0.0,
        confidenceInterval95: (j['confidenceInterval95'] as List<dynamic>? ?? [])
            .whereType<num>()
            .map((v) => v.toDouble())
            .toList(),
        confidenceStatus: j['confidenceStatus'] as String? ?? '',
        imageQualityStatus: j['imageQualityStatus'] as String? ?? '',
        recommendation: j['recommendation'] as String? ?? '',
        modelName: j['modelName'] as String? ?? '',
        modelVersion: j['modelVersion'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {
        'timestamp': timestamp,
        'estimatedHb': estimatedHb,
        'hbStd': hbStd,
        'confidenceInterval95': confidenceInterval95,
        'confidenceStatus': confidenceStatus,
        'imageQualityStatus': imageQualityStatus,
        'recommendation': recommendation,
        'modelName': modelName,
        'modelVersion': modelVersion,
      };
}