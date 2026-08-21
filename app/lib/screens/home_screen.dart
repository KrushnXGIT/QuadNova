import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Home screen — Anthropic-inspired warm cream design.
class HomeScreen extends StatelessWidget {
  final VoidCallback? onStartScreening;

  const HomeScreen({super.key, this.onStartScreening});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          // ── App Bar ─────────────────────────────────────
          SliverAppBar(
            pinned: true,
            backgroundColor: AppTheme.cream,
            surfaceTintColor: Colors.transparent,
            scrolledUnderElevation: 0,
            elevation: 0,
            centerTitle: false,
            automaticallyImplyLeading: false,
            title: Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: AppTheme.terracotta,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.remove_red_eye_rounded,
                    size: 15,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  'HemoScan',
                  style: GoogleFontsHelper.interBold(17, AppTheme.slateInk),
                ),
                Text(
                  ' AI',
                  style: GoogleFontsHelper.interBold(17, AppTheme.terracotta),
                ),
              ],
            ),
            actions: [
              GestureDetector(
                onTap: () => Navigator.pushNamed(context, '/account'),
                child: Padding(
                  padding: const EdgeInsets.only(right: 16),
                  child: Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
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

          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Hero ────────────────────────────────────
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 36, 24, 0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Tag chip
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: AppTheme.peach,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 6,
                              height: 6,
                              decoration: BoxDecoration(
                                color: AppTheme.terracotta,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              'QuadNova Research',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.terracottaDark,
                                letterSpacing: 0.3,
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 18),

                      // Headline
                      RichText(
                        text: TextSpan(
                          style: const TextStyle(
                            fontSize: 34,
                            fontWeight: FontWeight.w800,
                            height: 1.13,
                            letterSpacing: -1.0,
                            color: AppTheme.slateInk,
                          ),
                          children: const [
                            TextSpan(text: 'Check your Hb.\n'),
                            TextSpan(
                              text: 'No blood draw',
                              style: TextStyle(color: AppTheme.terracotta),
                            ),
                            TextSpan(text: '\nrequired.'),
                          ],
                        ),
                      ),

                      const SizedBox(height: 16),

                      Text(
                        'Advanced smartphone imaging estimates haemoglobin '
                        'levels from a simple photo of the inner eyelid.',
                        style: TextStyle(
                          fontSize: 15,
                          color: AppTheme.slateMid,
                          height: 1.65,
                        ),
                      ),

                      const SizedBox(height: 28),

                      // CTA buttons
                      Row(
                        children: [
                          Expanded(
                            child: SizedBox(
                              height: 50,
                              child: ElevatedButton(
                                onPressed: onStartScreening,
                                child: const Text('Start Screening'),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          SizedBox(
                            height: 50,
                            child: OutlinedButton(
                              onPressed: () =>
                                  Navigator.pushNamed(context, '/info'),
                              child: const Text('How It Works'),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 40),

                // ── Section divider ──────────────────────────
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Row(
                    children: [
                      const Expanded(child: Divider()),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Text(
                          'Why HemoScan AI',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.slateLight,
                            letterSpacing: 0.8,
                          ),
                        ),
                      ),
                      const Expanded(child: Divider()),
                    ],
                  ),
                ),

                const SizedBox(height: 20),

                // ── Feature Cards ────────────────────────────
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    children: [
                      _FeatureRow(
                        icon: Icons.healing_rounded,
                        title: 'Non-Invasive',
                        description:
                            'No needles or discomfort. Replaces capillary blood draws for preliminary screening.',
                      ),
                      const SizedBox(height: 10),
                      _FeatureRow(
                        icon: Icons.smartphone_rounded,
                        title: 'Smartphone-Based',
                        description:
                            'Accessible anywhere using your phone camera and flash.',
                      ),
                      const SizedBox(height: 10),
                      _FeatureRow(
                        icon: Icons.verified_outlined,
                        title: 'Confidence-Aware',
                        description:
                            'Built-in quality checks ensure only reliable images are analysed.',
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 28),

                // ── Disclaimer banner ────────────────────────
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 0, 24, 36),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.surfacePaper,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.divider),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.info_outline_rounded,
                          size: 16,
                          color: AppTheme.terracotta,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Research prototype. Estimates only — not for clinical diagnosis. '
                            'Confirmatory testing should always be considered.',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.slateMid,
                              height: 1.55,
                            ),
                          ),
                        ),
                      ],
                    ),
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

class _FeatureRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;

  const _FeatureRow({
    required this.icon,
    required this.title,
    required this.description,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: AppTheme.peach,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 18, color: AppTheme.terracotta),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.slateInk,
                  ),
                ),
                const SizedBox(height: 3),
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

/// Tiny helper since we can't import google_fonts in a const context.
class GoogleFontsHelper {
  static TextStyle interBold(double size, Color color) => TextStyle(
        fontFamily: 'Inter',
        fontSize: size,
        fontWeight: FontWeight.w700,
        color: color,
      );
}
