import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Feature card matching the HemoScan AI design.
///
/// Used for Non-Invasive, Smartphone-Based, Confidence-Aware sections.
class FeatureCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  final Color? backgroundColor;
  final Color? iconColor;

  const FeatureCard({
    super.key,
    required this.icon,
    required this.title,
    required this.description,
    this.backgroundColor,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    final bg = backgroundColor ?? AppTheme.surfaceWhite;
    final ic = iconColor ?? AppTheme.terracotta;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(16),
        border: bg == AppTheme.surfaceWhite
            ? Border.all(color: AppTheme.divider.withValues(alpha: 0.6))
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Icon in a rounded square
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: ic.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 22, color: ic),
          ),

          const SizedBox(height: 14),

          Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppTheme.slateInk,
            ),
          ),

          const SizedBox(height: 6),

          Text(
            description,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: AppTheme.slateMid,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}
