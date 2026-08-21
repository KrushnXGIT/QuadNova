import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/server_discovery.dart';
import '../theme/app_theme.dart';

/// Shown on first launch or from Account → Server Settings.
/// Can auto-detect the backend on the LAN or accept a manual URL.
class ServerSetupScreen extends StatefulWidget {
  final bool isSettings;
  const ServerSetupScreen({super.key, this.isSettings = false});

  @override
  State<ServerSetupScreen> createState() => _ServerSetupScreenState();
}

class _ServerSetupScreenState extends State<ServerSetupScreen>
    with SingleTickerProviderStateMixin {
  final _controller = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  _Mode _mode = _Mode.idle;
  double _scanProgress = 0.0;
  String? _foundUrl;
  String _statusMessage = '';

  late AnimationController _pulseCtrl;
  late Animation<double> _pulse;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _pulse = Tween<double>(begin: 0.85, end: 1.0)
        .animate(CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut));
    _loadCurrent();
  }

  Future<void> _loadCurrent() async {
    final url = await ApiService.instance.getBaseUrl();
    if (url.isNotEmpty && mounted) {
      setState(() => _controller.text = url);
    }
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _controller.dispose();
    super.dispose();
  }

  // ── Auto-detect ───────────────────────────────────────────

  Future<void> _autoDetect() async {
    setState(() {
      _mode = _Mode.scanning;
      _scanProgress = 0;
      _foundUrl = null;
      _statusMessage = 'Scanning local network…';
    });

    final url = await ServerDiscovery.discover(
      onProgress: (progress, found) {
        if (!mounted) return;
        setState(() {
          _scanProgress = progress;
          if (found != null) _foundUrl = found;
        });
      },
    );

    if (!mounted) return;

    if (url != null) {
      await ApiService.instance.setBaseUrl(url);
      setState(() {
        _mode = _Mode.found;
        _statusMessage = 'Found at $url';
        _controller.text = url;
      });
      await Future.delayed(const Duration(milliseconds: 900));
      if (!mounted) return;
      _proceed();
    } else {
      setState(() {
        _mode = _Mode.notFound;
        _statusMessage =
            'No server found on this network. Enter the URL manually.';
      });
    }
  }

  // ── Manual save ───────────────────────────────────────────

  Future<void> _testAndSave() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _mode = _Mode.testing;
      _statusMessage = 'Connecting…';
    });

    final url = _controller.text.trim().replaceAll(RegExp(r'/$'), '');
    final ok = await ApiService.instance.checkHealth(url);

    if (!mounted) return;
    if (ok) {
      await ApiService.instance.setBaseUrl(url);
      setState(() {
        _mode = _Mode.found;
        _statusMessage = 'Connected! Server is online.';
      });
      await Future.delayed(const Duration(milliseconds: 700));
      if (!mounted) return;
      _proceed();
    } else {
      setState(() {
        _mode = _Mode.notFound;
        _statusMessage =
            'Could not reach server. Check the URL and ensure both devices are on the same Wi-Fi.';
      });
    }
  }

  void _proceed() {
    if (widget.isSettings) {
      Navigator.pop(context);
    } else {
      Navigator.pushReplacementNamed(context, '/main');
    }
  }

  // ── Build ─────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      appBar: widget.isSettings
          ? AppBar(
              backgroundColor: AppTheme.cream,
              surfaceTintColor: Colors.transparent,
              title: const Text('Server Settings'),
            )
          : null,
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(28, 20, 28, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (!widget.isSettings) ...[
                const SizedBox(height: 24),
                _buildHeader(),
                const SizedBox(height: 40),
              ] else
                const SizedBox(height: 16),

              // ── Auto-detect card ───────────────────
              _buildAutoDetectCard(),

              const SizedBox(height: 16),

              // ── Divider ────────────────────────────
              Row(children: [
                const Expanded(child: Divider()),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text('or enter manually',
                      style: TextStyle(
                          fontSize: 12, color: AppTheme.slateLight)),
                ),
                const Expanded(child: Divider()),
              ]),

              const SizedBox(height: 16),

              // ── Manual URL ─────────────────────────
              _buildManualSection(),

              const SizedBox(height: 12),

              if (!widget.isSettings)
                TextButton(
                  onPressed: _isbusy ? null : _proceed,
                  child: const Text('Skip for now',
                      style: TextStyle(color: AppTheme.slateLight)),
                ),
            ],
          ),
        ),
      ),
    );
  }

  bool get _isbusy =>
      _mode == _Mode.scanning || _mode == _Mode.testing;

  Widget _buildHeader() {
    return Column(
      children: [
        AnimatedBuilder(
          animation: _pulse,
          builder: (context, child) => Transform.scale(
            scale: _mode == _Mode.scanning ? _pulse.value : 1.0,
            child: child,
          ),
          child: Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: _mode == _Mode.found
                  ? AppTheme.successGreen
                  : AppTheme.terracotta,
              shape: BoxShape.circle,
            ),
            child: Icon(
              _mode == _Mode.found
                  ? Icons.check_rounded
                  : Icons.wifi_find_rounded,
              size: 34,
              color: Colors.white,
            ),
          ),
        ),
        const SizedBox(height: 20),
        const Text(
          'Connect to Backend',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.w800,
            color: AppTheme.slateInk,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Auto-detect the server on your Wi-Fi, or enter the IP manually.',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 14,
            color: AppTheme.slateMid,
            height: 1.55,
          ),
        ),
      ],
    );
  }

  Widget _buildAutoDetectCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: AppTheme.peach,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.radar_rounded,
                    size: 18, color: AppTheme.terracotta),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Auto-Detect',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.slateInk,
                        )),
                    Text('Scans your Wi-Fi for the server',
                        style: TextStyle(
                            fontSize: 12, color: AppTheme.slateLight)),
                  ],
                ),
              ),
            ],
          ),

          // Progress bar during scan
          if (_mode == _Mode.scanning) ...[
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: _scanProgress,
                backgroundColor: AppTheme.divider,
                valueColor: const AlwaysStoppedAnimation(AppTheme.terracotta),
                minHeight: 5,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _foundUrl != null
                  ? 'Found: $_foundUrl'
                  : 'Scanning ${(_scanProgress * 254).toInt()} / 254 hosts…',
              style: const TextStyle(
                  fontSize: 11, color: AppTheme.slateMid),
            ),
          ],

          // Status message
          if (_statusMessage.isNotEmpty &&
              _mode != _Mode.scanning) ...[
            const SizedBox(height: 12),
            _StatusChip(mode: _mode, message: _statusMessage),
          ],

          const SizedBox(height: 16),

          ElevatedButton.icon(
            onPressed: _isbusy ? null : _autoDetect,
            icon: _mode == _Mode.scanning
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.search_rounded, size: 18),
            label: Text(_mode == _Mode.scanning
                ? 'Scanning…'
                : 'Find Server Automatically'),
          ),
        ],
      ),
    );
  }

  Widget _buildManualSection() {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextFormField(
            controller: _controller,
            keyboardType: TextInputType.url,
            autocorrect: false,
            enabled: !_isbusy,
            decoration: InputDecoration(
              hintText: 'http://192.168.1.42:8000',
              labelText: 'Server URL',
              prefixIcon: const Icon(Icons.dns_rounded,
                  color: AppTheme.terracotta, size: 20),
              filled: true,
              fillColor: AppTheme.surfaceWhite,
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppTheme.divider)),
              enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppTheme.divider)),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(
                    color: AppTheme.terracotta, width: 1.5),
              ),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) {
                return 'Enter the server URL';
              }
              final uri = Uri.tryParse(v.trim());
              if (uri == null || !uri.scheme.startsWith('http')) {
                return 'Must start with http:// or https://';
              }
              return null;
            },
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _isbusy ? null : _testAndSave,
            icon: _mode == _Mode.testing
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppTheme.terracotta),
                  )
                : const Icon(Icons.check_rounded, size: 18),
            label: Text(
                _mode == _Mode.testing ? 'Testing…' : 'Test & Save'),
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  final _Mode mode;
  final String message;
  const _StatusChip({required this.mode, required this.message});

  @override
  Widget build(BuildContext context) {
    final isGood = mode == _Mode.found;
    final color = isGood ? AppTheme.successGreen : AppTheme.errorRed;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          Icon(
            isGood ? Icons.check_circle_rounded : Icons.error_outline_rounded,
            size: 14,
            color: color,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(message,
                style: TextStyle(fontSize: 12, color: color)),
          ),
        ],
      ),
    );
  }
}

enum _Mode { idle, scanning, testing, found, notFound }
