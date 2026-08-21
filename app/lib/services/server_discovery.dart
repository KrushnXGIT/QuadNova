import 'dart:async';
import 'dart:io';

/// Auto-discovers the HemoScan AI backend on the local network.
///
/// Strategy:
///   1. Get device's own WiFi IPv4 address → extract subnet (e.g. 192.168.1.x)
///   2. Fire parallel HTTP HEAD requests to all 254 hosts on port 8000
///   3. Return the first URL that responds to GET /health with HTTP 200
///
/// Typical discovery time: < 3 seconds on a home/office WiFi.
class ServerDiscovery {
  ServerDiscovery._();

  static const int kPort = 8000;
  static const Duration kProbeTimeout = Duration(seconds: 3);
  static const Duration kScanTimeout = Duration(seconds: 8);

  /// Returns the discovered base URL (e.g. "http://192.168.1.42:8000")
  /// or null if nothing found within [kScanTimeout].
  ///
  /// [onProgress] is called with a 0.0–1.0 value as the scan advances.
  static Future<String?> discover({
    void Function(double progress, String? found)? onProgress,
  }) async {
    final subnets = await _getSubnets();
    if (subnets.isEmpty) return null;

    // Try the device's own subnet first (most common case)
    final subnet = subnets.first;

    final completer = Completer<String?>();
    int completed = 0;
    int found = 0;

    for (int i = 1; i <= 254; i++) {
      final ip = '$subnet.$i';
      final url = 'http://$ip:$kPort';

      _probe(url).then((ok) {
        completed++;
        final progress = completed / 254.0;

        if (ok && found == 0) {
          found++;
          onProgress?.call(progress, url);
          if (!completer.isCompleted) completer.complete(url);
        } else {
          onProgress?.call(progress, null);
        }

        if (completed == 254 && !completer.isCompleted) {
          completer.complete(null);
        }
      });
    }

    return completer.future.timeout(kScanTimeout, onTimeout: () => null);
  }

  /// Quick check — open TCP + GET /health, expect 200.
  static Future<bool> _probe(String url) async {
    try {
      final client = HttpClient()
        ..connectionTimeout = kProbeTimeout
        ..idleTimeout = kProbeTimeout;

      final req = await client
          .getUrl(Uri.parse('$url/health'))
          .timeout(kProbeTimeout);
      req.headers.set('Connection', 'close');
      final res = await req.close().timeout(kProbeTimeout);
      await res.drain<void>();
      client.close();
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Returns IPv4 subnet prefixes (e.g. ["192.168.1"]) from all
  /// non-loopback, non-link-local interfaces.
  static Future<List<String>> _getSubnets() async {
    try {
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLoopback: false,
      );

      final subnets = <String>[];
      for (final iface in interfaces) {
        for (final addr in iface.addresses) {
          final ip = addr.address;
          // Skip loopback and link-local (169.254.x.x)
          if (ip.startsWith('127.') || ip.startsWith('169.254.')) continue;
          final parts = ip.split('.');
          if (parts.length == 4) {
            subnets.add('${parts[0]}.${parts[1]}.${parts[2]}');
          }
        }
      }
      return subnets;
    } catch (_) {
      return [];
    }
  }
}
