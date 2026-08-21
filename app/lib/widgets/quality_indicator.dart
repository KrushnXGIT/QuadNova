import 'package:flutter/material.dart';

/// Pill-shaped quality indicator badge for the camera screen.
///
/// Shows status like "Lighting: Good" with a coloured dot.
class QualityIndicator extends StatelessWidget {
  final String label;
  final String value;
  final QualityStatus status;

  const QualityIndicator({
    super.key,
    required this.label,
    required this.value,
    required this.status,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: _statusColor.withValues(alpha: 0.5),
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Status dot or spinner
          if (status == QualityStatus.scanning)
            SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: _statusColor,
              ),
            )
          else
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: _statusColor,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: _statusColor.withValues(alpha: 0.5),
                    blurRadius: 6,
                  ),
                ],
              ),
            ),

          const SizedBox(width: 8),

          Text(
            '$label: $value',
            style: TextStyle(
              color: _statusColor,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }

  Color get _statusColor {
    switch (status) {
      case QualityStatus.good:
        return const Color(0xFF22C55E);
      case QualityStatus.scanning:
        return const Color(0xFFFFA726);
      case QualityStatus.poor:
        return const Color(0xFFFF6B6B);
    }
  }
}

enum QualityStatus { good, scanning, poor }
