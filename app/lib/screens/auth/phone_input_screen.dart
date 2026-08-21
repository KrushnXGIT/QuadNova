import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../services/auth_service.dart';
import '../../theme/app_theme.dart';

/// Phone number input screen for OTP authentication.
class PhoneInputScreen extends StatefulWidget {
  const PhoneInputScreen({super.key});

  @override
  State<PhoneInputScreen> createState() => _PhoneInputScreenState();
}

class _PhoneInputScreenState extends State<PhoneInputScreen> {
  final _phoneController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _isSending = false;

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _sendOtp() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSending = true);

    final phone = '+91${_phoneController.text.trim()}';
    final sent = await AuthService().sendOtp(phone);

    if (!mounted) return;
    setState(() => _isSending = false);

    if (sent) {
      Navigator.pushNamed(context, '/auth/otp', arguments: phone);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to send OTP. Try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Spacer(flex: 2),

                // ── Icon ──────────────────────────────
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: AppTheme.terracotta.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: const Icon(
                    Icons.phone_android_rounded,
                    size: 32,
                    color: AppTheme.terracotta,
                  ),
                ),

                const SizedBox(height: 28),

                // ── Title ─────────────────────────────
                Text(
                  'Enter your\nmobile number',
                  style: Theme.of(context).textTheme.headlineLarge,
                ),

                const SizedBox(height: 12),

                Text(
                  "We'll send you a verification code to confirm your identity.",
                  style: Theme.of(context).textTheme.bodyMedium,
                ),

                const SizedBox(height: 36),

                // ── Phone input ───────────────────────
                TextFormField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  maxLength: 10,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.slateInk,
                    letterSpacing: 1.2,
                  ),
                  decoration: InputDecoration(
                    counterText: '',
                    prefixIcon: Container(
                      padding: const EdgeInsets.only(left: 16, right: 8),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            '🇮🇳  +91',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.slateInk,
                            ),
                          ),
                          SizedBox(width: 8),
                          SizedBox(
                            height: 24,
                            child: VerticalDivider(
                              width: 1,
                              color: AppTheme.divider,
                            ),
                          ),
                        ],
                      ),
                    ),
                    hintText: '98765 43210',
                  ),
                  validator: (value) {
                    if (value == null || value.trim().length != 10) {
                      return 'Enter a valid 10-digit mobile number';
                    }
                    return null;
                  },
                ),

                const SizedBox(height: 28),

                // ── CTA ───────────────────────────────
                SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: ElevatedButton(
                    onPressed: _isSending ? null : _sendOtp,
                    child: _isSending
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.5,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Send OTP'),
                  ),
                ),

                const Spacer(flex: 3),

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
                          'Dev mode — OTP is 123456',
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
      ),
    );
  }
}
