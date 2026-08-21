import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/quality_indicator.dart';
import '../widgets/eye_guide_overlay.dart';

/// Camera screening screen matching the HemoScan AI design.
///
/// Quality indicator pills, eye guide overlay, zoom slider, shutter button.
class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  bool _isInitialised = false;
  bool _isCapturing = false;
  String? _errorMessage;

  // Quality indicators (simulated)
  QualityStatus _lightingStatus = QualityStatus.scanning;
  String _lightingValue = 'Checking';
  QualityStatus _sharpnessStatus = QualityStatus.scanning;
  String _sharpnessValue = 'Scanning';
  QualityStatus _visibilityStatus = QualityStatus.scanning;
  String _visibilityValue = 'Checking';

  // Zoom
  double _currentZoom = 1.0;
  double _minZoom = 1.0;
  double _maxZoom = 2.0;

  Timer? _qualityTimer;

  // ── Lifecycle ─────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initCamera();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _qualityTimer?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (_controller == null || !_controller!.value.isInitialized) return;
    if (state == AppLifecycleState.inactive) {
      _controller?.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _initCamera();
    }
  }

  // ── Init ──────────────────────────────────────────────────

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        setState(() => _errorMessage = 'No cameras found on this device.');
        return;
      }

      final backCamera = _cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => _cameras.first,
      );

      _controller = CameraController(
        backCamera,
        ResolutionPreset.high,
        enableAudio: false,
      );

      await _controller!.initialize();

      // Get zoom range
      _minZoom = await _controller!.getMinZoomLevel();
      _maxZoom = await _controller!.getMaxZoomLevel();
      // Cap max zoom at 2x for UI slider
      if (_maxZoom > 2.0) _maxZoom = 2.0;

      if (!mounted) return;
      setState(() => _isInitialised = true);

      _startQualitySimulation();
    } catch (e) {
      setState(() => _errorMessage = 'Camera error: $e');
    }
  }

  /// Simulate quality indicators updating over time.
  void _startQualitySimulation() {
    // Simulate: after 1.5s lighting becomes Good, after 2.5s visibility, after 3.5s sharpness
    Future.delayed(const Duration(milliseconds: 1500), () {
      if (mounted) {
        setState(() {
          _lightingStatus = QualityStatus.good;
          _lightingValue = 'Good';
        });
      }
    });
    Future.delayed(const Duration(milliseconds: 2500), () {
      if (mounted) {
        setState(() {
          _visibilityStatus = QualityStatus.good;
          _visibilityValue = 'Visible';
        });
      }
    });
    Future.delayed(const Duration(milliseconds: 3500), () {
      if (mounted) {
        setState(() {
          _sharpnessStatus = QualityStatus.good;
          _sharpnessValue = 'Sharp';
        });
      }
    });
  }

  // ── Actions ───────────────────────────────────────────────

  Future<void> _captureImage() async {
    if (_controller == null ||
        !_controller!.value.isInitialized ||
        _isCapturing) {
      return;
    }

    setState(() => _isCapturing = true);

    try {
      final XFile file = await _controller!.takePicture();
      if (!mounted) return;
      Navigator.pushNamed(context, '/preview', arguments: file.path);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Capture failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isCapturing = false);
    }
  }

  void _onZoomChanged(double value) {
    setState(() => _currentZoom = value);
    _controller?.setZoomLevel(value);
  }

  // ── Build ─────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: _errorMessage != null
          ? _buildError()
          : !_isInitialised
              ? _buildLoading()
              : _buildCamera(),
    );
  }

  Widget _buildLoading() {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: Colors.white70),
          SizedBox(height: 16),
          Text('Initialising camera…',
              style: TextStyle(color: Colors.white70)),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 56, color: Colors.redAccent),
            const SizedBox(height: 16),
            Text(
              _errorMessage!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white70, fontSize: 15),
            ),
            const SizedBox(height: 24),
            OutlinedButton(
              onPressed: () => Navigator.pop(context),
              style: OutlinedButton.styleFrom(foregroundColor: Colors.white),
              child: const Text('Go Back'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCamera() {
    final controller = _controller!;
    final size = MediaQuery.of(context).size;
    final previewAspect = controller.value.aspectRatio;
    var scale = size.aspectRatio * previewAspect;
    if (scale < 1) scale = 1 / scale;

    return Stack(
      fit: StackFit.expand,
      children: [
        // ── Camera preview ──────────────────────────
        Center(
          child: Transform.scale(
            scale: scale,
            child: CameraPreview(controller),
          ),
        ),

        // ── Eye guide overlay ───────────────────────
        const EyeGuideOverlay(),

        // ── Top bar ─────────────────────────────────
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _circleButton(
                    icon: Icons.close_rounded,
                    onTap: () => Navigator.pop(context),
                  ),
                  const Text(
                    'HemoScan AI',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  _circleButton(
                    icon: Icons.help_outline_rounded,
                    onTap: () {
                      // TODO: Show help dialog
                    },
                  ),
                ],
              ),
            ),
          ),
        ),

        // ── Quality indicators ──────────────────────
        Positioned(
          top: MediaQuery.of(context).padding.top + 56,
          left: 0,
          right: 0,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Wrap(
              alignment: WrapAlignment.center,
              spacing: 8,
              runSpacing: 8,
              children: [
                QualityIndicator(
                  label: 'Lighting',
                  value: _lightingValue,
                  status: _lightingStatus,
                ),
                QualityIndicator(
                  label: 'Sharpness',
                  value: _sharpnessValue,
                  status: _sharpnessStatus,
                ),
                QualityIndicator(
                  label: 'Visibility',
                  value: _visibilityValue,
                  status: _visibilityStatus,
                ),
              ],
            ),
          ),
        ),

        // ── Instruction text ────────────────────────
        Positioned(
          bottom: 200,
          left: 24,
          right: 24,
          child: Center(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Text(
                'Pull down lower eyelid and align\nconjunctiva within guide.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white70,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  height: 1.4,
                ),
              ),
            ),
          ),
        ),

        // ── Bottom controls ─────────────────────────
        Positioned(
          bottom: 0,
          left: 0,
          right: 0,
          child: SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Zoom slider
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 60),
                  child: Row(
                    children: [
                      Text(
                        '${_minZoom.toStringAsFixed(0)}x',
                        style: const TextStyle(
                          color: Colors.white60,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Expanded(
                        child: SliderTheme(
                          data: SliderThemeData(
                            activeTrackColor: AppTheme.terracottaLight,
                            inactiveTrackColor:
                                Colors.white.withValues(alpha: 0.2),
                            thumbColor: Colors.white,
                            thumbShape: const RoundSliderThumbShape(
                              enabledThumbRadius: 8,
                            ),
                            trackHeight: 3,
                            overlayShape: const RoundSliderOverlayShape(
                              overlayRadius: 16,
                            ),
                          ),
                          child: Slider(
                            value: _currentZoom,
                            min: _minZoom,
                            max: _maxZoom,
                            onChanged: _onZoomChanged,
                          ),
                        ),
                      ),
                      Text(
                        '${_maxZoom.toStringAsFixed(0)}x',
                        style: const TextStyle(
                          color: Colors.white60,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 16),

                // Shutter button
                GestureDetector(
                  onTap: _captureImage,
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 150),
                    width: _isCapturing ? 62 : 72,
                    height: _isCapturing ? 62 : 72,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 4),
                      color: _isCapturing ? Colors.white24 : Colors.transparent,
                    ),
                    child: Container(
                      margin: const EdgeInsets.all(5),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _isCapturing
                            ? Colors.white54
                            : Colors.white,
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _circleButton({
    required IconData icon,
    required VoidCallback onTap,
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
