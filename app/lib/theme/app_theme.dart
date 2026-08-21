import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// HemoScan AI — Anthropic-inspired "Claude" design system.
///
/// Warm cream backgrounds, earthy terracotta orange accents,
/// slate ink text. Restrained, human-centric, premium.
class AppTheme {
  AppTheme._();

  // ── Official "Claude-inspired" Palette ──────────────────
  static const Color cream       = Color(0xFFFAF3E7); // warm ivory cream bg
  static const Color surfacePaper= Color(0xFFF4F0E8); // card/section bg
  static const Color surfaceWhite= Color(0xFFFFFFFF); // pure white surfaces
  static const Color peach       = Color(0xFFFDE8D8); // light orange tint
  static const Color terracotta  = Color(0xFFD97757); // primary CTA orange
  static const Color terracottaDark = Color(0xFFC15F3C); // darker terracotta
  static const Color terracottaLight= Color(0xFFF0A07A); // light orange accent
  static const Color slateInk    = Color(0xFF141413); // near-black text
  static const Color slateDeep   = Color(0xFF2E2B28); // dark brown text
  static const Color slateMid    = Color(0xFF6B6560); // mid warm gray
  static const Color slateLight  = Color(0xFFB1ADA1); // light warm gray
  static const Color divider     = Color(0xFFE8E0D4); // warm divider
  static const Color successGreen= Color(0xFF3D9970); // muted medical green
  static const Color errorRed    = Color(0xFFCC4A3A); // muted error red

  // ── Light Theme ─────────────────────────────────────────
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: cream,
      colorScheme: const ColorScheme.light(
        primary: terracotta,
        secondary: terracottaLight,
        surface: surfaceWhite,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: slateInk,
        error: errorRed,
      ),

      // ── AppBar ─────────────────────────────────────────
      appBarTheme: AppBarTheme(
        backgroundColor: cream,
        foregroundColor: slateInk,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        surfaceTintColor: Colors.transparent,
        shadowColor: Colors.transparent,
        titleTextStyle: GoogleFonts.inter(
          fontSize: 17,
          fontWeight: FontWeight.w700,
          color: slateInk,
          letterSpacing: -0.2,
        ),
        iconTheme: const IconThemeData(color: slateDeep),
      ),

      // ── Elevated Button ────────────────────────────────
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: terracotta,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          elevation: 0,
          textStyle: GoogleFonts.inter(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.1,
          ),
        ),
      ),

      // ── Outlined Button ────────────────────────────────
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: terracotta,
          side: const BorderSide(color: terracotta, width: 1.5),
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: GoogleFonts.inter(
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),

      // ── Text Theme ─────────────────────────────────────
      textTheme: TextTheme(
        headlineLarge: GoogleFonts.inter(
          fontSize: 30,
          fontWeight: FontWeight.w800,
          color: slateInk,
          height: 1.15,
          letterSpacing: -0.8,
        ),
        headlineMedium: GoogleFonts.inter(
          fontSize: 24,
          fontWeight: FontWeight.w700,
          color: slateInk,
          height: 1.2,
          letterSpacing: -0.5,
        ),
        headlineSmall: GoogleFonts.inter(
          fontSize: 19,
          fontWeight: FontWeight.w700,
          color: slateInk,
          height: 1.3,
        ),
        titleLarge: GoogleFonts.inter(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: slateInk,
          letterSpacing: -0.1,
        ),
        titleMedium: GoogleFonts.inter(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: slateDeep,
        ),
        bodyLarge: GoogleFonts.inter(
          fontSize: 15,
          fontWeight: FontWeight.w400,
          color: slateMid,
          height: 1.65,
        ),
        bodyMedium: GoogleFonts.inter(
          fontSize: 14,
          fontWeight: FontWeight.w400,
          color: slateMid,
          height: 1.6,
        ),
        bodySmall: GoogleFonts.inter(
          fontSize: 12,
          fontWeight: FontWeight.w400,
          color: slateLight,
          height: 1.5,
        ),
        labelSmall: GoogleFonts.inter(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: slateLight,
          letterSpacing: 0.3,
        ),
      ),

      // ── Card ───────────────────────────────────────────
      cardTheme: CardThemeData(
        color: surfaceWhite,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: divider, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),

      // ── Input ──────────────────────────────────────────
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfacePaper,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: divider),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: divider),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: terracotta, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 15,
        ),
        hintStyle: GoogleFonts.inter(fontSize: 15, color: slateLight),
      ),

      // ── Divider ────────────────────────────────────────
      dividerTheme: const DividerThemeData(color: divider, thickness: 1),

      // ── SnackBar ───────────────────────────────────────
      snackBarTheme: SnackBarThemeData(
        backgroundColor: slateDeep,
        contentTextStyle: GoogleFonts.inter(color: Colors.white),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Dark camera theme — full-screen camera/preview only.
  static ThemeData get cameraTheme => ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0F0A08),
      );
}
