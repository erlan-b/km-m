import 'package:flutter/material.dart';

class AppTheme {
  AppTheme._();

  // ── Colors (from admin CSS variables) ──
  static const accent = Color(0xFFD97745);
  static const accentHover = Color(0xFFC86635);
  static const accentPressed = Color(0xFFAE572B);
  static const bgPage = Color(0xFFFAF9F6);
  static const bgSurface = Color(0xFFF8F6F1);
  static const bgMuted = Color(0xFFF3F1EA);
  static const textMain = Color(0xFF111111);
  static const textSubtle = Color(0xFF3C3C3C);
  static const border = Color(0xFFDFDBD1);
  static const focus = Color(0xFFE79A6E);
  static const white = Color(0xFFFAF8F2);

  static const statusSuccess = Color(0xFF2A5E28);
  static const statusSuccessBg = Color(0xFFEAF8E9);
  static const statusError = Color(0xFF7A0000);
  static const statusErrorBg = Color(0xFFFFF0F0);
  static const statusWarningBg = Color(0xFFFFF6DF);
  static const bookmarkActive = Color(0xFFFFC107);

  static const radius = 8.0;
  static const cardRadius = 12.0;

  static ThemeData get light {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: accent,
      brightness: Brightness.light,
      surface: bgSurface,
      primary: accent,
      onPrimary: Colors.white,
      error: const Color(0xFFB80000),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: bgPage,
      fontFamily: 'Inter',
      appBarTheme: const AppBarTheme(
        backgroundColor: bgSurface,
        foregroundColor: textMain,
        elevation: 0,
        scrolledUnderElevation: 1,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          fontFamily: 'Inter',
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: textMain,
        ),
      ),
      cardTheme: CardThemeData(
        color: bgSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(cardRadius),
          side: const BorderSide(color: border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: white,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 12,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: const BorderSide(color: accent, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: BorderSide(color: colorScheme.error),
        ),
        hintStyle: const TextStyle(color: textSubtle, fontSize: 14),
        labelStyle: const TextStyle(color: textSubtle, fontSize: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radius),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textMain,
          minimumSize: const Size(double.infinity, 48),
          side: const BorderSide(color: border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radius),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: accent,
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: bgMuted,
        selectedColor: accent,
        side: const BorderSide(color: border),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
        ),
        labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
      ),
      dividerTheme: const DividerThemeData(
        color: border,
        thickness: 1,
        space: 0,
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: bgSurface,
        selectedItemColor: accent,
        unselectedItemColor: textSubtle,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: textMain,
        contentTextStyle: const TextStyle(color: Colors.white, fontSize: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
        ),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
