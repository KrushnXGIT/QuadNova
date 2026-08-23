import 'package:flutter/material.dart';

import '../services/consent_service.dart';
import 'camera_screen.dart';
import 'consent_screen.dart';

/// Decides whether this device needs current consent before camera access.
class ScreeningEntryScreen extends StatefulWidget {
  const ScreeningEntryScreen({super.key});

  @override
  State<ScreeningEntryScreen> createState() => _ScreeningEntryScreenState();
}

class _ScreeningEntryScreenState extends State<ScreeningEntryScreen> {
  @override
  void initState() {
    super.initState();
    _openNextStep();
  }

  Future<void> _openNextStep() async {
    final grant = await ConsentService.instance.getCurrentConsent();
    if (!mounted) return;

    if (grant == null) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const ConsentScreen()),
      );
      return;
    }

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
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
