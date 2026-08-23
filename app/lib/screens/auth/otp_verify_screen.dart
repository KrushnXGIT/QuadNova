import 'dart:async';
import 'package:flutter/material.dart';
import 'package:pinput/pinput.dart';
import '../../services/auth_service.dart';
import '../../theme/app_theme.dart';

/// 6-digit OTP verification screen.
class OtpVerifyScreen extends StatefulWidget {
  final String phoneNumber;

  const OtpVerifyScreen({super.key, required this.phoneNumber});

  @override
  State<OtpVerifyScreen> createState() => _OtpVerifyScreenState();
}

class _OtpVerifyScreenState extends State<OtpVerifyScreen> {
  final _pinController = TextEditingController();
  final _focusNode = FocusNode();
  bool _isVerifying = false;
  String? _error;
  int _resendTimer = 30;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startResendTimer();
  }

  void _startResendTimer() {
    _resendTimer = 30;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (_resendTimer > 0) {
        setState(() => _resendTimer--);
      } else {
        t.cancel();
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pinController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  Future<void> _verify(String otp) async {
    setState(() {
      _isVerifying = true;
      _error = null;
    });

    final success = await AuthService().verifyOtp(widget.phoneNumber, otp);

    if (!mounted) return;

    if (success) {
      Navigator.pushNamedAndRemoveUntil(context, '/camera', (_) => false);
    } else {
      setState(() {
        _isVerifying = false;
        _error = 'Invalid OTP. Please try again.';
        _pinController.clear();
      });
      _focusNode.requestFocus();
    }
  }

  Future<void> _resendOtp() async {
    await AuthService().sendOtp(widget.phoneNumber);
    _startResendTimer();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('OTP resent!')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    // Pinput theme
    final defaultPinTheme = PinTheme(
      width: 52,
      height: 58,
      textStyle: const TextStyle(
        fontSize: 22,
        fontWeight: FontWeight.w700,
        color: AppTheme.slateInk,
      ),
      decoration: BoxDecoration(
        color: AppTheme.surfacePaper,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.divider),
      ),
    );

    final focusedPinTheme = defaultPinTheme.copyWith(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.terracotta, width: 2),
      ),
    );

    final errorPinTheme = defaultPinTheme.copyWith(
      decoration: BoxDecoration(
        color: AppTheme.errorRed.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.errorRed),
      ),
    );

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 16),

              // ── Title ─────────────────────────────
              Text(
                'Verify your\nnumber',
                style: Theme.of(context).textTheme.headlineLarge,
              ),

              const SizedBox(height: 12),

              Text(
                'Enter the 6-digit code sent to',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 4),
              Text(
                widget.phoneNumber,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.terracotta,
                ),
              ),

              const SizedBox(height: 40),

              // ── OTP Input ─────────────────────────
              Center(
                child: Pinput(
                  length: 6,
                  controller: _pinController,
                  focusNode: _focusNode,
                  defaultPinTheme: defaultPinTheme,
                  focusedPinTheme: focusedPinTheme,
                  errorPinTheme: errorPinTheme,
                  autofocus: true,
                  onCompleted: _verify,
                  errorText: _error,
                  hapticFeedbackType: HapticFeedbackType.lightImpact,
                ),
              ),

              if (_error != null) ...[
                const SizedBox(height: 12),
                Center(
                  child: Text(
                    _error!,
                    style: const TextStyle(
                      color: AppTheme.errorRed,
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],

              const SizedBox(height: 32),

              // ── Verifying indicator ────────────────
              if (_isVerifying)
                const Center(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppTheme.terracotta,
                        ),
                      ),
                      SizedBox(width: 10),
                      Text(
                        'Verifying…',
                        style: TextStyle(
                          color: AppTheme.slateMid,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),

              const SizedBox(height: 24),

              // ── Resend ────────────────────────────
              Center(
                child: _resendTimer > 0
                    ? Text(
                        'Resend code in ${_resendTimer}s',
                        style: Theme.of(context).textTheme.bodySmall,
                      )
                    : TextButton(
                        onPressed: _resendOtp,
                        child: const Text(
                          'Resend OTP',
                          style: TextStyle(
                            color: AppTheme.terracotta,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
              ),

              const Spacer(),

              // ── Dev hint ──────────────────────────
              Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: AppTheme.surfacePaper,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.bug_report_outlined,
                          size: 16, color: AppTheme.slateMid),
                      SizedBox(width: 8),
                      Text(
                        'Dev mode — enter 123456',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.slateMid,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}
