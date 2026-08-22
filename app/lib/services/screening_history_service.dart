import 'dart:convert';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';
import 'api_service.dart';

/// Screening history backed by a local SQLite database.
///
/// Each [ScreeningRecord] maps to one row in the `screenings` table.
/// A `screening_id` column holds a human-readable ID derived from
/// the timestamp (e.g. `SCR_20260822_113000`).
///
/// On first open after an update from the old SharedPreferences store,
/// existing records are automatically migrated so no history is lost.
///
/// Raw camera images are never stored — only result metadata.
class ScreeningHistoryService {
  ScreeningHistoryService._();
  static final ScreeningHistoryService instance = ScreeningHistoryService._();

  static const int _maxEntries = 50;
  static const String _dbName = 'screening_history.db';
  static const int _dbVersion = 1;

  Database? _db;

  Future<Database> _openDb() async {
    if (_db != null && _db!.isOpen) return _db!;
    final dir = await getApplicationDocumentsDirectory();
    final path = p.join(dir.path, _dbName);
    _db = await openDatabase(
      path,
      version: _dbVersion,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE screenings (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            screening_id         TEXT NOT NULL,
            timestamp            TEXT NOT NULL,
            estimated_hb         REAL NOT NULL,
            hb_std               REAL NOT NULL DEFAULT 0,
            ci_95_low            REAL,
            ci_95_high           REAL,
            confidence_status    TEXT NOT NULL DEFAULT '',
            image_quality_status TEXT NOT NULL DEFAULT '',
            recommendation       TEXT NOT NULL DEFAULT '',
            model_name           TEXT NOT NULL DEFAULT '',
            model_version        TEXT NOT NULL DEFAULT ''
          )
        ''');
        // One-time migration from SharedPreferences JSON list.
        await _migrateFromPrefs(db);
      },
    );
    return _db!;
  }

  /// One-time migration: reads the old SharedPreferences JSON list and
  /// inserts the records into SQLite, then deletes the old key.
  Future<void> _migrateFromPrefs(Database db) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString('screening_history');
      if (raw == null || raw.isEmpty) return;

      final list = jsonDecode(raw) as List<dynamic>;
      final batch = db.batch();
      for (final item in list.whereType<Map<String, dynamic>>()) {
        final record = ScreeningRecord.fromJson(item);
        batch.insert('screenings', record._toDbMap());
      }
      await batch.commit(noResult: true);
      await prefs.remove('screening_history');
    } catch (_) {
      // Migration failure must never crash the app.
    }
  }

  // ── Public API ────────────────────────────────────────────

  Future<List<ScreeningRecord>> getAll() async {
    final db = await _openDb();
    final rows = await db.query(
      'screenings',
      orderBy: 'timestamp DESC',
      limit: _maxEntries,
    );
    return rows.map(ScreeningRecord._fromDbRow).toList();
  }

  /// Persist a completed (or low-confidence) screening result.
  Future<void> addFromResult(PredictionResult result) async {
    final data = result.data;
    if (data == null) return;
    final now = DateTime.now();
    final record = ScreeningRecord(
      timestamp: now.toIso8601String(),
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
    final db = await _openDb();
    await db.insert(
      'screenings',
      record._toDbMap(),
      conflictAlgorithm: ConflictAlgorithm.ignore,
    );
    // Trim to max entries (keep newest).
    final count =
        Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM screenings'));
    if (count != null && count > _maxEntries) {
      await db.rawDelete('''
        DELETE FROM screenings WHERE id IN (
          SELECT id FROM screenings ORDER BY timestamp ASC LIMIT ?
        )
      ''', [count - _maxEntries]);
    }
  }

  Future<void> clear() async {
    final db = await _openDb();
    await db.delete('screenings');
  }
}

// ── ScreeningRecord ───────────────────────────────────────

class ScreeningRecord {
  /// SQLite row id (null until the record has been inserted).
  final int? id;

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
    this.id,
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

  // ── Computed helpers ─────────────────────────────────────

  DateTime get dateTime => DateTime.tryParse(timestamp) ?? DateTime.now();

  /// Human-readable screening ID derived from timestamp.
  /// Example: SCR_20260822_113000
  String get screeningId {
    final dt = dateTime;
    final yy  = dt.year.toString();
    final mm  = dt.month.toString().padLeft(2, '0');
    final dd  = dt.day.toString().padLeft(2, '0');
    final hh  = dt.hour.toString().padLeft(2, '0');
    final min = dt.minute.toString().padLeft(2, '0');
    final ss  = dt.second.toString().padLeft(2, '0');
    return 'SCR_$yy$mm${dd}_$hh$min$ss';
  }

  /// True when the screening completed with a usable Hb estimate.
  bool get hasResult => estimatedHb > 0;

  // ── SQLite serialisation ──────────────────────────────────

  Map<String, dynamic> _toDbMap() {
    final ci = confidenceInterval95;
    return {
      'screening_id': screeningId,
      'timestamp': timestamp,
      'estimated_hb': estimatedHb,
      'hb_std': hbStd,
      'ci_95_low': ci.length >= 2 ? ci[0] : null,
      'ci_95_high': ci.length >= 2 ? ci[1] : null,
      'confidence_status': confidenceStatus,
      'image_quality_status': imageQualityStatus,
      'recommendation': recommendation,
      'model_name': modelName,
      'model_version': modelVersion,
    };
  }

  factory ScreeningRecord._fromDbRow(Map<String, dynamic> row) {
    final ciLow = row['ci_95_low'] as double?;
    final ciHigh = row['ci_95_high'] as double?;
    return ScreeningRecord(
      id: row['id'] as int?,
      timestamp: row['timestamp'] as String? ?? '',
      estimatedHb: (row['estimated_hb'] as num?)?.toDouble() ?? 0.0,
      hbStd: (row['hb_std'] as num?)?.toDouble() ?? 0.0,
      confidenceInterval95:
          (ciLow != null && ciHigh != null) ? [ciLow, ciHigh] : [],
      confidenceStatus: row['confidence_status'] as String? ?? '',
      imageQualityStatus: row['image_quality_status'] as String? ?? '',
      recommendation: row['recommendation'] as String? ?? '',
      modelName: row['model_name'] as String? ?? '',
      modelVersion: row['model_version'] as String? ?? '',
    );
  }

  // ── Legacy JSON deserialisation (used only during migration) ─

  factory ScreeningRecord.fromJson(Map<String, dynamic> j) => ScreeningRecord(
        timestamp: j['timestamp'] as String? ?? '',
        estimatedHb: (j['estimatedHb'] as num?)?.toDouble() ?? 0.0,
        hbStd: (j['hbStd'] as num?)?.toDouble() ?? 0.0,
        confidenceInterval95:
            (j['confidenceInterval95'] as List<dynamic>? ?? [])
                .whereType<num>()
                .map((v) => v.toDouble())
                .toList(),
        confidenceStatus: j['confidenceStatus'] as String? ?? '',
        imageQualityStatus: j['imageQualityStatus'] as String? ?? '',
        recommendation: j['recommendation'] as String? ?? '',
        modelName: j['modelName'] as String? ?? '',
        modelVersion: j['modelVersion'] as String? ?? '',
      );
}