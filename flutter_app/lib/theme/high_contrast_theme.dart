import 'package:flutter/material.dart';

import '../core/constants/app_constants.dart';
import 'app_typography.dart';
import 'design_tokens.dart';

/// High-contrast theme — pure black/white contrast, thicker borders, no
/// translucent fills. Same token structure as [AppTheme], just different
/// values, per Architecture §9.2/§2.5.
///
/// Not wired into [AppTheme]/`app.dart` automatically — that requires an
/// accessibility-settings toggle (Architecture §9, `features/settings`),
/// which is a separate feature. Once that provider exists, swap
/// `MaterialApp.theme` between [AppTheme.light] and
/// [HighContrastTheme.light] based on it.
class HighContrastTheme {
  HighContrastTheme._();

  static const double _minTouchTarget = AppConstants.minTouchTargetSize;

  static ThemeData light() => _build(
    const ColorScheme(
      brightness: Brightness.light,
      primary: Colors.black,
      onPrimary: Colors.white,
      secondary: Colors.black,
      onSecondary: Colors.white,
      error: Color(0xFFB00020),
      onError: Colors.white,
      surface: Colors.white,
      onSurface: Colors.black,
      outline: Colors.black,
    ),
  );

  static ThemeData dark() => _build(
    const ColorScheme(
      brightness: Brightness.dark,
      primary: Colors.white,
      onPrimary: Colors.black,
      secondary: Colors.white,
      onSecondary: Colors.black,
      error: Color(0xFFFFB4AB),
      onError: Colors.black,
      surface: Colors.black,
      onSurface: Colors.white,
      outline: Colors.white,
    ),
  );

  static ThemeData _build(ColorScheme colorScheme) {
    final OutlineInputBorder border = OutlineInputBorder(
      borderRadius: BorderRadius.circular(AppRadius.md),
      borderSide: BorderSide(color: colorScheme.onSurface, width: 2),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      textTheme: AppTypography.textTheme.apply(
        bodyColor: colorScheme.onSurface,
        displayColor: colorScheme.onSurface,
      ),
      scaffoldBackgroundColor: colorScheme.surface,
      inputDecorationTheme: InputDecorationTheme(
        filled: false,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: Spacing.md,
          vertical: Spacing.md,
        ),
        border: border,
        enabledBorder: border,
        focusedBorder: border.copyWith(
          borderSide: BorderSide(color: colorScheme.primary, width: 3),
        ),
        errorBorder: border.copyWith(
          borderSide: BorderSide(color: colorScheme.error, width: 2),
        ),
        focusedErrorBorder: border.copyWith(
          borderSide: BorderSide(color: colorScheme.error, width: 3),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(_minTouchTarget + 4),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.button),
            side: BorderSide(color: colorScheme.onPrimary, width: 2),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(_minTouchTarget + 4),
          side: BorderSide(color: colorScheme.onSurface, width: 2),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.button),
          ),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: colorScheme.onSurface,
        thickness: 1.5,
      ),
    );
  }
}
