import 'dart:async';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import '../theme/app_theme.dart';
import '../widgets/eye_guide_overlay.dart';
import '../widgets/quality_indicator.dart';

/// Camera screening screen matching the HemoScan AI design.
///
/// Real camera preview with permission handling, eye guide overlay,
/// zoom slider and shutter button.
///
/// The Lighting / Sharpness / Steadiness pills show GENUINE real-time
/// measurements computed from live preview frames (luma brightness,
/// Laplacian-variance blur estimate, frame-to-frame motion). They are
/// capture-guidance heuristics only — the authoritative image-quality
/// decision always remains with the backend AI pipeline.
class CameraScreen extends StatefulWidget {
  final bool consentGiven;
  final String consentVersion;
  final DateTime consentTimestamp;

  const CameraScreen({
    super.key,
    required this.consentGiven,
    required this.consentVersion,
    required this.consentTimestamp,
  });

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

enum _CameraPhase {
  consentRequired,
  requestingPermission,
  permissionDenied,
  permissionPermanentlyDenied,
  initializing,
  ready,
  error,
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  _CameraPhase _phase = _CameraPhase.requestingPermission;
  String? _errorMessage;

  // ── Real-time quality analysis state ──────────────────────
  QualityStatus _lightingStatus = QualityStatus.scanning;
  String _lightingValue = 'Checking';
  QualityStatus _sharpnessStatus = QualityStatus.scanning;
  String _sharpnessValue = 'Scanning';
  QualityStatus _steadinessStatus = QualityStatus.scanning;
  String _steadinessValue = 'Checking';

  Uint8List? _prevLuma; // previous downsampled luma grid (for motion)
  int _prevLumaW = 0;
  int _prevLumaH = 0;
  DateTime _lastFrameAnalysis =
      DateTime.fromMillisecondsSinceEpoch(0);
  bool _isStreaming = false;

  // ── Zoom ──────────────────────────────────────────────────
  double _currentZoom = 1.0;
  double _minZoom = 1.0;
  double _maxZoom = 2.0;

  bool _showHelp = false;

  // ── Lifecycle ─────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (widget.consentGiven) {
      _ensurePermissionAndInit();
    } else {
      _phase = _CameraPhase.consentRequired;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _disposeController();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Re-initialise when returning from app settings (permission grant) and
    // release the camera when the app is backgrounded.
    if (state == AppLifecycleState.inactive) {
      _disposeController();
    } else if (state == AppLifecycleState.resumed) {
      if (_phase == _CameraPhase.ready ||
          _phase == _CameraPhase.permissionDenied ||
          _phase == _CameraPhase.permissionPermanentlyDenied) {
        _ensurePermissionAndInit();
      }
    }
  }

  // ── Permission + init ─────────────────────────────────────

  Future<void> _ensurePermissionAndInit() async {
    setState(() => _phase = _CameraPhase.requestingPermission);

    final status = await Permission.camera.status;
    PermissionStatus effective = status;
    if (status.isDenied || status.isRestricted) {
      effective = await Permission.camera.request();
    }

    if (!mounted) return;
    if (effective.isPermanentlyDenied || effective.isRestricted) {
      setState(() => _phase = _CameraPhase.permissionPermanentlyDenied);
      return;
    }
    if (!effective.isGranted) {
      setState(() => _phase = _CameraPhase.permissionDenied);
      return;
    }

    await _initCamera();
  }

  Future<void> _initCamera() async {
    setState(() => _phase = _CameraPhase.initializing);
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        setState(() {
          _phase = _CameraPhase.error;
          _errorMessage = 'No cameras were found on this device.';
        });
        return;
      }

