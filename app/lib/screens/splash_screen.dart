import 'dart:math';
import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import '../theme/app_theme.dart';

/// Branded splash — warm cream with terracotta pulse animation.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _ringCtrl;
  late AnimationController _fadeCtrl;
  late AnimationController _pulseCtrl;

  late Animation<double> _ring1;
  late Animation<double> _ring2;
  late Animation<double> _fadeIn;
  late Animation<double> _slideUp;
  late Animation<double> _pulse;

  @override
  void initState() {
    super.initState();

    _ringCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    )..repeat();

    _ring1 = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(
        parent: _ringCtrl,
        curve: const Interval(0.0, 0.8, curve: Curves.easeOut),
      ),
    );
    _ring2 = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(
        parent: _ringCtrl,
        curve: const Interval(0.25, 1.0, curve: Curves.easeOut),
      ),
    );

    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..forward();

    _fadeIn = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
    _slideUp = Tween<double>(begin: 24, end: 0).animate(
      CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOutCubic),
    );

    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
    _pulse = Tween<double>(begin: 0.93, end: 1.07).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );

    _checkAuth();
  }

  Future<void> _checkAuth() async {
    await Future.delayed(const Duration(milliseconds: 2400));
    if (!mounted) return;
    final loggedIn = await AuthService().isLoggedIn();
    if (!mounted) return;
    Navigator.pushReplacementNamed(
      context,
      loggedIn ? '/main' : '/auth/phone',
    );
  }

  @override
  void dispose() {
    _ringCtrl.dispose();
    _fadeCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;

    return Scaffold(
      backgroundColor: AppTheme.cream,
      body: Stack(
        alignment: Alignment.center,
        children: [
          // ── Soft terracotta rings ──────────────────────
          AnimatedBuilder(
            animation: _ringCtrl,
            builder: (context, child) => CustomPaint(
              size: Size(size.width, size.height),
              painter: _RingPainter(
                r1: _ring1.value,
                r2: _ring2.value,
                maxRadius: size.width * 0.65,
              ),
            ),
          ),

          // ── Radial glow ────────────────────────────────
          Container(
            width: 260,
            height: 260,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  AppTheme.terracotta.withValues(alpha: 0.08),
                  Colors.transparent,
                ],
              ),
            ),
          ),

          // ── Content ────────────────────────────────────
          AnimatedBuilder(
            animation: _fadeCtrl,
            builder: (context, child) => Opacity(
              opacity: _fadeIn.value,
              child: Transform.translate(
                offset: Offset(0, _slideUp.value),
                child: child,
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Pulsing icon
                AnimatedBuilder(
                  animation: _pulse,
                  builder: (context, child) => Transform.scale(
                    scale: _pulse.value,
                    child: child,
                  ),
                  child: Container(
                    width: 88,
                    height: 88,
                    decoration: BoxDecoration(
                      color: AppTheme.terracotta,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.terracotta.withValues(alpha: 0.3),
                          blurRadius: 28,
                          spreadRadius: 4,
                        ),
                        BoxShadow(
                          color: AppTheme.terracotta.withValues(alpha: 0.12),
                          blurRadius: 56,
                          spreadRadius: 12,
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.remove_red_eye_rounded,
                      size: 40,
                      color: Colors.white,
                    ),
                  ),
                ),

                const SizedBox(height: 28),

                // App name
                RichText(
                  text: const TextSpan(
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.6,
                    ),
                    children: [
                      TextSpan(
                        text: 'HemoScan',
                        style: TextStyle(color: AppTheme.slateInk),
                      ),
                      TextSpan(
                        text: ' AI',
                        style: TextStyle(color: AppTheme.terracotta),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 6),

                Text(
                  'by QuadNova',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w400,
                    color: AppTheme.slateLight,
                    letterSpacing: 1.0,
                  ),
                ),

                const SizedBox(height: 52),

                // Dots loader
                _DotsLoader(),
              ],
            ),
          ),

          // ── Tagline at bottom ──────────────────────────
          Positioned(
            bottom: 44,
            child: Text(
              'Non-Invasive Haemoglobin Estimation',
              style: TextStyle(
                fontSize: 11,
                color: AppTheme.slateLight,
                letterSpacing: 0.6,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final double r1, r2, maxRadius;
  _RingPainter({required this.r1, required this.r2, required this.maxRadius});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);

    void ring(double t, Color color) {
      if (t <= 0) return;
      canvas.drawCircle(
        center,
        maxRadius * t,
        Paint()
          ..color = color.withValues(alpha: (1 - t).clamp(0.0, 1.0) * 0.25)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2,
      );
    }

    ring(r1, AppTheme.terracotta);
    ring(r2, AppTheme.terracottaLight);
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.r1 != r1 || old.r2 != r2;
}

class _DotsLoader extends StatefulWidget {
  @override
  State<_DotsLoader> createState() => _DotsLoaderState();
}

class _DotsLoaderState extends State<_DotsLoader>
    with SingleTickerProviderStateMixin {
  late AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (context, child) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final delay = i / 3;
            final t = ((_c.value - delay) % 1.0).clamp(0.0, 1.0);
            final scale = 0.6 + 0.4 * sin(t * pi);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 3),
              child: Transform.scale(
                scale: scale,
                child: Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppTheme.terracotta.withValues(alpha: scale),
                  ),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
