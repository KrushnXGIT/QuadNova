import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'result_screen.dart';

/// Displays the captured image with Retake / Use This Image actions.
///
/// "Use This Image" uploads the real capture to the backend and navigates to
/// the result report. No Hb value is computed or faked here — the backend's
/// AI model is the only source of predictions.
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
  Timer? _stageTimer;
  int _stageIndex = 0;

  /// Honest progress stages — indeterminate, no fake percentages.
  static const List<String> _stages = [
    'Uploading image…',
    'Checking image quality…',
    'Estimating haemoglobin…',
  ];

  @override
  void dispose() {
    _transformController.dispose();
    _stageTimer?.cancel();
    super.dispose();
  }

  void _startStageTimer() {
    _stageIndex = 0;
    _stageTimer?.cancel();
    _stageTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (!mounted) return;
      setState(() {
        _stageIndex = (_stageIndex + 1) % _stages.length;
      });
    });
  }

  /// Basic client-side usability check (file exists, non-trivial size).
  /// The authoritative image-quality check remains in the backend AI model.
  bool _imageFileLooksUsable() {
    final file = File(widget.imagePath);
    try {
      return file.existsSync() && file.lengthSync() >= 1024;
    } catch (_) {
      return false;
    }
  }

  Future<void> _useThisImage() async {
    if (_isAnalysing) return; // prevent duplicate submissions

    if (!_imageFileLooksUsable()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'This image could not be read. Please retake the photo.',
          ),
        ),
      );
      return;
    }

    setState(() => _isAnalysing = true);
    _startStageTimer();

    final result = await ApiService.instance.predict(
      File(widget.imagePath),
    );

    _stageTimer?.cancel();
    if (!mounted) return;
    setState(() => _isAnalysing = false);

    // All outcomes — success, low confidence, quality/ROI failure, model
    // unavailable, network errors — are reported on the result screen.
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => ResultScreen(result: result, imagePath: widget.imagePath),
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
                errorBuilder: (_, _, _) => const Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.broken_image_outlined,
                        size: 64, color: Colors.white38),
                    SizedBox(height: 12),
                    Text(
                      'Image could not be displayed.\nPlease retake the photo.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white54, fontSize: 13),
                    ),
                  ],
                ),
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

          // ── Analysing overlay (staged, indeterminate) ──
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
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 350),
                      child: Text(
                        _stages[_stageIndex],
                        key: ValueKey<int>(_stageIndex),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Running AI analysis on the server',
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
                          onPressed: _useThisImage,
                          icon:
                              const Icon(Icons.analytics_rounded),
                          label: const Text('Use This Image'),
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