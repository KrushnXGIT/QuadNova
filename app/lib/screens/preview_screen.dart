import 'dart:io';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'result_screen.dart';

/// Displays the captured image with Retake / Analyse actions.
/// "Analyse" uploads to the backend and navigates to ResultScreen.
class PreviewScreen extends StatefulWidget {
  final String imagePath;

  const PreviewScreen({super.key, required this.imagePath});

  @override
  State<PreviewScreen> createState() => _PreviewScreenState();
}

class _PreviewScreenState extends State<PreviewScreen> {
  final TransformationController _transformController =
      TransformationController();

  bool _isAnalysing = false;

  @override
  void dispose() {
    _transformController.dispose();
    super.dispose();
  }

  Future<void> _analyse() async {
    setState(() => _isAnalysing = true);

    final result = await ApiService.instance.predict(
      File(widget.imagePath),
    );

    if (!mounted) return;
    setState(() => _isAnalysing = false);

    // Handle quality failure inline — prompt to retake immediately
    if (result.status == PredictionStatus.imageQualityFailed) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result.message ??
                'Image quality insufficient. Please retake.',
          ),
          action: SnackBarAction(
            label: 'Retake',
            onPressed: () => Navigator.pop(context),
          ),
        ),
      );
      return;
    }

    // Navigate to result screen for all other responses
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => ResultScreen(result: result),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // ── Zoomable image ─────────────────────────
          InteractiveViewer(
            transformationController: _transformController,
            minScale: 1.0,
            maxScale: 5.0,
            child: Center(
              child: Image.file(
                File(widget.imagePath),
                fit: BoxFit.contain,
              ),
            ),
          ),

          // ── Top bar ────────────────────────────────
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment:
                      MainAxisAlignment.spaceBetween,
                  children: [
                    _circleButton(
                      icon: Icons.close_rounded,
                      onTap: _isAnalysing
                          ? null
                          : () => Navigator.pop(context),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.black45,
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Text(
                        'Preview',
                        style: TextStyle(
                          color: Colors.white70,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    const SizedBox(width: 42),
                  ],
                ),
              ),
            ),
          ),

          // ── Zoom hint ──────────────────────────────
          if (!_isAnalysing)
            Positioned(
              top: MediaQuery.of(context).padding.top + 60,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.black38,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Text(
                    'Pinch to zoom',
                    style: TextStyle(
                        color: Colors.white38, fontSize: 12),
                  ),
                ),
              ),
            ),

          // ── Analysing overlay ──────────────────────
          if (_isAnalysing)
            Container(
              color: Colors.black.withValues(alpha: 0.65),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppTheme.terracotta
                            .withValues(alpha: 0.15),
                        border: Border.all(
                            color: AppTheme.terracotta,
                            width: 2),
                      ),
                      child: const Padding(
                        padding: EdgeInsets.all(16),
                        child: CircularProgressIndicator(
                          color: AppTheme.terracotta,
                          strokeWidth: 2.5,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Analysing image…',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Sending to HemoScan AI server',
                      style: TextStyle(
                          color: Colors.white54, fontSize: 13),
                    ),
                  ],
                ),
              ),
            ),

          // ── Bottom actions ─────────────────────────
          if (!_isAnalysing)
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: SafeArea(
                child: Container(
                  padding:
                      const EdgeInsets.fromLTRB(24, 20, 24, 28),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.transparent,
                        Colors.black.withValues(alpha: 0.85),
                      ],
                    ),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () =>
                              Navigator.pop(context),
                          icon: const Icon(
                              Icons.refresh_rounded),
                          label: const Text('Retake'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.white,
                            side: const BorderSide(
                                color: Colors.white54),
                            padding:
                                const EdgeInsets.symmetric(
                                    vertical: 14),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: _analyse,
                          icon:
                              const Icon(Icons.analytics_rounded),
                          label: const Text('Analyse'),
                          style: ElevatedButton.styleFrom(
                            padding:
                                const EdgeInsets.symmetric(
                                    vertical: 14),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _circleButton({
    required IconData icon,
    required VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: Colors.black.withValues(alpha: 0.4),
        ),
        child: Icon(icon, color: Colors.white, size: 22),
      ),
    );
  }
}
