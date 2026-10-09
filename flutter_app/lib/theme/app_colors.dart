import 'package:flutter/material.dart';

/// Semantic color palette.
///
/// All colors are 4.5:1 contrast ratio for normal text, 3:1 for large text.
/// High-contrast mode uses [HighContrastColors] instead.
class AppColors {
  AppColors._();

  // Primary — deep rose (white text on it is ≥ 7:1)
  static const Color primary = Color(0xFF9C2451);
  static const Color primaryLight = Color(0xFFC94F7C);
  static const Color primaryDark = Color(0xFF6A1236);
  static const Color onPrimary = Colors.white;

  // Secondary — marigold accent (use dark text on it, never white)
  static const Color secondary = Color(0xFFE8A33D);
  static const Color onSecondary = Color(0xFF2B1700);

  // Landing hero gradient (white text ≥ 4.5:1 across the whole ramp)
  static const Color heroStart = Color(0xFF4A0D26);
  static const Color heroMid = Color(0xFF7A1A42);
  static const Color heroEnd = Color(0xFFA8325A);
  static const Color heroGold = Color(0xFFF5C977);

  // Soft warm surface for alternating landing sections
  static const Color blush = Color(0xFFFFF4F1);

  // Surface
  static const Color surface = Color(0xFFFAFAFA);
  static const Color surfaceDark = Color(0xFF121212);
  static const Color onSurface = Color(0xFF1C1B1F);
  static const Color onSurfaceDark = Color(0xFFE6E1E5);

  // Background
  static const Color background = Colors.white;
  static const Color backgroundDark = Color(0xFF1C1B1F);

  // Semantic
  static const Color error = Color(0xFFBA1A1A);
  static const Color success = Color(0xFF2E7D32);
  static const Color warning = Color(0xFFF9A825);
  static const Color info = Color(0xFF0288D1);

  // Neutral
  static const Color divider = Color(0xFFE0E0E0);
  static const Color disabled = Color(0xFFBDBDBD);
  static const Color textSecondary = Color(0xFF757575);
}