      final backCamera = _cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => _cameras.first,
      );

      final controller = CameraController(
        backCamera,
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      await controller.initialize();

      double minZoom = 1.0;
      double maxZoom = 2.0;
      try {
        minZoom = await controller.getMinZoomLevel();
        maxZoom = await controller.getMaxZoomLevel();
        if (maxZoom > 2.0) maxZoom = 2.0;
      } catch (_) {
        // Zoom unsupported — keep defaults.
      }

      if (!mounted) {
        await controller.dispose();
        return;
      }

      _disposeController();
      setState(() {
        _controller = controller;
        _minZoom = minZoom;
        _maxZoom = maxZoom;
        _currentZoom = minZoom < 1.0 ? 1.0 : minZoom;
        _phase = _CameraPhase.ready;
        _errorMessage = null;
        _resetQualityPills();
      });

      await _startFrameAnalysis();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _phase = _CameraPhase.error;
        _errorMessage =
            'The camera could not be started. Close other apps using the '
            'camera and try again.';
      });
    }
  }

  void _resetQualityPills() {
    _lightingStatus = QualityStatus.scanning;
    _lightingValue = 'Checking';
    _sharpnessStatus = QualityStatus.scanning;
    _sharpnessValue = 'Scanning';
    _steadinessStatus = QualityStatus.scanning;
    _steadinessValue = 'Checking';
    _prevLuma = null;
  }

  void _disposeController() {
    final controller = _controller;
    _controller = null;
    _isStreaming = false;
    controller?.dispose();
  }

  // ── Real-time frame analysis ──────────────────────────────

  Future<void> _startFrameAnalysis() async {
    final controller = _controller;
    if (controller == null ||
        !controller.value.isInitialized ||
        _isStreaming) {
      return;
    }
    try {
      await controller.startImageStream(_onCameraFrame);
      _isStreaming = true;
    } catch (_) {
      // Analysis is best-effort guidance; capture still works without it.
    }
  }

  Future<void> _stopFrameAnalysis() async {
    if (!_isStreaming) return;
    _isStreaming = false;
    try {
      await _controller?.stopImageStream();
    } catch (_) {
      // ignore — controller may already be disposed
    }
  }

  /// Runs on every camera frame (throttled internally). Computes three
  /// genuine signals from the luma plane:
  ///   1. Lighting  — mean luma brightness.
  ///   2. Sharpness — variance of the Laplacian (low variance ⇒ blur).
  ///   3. Steadiness— mean absolute frame-to-frame luma difference.
  void _onCameraFrame(CameraImage image) {
    final now = DateTime.now();
    if (now.difference(_lastFrameAnalysis).inMilliseconds < 400) return;
    _lastFrameAnalysis = now;

    final plane = image.planes.first;
    final bytes = plane.bytes;
    final int width = image.width;
    final int height = image.height;
    final int rowStride = plane.bytesPerRow;
    if (bytes.isEmpty || width < 32 || height < 32) return;

    // Downsample the luma plane to a small grid for cheap analysis.
    const int gridW = 96;
    const int gridH = 72;
    final luma = Uint8List(gridW * gridH);
    double sum = 0;
    for (int gy = 0; gy < gridH; gy++) {
      final int sy = (gy * height) ~/ gridH;
      final int rowStart = sy * rowStride;
      for (int gx = 0; gx < gridW; gx++) {
        final int sx = (gx * width) ~/ gridW;
        final int idx = rowStart + sx;
        if (idx >= bytes.length) continue;
        final int v = bytes[idx];
        luma[gy * gridW + gx] = v;
        sum += v;
      }
    }
    final double meanLuma = sum / (gridW * gridH);

    // 1) Lighting — mean brightness of the scene.
    QualityStatus lightingStatus;
    String lightingValue;
    if (meanLuma < 55) {
      lightingStatus = QualityStatus.poor;
      lightingValue = 'Too dark';
    } else if (meanLuma > 205) {
      lightingStatus = QualityStatus.poor;
      lightingValue = 'Too bright';
    } else {
      lightingStatus = QualityStatus.good;
      lightingValue = 'Good';
    }

    // 2) Sharpness — Laplacian variance on the luma grid.
    double lapSum = 0;
    double lapSqSum = 0;
    int lapCount = 0;
    for (int y = 1; y < gridH - 1; y++) {
      for (int x = 1; x < gridW - 1; x++) {
        final int c = luma[y * gridW + x];
        final int lap = 4 * c -
            luma[(y - 1) * gridW + x] -
            luma[(y + 1) * gridW + x] -
            luma[y * gridW + x - 1] -
            luma[y * gridW + x + 1];
        lapSum += lap;
        lapSqSum += lap * lap;
        lapCount++;
      }
    }
    QualityStatus sharpnessStatus;
    String sharpnessValue;
    if (lapCount > 0) {
      final double lapMean = lapSum / lapCount;
      final double lapVar = lapSqSum / lapCount - lapMean * lapMean;
      if (lapVar < 30) {
        sharpnessStatus = QualityStatus.poor;
        sharpnessValue = 'Blurry';
      } else {
        sharpnessStatus = QualityStatus.good;
        sharpnessValue = 'Sharp';
      }
    } else {
      sharpnessStatus = QualityStatus.scanning;
      sharpnessValue = 'Scanning';
    }

    // 3) Steadiness — frame-to-frame mean absolute difference.
    QualityStatus steadinessStatus;
    String steadinessValue;
    final prev = _prevLuma;
    if (prev != null &&
        _prevLumaW == gridW &&
        _prevLumaH == gridH &&
        prev.length == luma.length) {
      double diffSum = 0;
      for (int i = 0; i < luma.length; i++) {
        diffSum += (luma[i] - prev[i]).abs();
      }
      final double meanDiff = diffSum / luma.length;
      if (meanDiff > 14) {
        steadinessStatus = QualityStatus.poor;
        steadinessValue = 'Shaky';
      } else {
        steadinessStatus = QualityStatus.good;
        steadinessValue = 'Steady';
      }
    } else {
      steadinessStatus = QualityStatus.scanning;
      steadinessValue = 'Checking';
    }
    _prevLuma = Uint8List.fromList(luma);
    _prevLumaW = gridW;
    _prevLumaH = gridH;

    if (!mounted) return;
    setState(() {
      _lightingStatus = lightingStatus;
      _lightingValue = lightingValue;
      _sharpnessStatus = sharpnessStatus;
      _sharpnessValue = sharpnessValue;
      _steadinessStatus = steadinessStatus;
      _steadinessValue = steadinessValue;
    });
  }

  // ── Actions ───────────────────────────────────────────────

  Future<void> _captureImage() async {
    final controller = _controller;
    if (controller == null ||
        !controller.value.isInitialized ||
        controller.value.isTakingPicture) {
      return;
    }

    try {
      // Pause frame analysis while capturing/reviewing.
      await _stopFrameAnalysis();
      final XFile file = await controller.takePicture();
      if (!mounted) return;
      // Pause the preview while the user reviews the capture.
      await controller.pausePreview();
      if (!mounted) return;
      await Navigator.pushNamed(context, '/preview', arguments: file.path);
      if (!mounted) return;
      // Resume preview + analysis when returning for a retake.
      if (controller.value.isInitialized) {
        try {
          await controller.resumePreview();
          await _startFrameAnalysis();
        } catch (_) {
          await _initCamera();
        }
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Capture failed. Please try again.'),
          ),
        );
      }
      // Best-effort restart of the guidance stream.
      await _startFrameAnalysis();
    }
  }

  void _onZoomChanged(double value) {
    setState(() => _currentZoom = value);
    _controller?.setZoomLevel(value);
  }

  void _openHelp() => setState(() => _showHelp = true);

  // ── Build ─────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: switch (_phase) {
        _CameraPhase.consentRequired => _buildConsentRequired(),
        _CameraPhase.requestingPermission ||
        _CameraPhase.initializing =>
          _buildLoading(),
        _CameraPhase.permissionDenied => _buildPermissionDenied(),
        _CameraPhase.permissionPermanentlyDenied =>
          _buildPermissionPermanentlyDenied(),
        _CameraPhase.error => _buildError(),
        _CameraPhase.ready => _buildCamera(),
      },
    );
  }

  Widget _buildConsentRequired() {
    return _buildMessageScreen(
      icon: Icons.fact_check_outlined,
      title: 'Consent Required',
      message: 'Please read and agree to the screening information before using the camera.',
      actions: [
        OutlinedButton(
          onPressed: () => Navigator.pop(context),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white,
            side: const BorderSide(color: Colors.white54),
          ),
          child: const Text('Go Back'),
        ),
      ],
    );
  }

  Widget _buildLoading() {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: Colors.white70),
          SizedBox(height: 16),
          Text('Preparing camera…',
              style: TextStyle(color: Colors.white70)),
        ],
      ),
    );
  }

  Widget _buildPermissionDenied() {
    return _buildMessageScreen(
      icon: Icons.no_photography_outlined,
      title: 'Camera Access Needed',
      message:
          'HemoScan AI needs camera access to capture the inner-eyelid image '
          'used for screening. Your photo is sent only to your screening '
          'server for analysis.',
      actions: [
        ElevatedButton.icon(
          onPressed: _ensurePermissionAndInit,
          icon: const Icon(Icons.refresh_rounded, size: 18),
          label: const Text('Try Again'),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: () => Navigator.pop(context),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white,
            side: const BorderSide(color: Colors.white54),
          ),
          child: const Text('Back'),
        ),
      ],
    );
  }

  Widget _buildPermissionPermanentlyDenied() {
    return _buildMessageScreen(
      icon: Icons.block_rounded,
      title: 'Camera Permission Blocked',
      message:
          'Camera access is permanently disabled for this app. Enable it in '
          'system settings to continue with image-based screening.',
      actions: [
        ElevatedButton.icon(
          onPressed: () => openAppSettings(),
          icon: const Icon(Icons.settings_rounded, size: 18),
          label: const Text('Open Settings'),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: _ensurePermissionAndInit,
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white,
            side: const BorderSide(color: Colors.white54),
          ),
          child: const Text('Check Again'),
        ),
      ],
    );
  }

  Widget _buildError() {
    return _buildMessageScreen(
      icon: Icons.error_outline_rounded,
      title: 'Camera Unavailable',
      message: _errorMessage ?? 'The camera could not be started.',
      actions: [
        ElevatedButton.icon(
          onPressed: _ensurePermissionAndInit,
          icon: const Icon(Icons.refresh_rounded, size: 18),
          label: const Text('Retry'),
        ),
      ],
    );
  }

  Widget _buildMessageScreen({
    required IconData icon,
    required String title,
    required String message,
    required List<Widget> actions,
  }) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.08),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, size: 38, color: Colors.white70),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 14,
                height: 1.6,
              ),
            ),
            const SizedBox(height: 32),
            ...actions,
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => Navigator.pop(context),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Colors.white54),
              ),
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

        // ── Eye guide overlay (positioning aid only) ─
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
                    onTap: _openHelp,
                  ),
                ],
              ),
            ),
          ),
        ),

        // ── Live quality indicators (real measurements) ──
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
                  label: 'Steadiness',
                  value: _steadinessValue,
                  status: _steadinessStatus,
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
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Text(
                'Pull down the lower eyelid and align the\ninner eyelid '
                '(conjunctiva) inside the guide area.',
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
                            value: _currentZoom.clamp(_minZoom, _maxZoom),
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
                  key: const ValueKey('shutter_button'),
                  onTap: _captureImage,
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 150),
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 4),
                    ),
                    child: Container(
                      margin: const EdgeInsets.all(5),
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 32),
              ],
            ),
          ),
        ),

        // ── Help sheet ──────────────────────────────
        if (_showHelp) _buildHelpSheet(),
      ],
    );
  }

  Widget _buildHelpSheet() {
    return GestureDetector(
      onTap: () => setState(() => _showHelp = false),
      child: Container(
        color: Colors.black54,
        alignment: Alignment.center,
        padding: const EdgeInsets.all(28),
        child: GestureDetector(
          onTap: () {}, // swallow taps inside the card
          child: Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppTheme.surfaceWhite,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'How to capture',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.slateInk,
                  ),
                ),
                const SizedBox(height: 14),
                _helpRow('1.',
                    'Gently pull down your lower eyelid to expose the inner eyelid.'),
                _helpRow('2.',
                    'Position the pink inner-eyelid area inside the guide box.'),
                _helpRow('3.',
                    'Use good, even lighting. Avoid strong shadows and flash glare.'),
                _helpRow('4.',
                    'Hold the phone steady and capture only when the image is clear.'),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () => setState(() => _showHelp = false),
                    child: const Text('Got it'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _helpRow(String num, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            num,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: AppTheme.terracotta,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                fontSize: 13,
                color: AppTheme.slateMid,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
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