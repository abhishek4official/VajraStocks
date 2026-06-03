import 'package:flutter/material.dart';

class VajraTheme {
  static const Color darkBackground = Color(0xFF07080A);
  static const Color darkCard = Color(0xFF0D0F14);
  static const Color primaryPurple = Color(0xFF7C3AED);
  static const Color accentGreen = Color(0xFF34D399); // Emerald Up-trend
  static const Color accentRed = Color(0xFFF87171);   // Rose Down-trend
  static const Color textPrimary = Color(0xFFF1F5F9);
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color borderSlate = Color(0xFF1E293B);

  static ThemeData get darkThemeData {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: darkBackground,
      colorScheme: const ColorScheme.dark(
        primary: primaryPurple,
        surface: darkCard,
        error: accentRed,
        outline: borderSlate,
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: textPrimary),
        headlineSmall: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: textPrimary),
        bodyLarge: TextStyle(fontSize: 14, color: textPrimary, height: 1.5),
        bodyMedium: TextStyle(fontSize: 12, color: textSecondary),
        labelLarge: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: textPrimary),
      ),
      cardTheme: CardThemeData(
        color: darkCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: borderSlate, width: 0.8),
        ),
        margin: EdgeInsets.zero,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: darkCard,
        indicatorColor: primaryPurple.withOpacity(0.2),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
    );
  }
}
