import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// "How It Works" screen — 4 numbered step cards.
class InfoScreen extends StatelessWidget {
  const InfoScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceWhite,
        title: const Text('HemoScan AI'),
        actions: [
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
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 28),

            Center(
              child: Text(
                'How It Works',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                'Four simple steps to instant conjunctival analysis.',
                style: Theme.of(context).textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
            ),

            const SizedBox(height: 28),

            // ── Step cards ─────────────────────────────
            _StepCard(
              stepNumber: 1,
              title: 'Capture',
              description:
                  'Position your phone camera to capture a clear, well-lit '
                  'image of the lower inner eyelid (conjunctiva).',
              icon: Icons.camera_alt_rounded,
              color: const Color(0xFFE3F2FD),
              iconColor: const Color(0xFF1976D2),
            ),

            const SizedBox(height: 16),

            _StepCard(
              stepNumber: 2,
              title: 'Check',
              description:
                  'Our system instantly analyzes the image quality, ensuring '
                  'perfect sharpness and lighting before processing.',
              icon: Icons.search_rounded,
              color: const Color(0xFFE8F5E9),
              iconColor: const Color(0xFF388E3C),
            ),

            const SizedBox(height: 16),

            _StepCard(
              stepNumber: 3,
              title: 'Analyze',
              description:
                  'HemoScan AI securely processes the image utilising our '
                  'advanced diagnostic models to evaluate paleness levels.',
              icon: Icons.analytics_rounded,
              color: const Color(0xFFF3E5F5),
              iconColor: const Color(0xFF7B1FA2),
            ),

            const SizedBox(height: 16),

            _StepCard(
              stepNumber: 4,
              title: 'Decide',
              description:
                  'Review clear, actionable results alongside AI confidence '
                  'levels to assist in your clinical decision-making process.',
              icon: Icons.fact_check_rounded,
              color: const Color(0xFFFFF3E0),
              iconColor: const Color(0xFFE65100),
            ),

            const SizedBox(height: 32),

            // ── Got It button ──────────────────────────
            SizedBox(
              width: double.infinity,
              height: 54,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Got It'),
              ),
            ),

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}

/// Individual step card with step number badge, icon area, title, description.
class _StepCard extends StatelessWidget {
  final int stepNumber;
  final String title;
  final String description;
  final IconData icon;
  final Color color;
  final Color iconColor;

  const _StepCard({
    required this.stepNumber,
    required this.title,
    required this.description,
    required this.icon,
    required this.color,
    required this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.divider.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Image/icon area ───────────────────────
          Container(
            width: double.infinity,
            height: 140,
            decoration: BoxDecoration(
              color: color,
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(18),
              ),
            ),
            child: Stack(
              children: [
                Center(
                  child: Icon(icon, size: 56, color: iconColor),
                ),
                // Step number badge
                Positioned(
                  top: 12,
                  left: 12,
                  child: Container(
                    width: 30,
                    height: 30,
                    decoration: BoxDecoration(
                      color: AppTheme.terracotta,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.terracotta.withValues(alpha: 0.3),
                          blurRadius: 8,
                        ),
                      ],
                    ),
                    child: Center(
                      child: Text(
                        '$stepNumber',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // ── Text content ──────────────────────────
          Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.slateInk,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.slateMid,
                    height: 1.5,
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
