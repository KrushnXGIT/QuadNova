import 'package:flutter/material.dart';
import '../services/screening_history_service.dart';
import '../theme/app_theme.dart';

/// History screen — lists REAL past screening results stored on-device.
///
/// Only result metadata is stored (timestamp, Hb, confidence, recommendation,
/// model version). Raw camera images are never persisted.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<ScreeningRecord> _records = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final records = await ScreeningHistoryService.instance.getAll();
    if (!mounted) return;
    setState(() {
      _records = records;
      _loading = false;
    });
  }

  Future<void> _confirmClear() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clear history?'),
        content: const Text(
            'All stored screening results will be removed from this device.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ScreeningHistoryService.instance.clear();
      if (mounted) _load();
    }
  }

  Color _confidenceColor(String status) {
    switch (status.toUpperCase()) {
      case 'HIGH_CONFIDENCE':
        return AppTheme.successGreen;
      case 'MEDIUM_CONFIDENCE':
        return AppTheme.terracotta;
      default:
        return AppTheme.errorRed;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceWhite,
        title: const Text('Screening History'),
        actions: [
          if (_records.isNotEmpty)
            IconButton(
              tooltip: 'Clear history',
              icon: const Icon(Icons.delete_outline_rounded),
              onPressed: _confirmClear,
            ),
          GestureDetector(
            onTap: () => Navigator.pushNamed(context, '/account'),
            child: Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Container(
                width: 36,
                height: 36,
                decoration: const BoxDecoration(
                  color: AppTheme.terracotta,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.person_rounded,
                  size: 18,
                  color: Colors.white,
                ),
              ),
            ),
          ),
        ],
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppTheme.terracotta))
          : _records.isEmpty
              ? _buildEmpty()
              : RefreshIndicator(
                  color: AppTheme.terracotta,
                  onRefresh: _load,
                  child: ListView.separated(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(20),
                    itemCount: _records.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 12),
                    itemBuilder: (_, i) => _buildRecordCard(_records[i]),
                  ),
                ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: const BoxDecoration(
                color: AppTheme.surfacePaper,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.history_rounded,
                size: 40,
                color: AppTheme.slateLight,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'No Screenings Yet',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 10),
            Text(
              'Your screening history will appear here\nafter your first scan.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecordCard(ScreeningRecord record) {
    final dt = record.dateTime;
    final dateStr =
        '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
    final timeStr =
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    final confColor = _confidenceColor(record.confidenceStatus);
    final isLowConf =
        record.confidenceStatus.toUpperCase() == 'LOW_CONFIDENCE';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Row(
        children: [
          // Hb value
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                record.estimatedHb.toStringAsFixed(1),
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.slateInk,
                  letterSpacing: -1,
                ),
              ),
              const Text(
                'g/dL',
                style: TextStyle(
                  fontSize: 11,
                  color: AppTheme.slateLight,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(width: 18),
          // Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$dateStr  ·  $timeStr',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.slateDeep,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: confColor.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        record.confidenceStatus
                            .replaceAll('_', ' ')
                            .toLowerCase(),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: confColor,
                        ),
                      ),
                    ),
                    if (isLowConf) ...[
                      const SizedBox(width: 6),
                      Icon(Icons.warning_amber_rounded,
                          size: 13, color: AppTheme.terracotta),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  record.modelVersion.isEmpty
                      ? 'HemoScan AI model'
                      : record.modelVersion,
                  style: const TextStyle(
                    fontSize: 10,
                    color: AppTheme.slateLight,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}