import 'dart:math';
import 'package:flutter/material.dart';

/// Dashed eye-guide overlay drawn on top of the camera preview.
///
/// Draws a rounded-rectangle guide in the centre of the screen
/// with dashed borders and corner brackets.
class EyeGuideOverlay extends StatelessWidget {
  const EyeGuideOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _EyeGuidePainter(),
      size: Size.infinite,
    );
  }
}

class _EyeGuidePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height * 0.42; // slightly above centre
    final guideW = size.width * 0.72;
    final guideH = guideW * 0.55;

    final rect = Rect.fromCenter(
      center: Offset(cx, cy),
      width: guideW,
      height: guideH,
    );

    // Semi-transparent overlay outside the guide
    final overlayPaint = Paint()
      ..color = Colors.black.withValues(alpha: 0.35)
      ..style = PaintingStyle.fill;

    // Cut out the guide area
    final fullRect = Rect.fromLTWH(0, 0, size.width, size.height);
    final rrect = RRect.fromRectAndRadius(rect, const Radius.circular(16));

    canvas.saveLayer(fullRect, Paint());
    canvas.drawRect(fullRect, overlayPaint);
    canvas.drawRRect(
      rrect,
      Paint()..blendMode = BlendMode.clear,
    );
    canvas.restore();

    // Dashed border
    _drawDashedRRect(canvas, rrect, size);

    // Corner brackets
    _drawCornerBrackets(canvas, rect);
  }

  void _drawDashedRRect(Canvas canvas, RRect rrect, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    const dashLen = 8.0;
    const gapLen = 6.0;

    // Approximate by drawing dashes along the perimeter
    final path = Path()..addRRect(rrect);
    final metrics = path.computeMetrics();

    for (final metric in metrics) {
      var distance = 0.0;
      while (distance < metric.length) {
        final end = min(distance + dashLen, metric.length);
        final segment = metric.extractPath(distance, end);
        canvas.drawPath(segment, paint);
        distance += dashLen + gapLen;
      }
    }
  }

  void _drawCornerBrackets(Canvas canvas, Rect rect) {
    final paint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;

    const len = 22.0;
    const offset = -4.0; // extend past corner

    // Top-left
    canvas.drawLine(
      Offset(rect.left + offset, rect.top + len),
      Offset(rect.left + offset, rect.top + offset),
      paint,
    );
    canvas.drawLine(
      Offset(rect.left + offset, rect.top + offset),
      Offset(rect.left + len, rect.top + offset),
      paint,
    );

    // Top-right
    canvas.drawLine(
      Offset(rect.right - len, rect.top + offset),
      Offset(rect.right - offset, rect.top + offset),
      paint,
    );
    canvas.drawLine(
      Offset(rect.right - offset, rect.top + offset),
      Offset(rect.right - offset, rect.top + len),
      paint,
    );

    // Bottom-left
    canvas.drawLine(
      Offset(rect.left + offset, rect.bottom - len),
      Offset(rect.left + offset, rect.bottom - offset),
      paint,
    );
    canvas.drawLine(
      Offset(rect.left + offset, rect.bottom - offset),
      Offset(rect.left + len, rect.bottom - offset),
      paint,
    );

    // Bottom-right
    canvas.drawLine(
      Offset(rect.right - len, rect.bottom - offset),
      Offset(rect.right - offset, rect.bottom - offset),
      paint,
    );
    canvas.drawLine(
      Offset(rect.right - offset, rect.bottom - offset),
      Offset(rect.right - offset, rect.bottom - len),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
