import 'package:flutter/material.dart';

import '../core/consent_strings.dart';
import '../services/consent_service.dart';
import '../theme/app_theme.dart';
import 'camera_screen.dart';

/// Shows the current consent wording when device-level consent is missing.
class ConsentScreen extends StatefulWidget {
  const ConsentScreen({super.key});

  @override
  State<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends State<ConsentScreen> {
  bool _agreed = false;
  bool _saving = false;

  Future<void> _continue() async {
    if (!_agreed || _saving) return;
    setState(() => _saving = true);
    final grant = await ConsentService.instance.saveCurrentConsent();
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => CameraScreen(
          consentGiven: true,
          consentVersion: grant.version,
          consentTimestamp: grant.timestamp,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      appBar: AppBar(
        backgroundColor: AppTheme.cream,
        title: const Text(ConsentStrings.title),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(ConsentStrings.subtitle,
                        style: TextStyle(fontSize: 16, height: 1.5,
                            color: AppTheme.slateMid)),
                    const SizedBox(height: 20),
                    _section(
                      title: ConsentStrings.whatWillHappen,
                      child: Column(
                        children: [
                          for (var i = 0; i < ConsentStrings.steps.length; i++)
                            _Step(number: i + 1, text: ConsentStrings.steps[i]),
                        ],
                      ),
                    ),
                    const SizedBox(height: 14),
                    _section(
                      title: 'Image and data',
                      child: const Text(ConsentStrings.dataUse,
                          style: TextStyle(fontSize: 14, height: 1.55,
                              color: AppTheme.slateMid)),
                    ),
                    const SizedBox(height: 14),
                    _section(
                      title: ConsentStrings.important,
                      child: const Text(ConsentStrings.disclaimer,
                          style: TextStyle(fontSize: 14, height: 1.55,
                              color: AppTheme.terracottaDark)),
                      color: AppTheme.peach,
                    ),
                  ],
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
              decoration: const BoxDecoration(color: AppTheme.surfaceWhite),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Material(
                    color: Colors.transparent,
                    child: CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      value: _agreed,
                      onChanged: (value) => setState(() => _agreed = value ?? false),
                      title: const Text(ConsentStrings.agree,
                          style: TextStyle(fontSize: 14, height: 1.35,
                              color: AppTheme.slateDeep)),
                    ),
                  ),
                  const SizedBox(height: 6),
                  ElevatedButton(
                    onPressed: _agreed && !_saving ? _continue : null,
                    child: _saving
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text(ConsentStrings.continueLabel),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _section({required String title, required Widget child, Color? color}) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color ?? AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 15,
              fontWeight: FontWeight.w700, color: AppTheme.slateDeep)),
          const SizedBox(height: 10),
          child,
        ],
      ),
    );
  }
}

class _Step extends StatelessWidget {
  final int number;
  final String text;
  const _Step({required this.number, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(radius: 11, backgroundColor: AppTheme.terracotta,
              child: Text('$number', style: const TextStyle(fontSize: 11,
                  color: Colors.white, fontWeight: FontWeight.w700))),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 14,
              height: 1.45, color: AppTheme.slateMid))),
        ],
      ),
    );
  }
}
