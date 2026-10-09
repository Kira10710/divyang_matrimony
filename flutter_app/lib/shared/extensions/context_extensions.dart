import 'package:flutter/material.dart';

/// Small, widely-used `BuildContext` shortcuts — kept intentionally tiny
/// (theme lookups + a snackbar helper) so it doesn't grow into a dumping
/// ground for one-off screen logic.
extension BuildContextX on BuildContext {
  ThemeData get theme => Theme.of(this);

  TextTheme get textTheme => Theme.of(this).textTheme;

  ColorScheme get colors => Theme.of(this).colorScheme;

  /// True on tablet/desktop/web-sized viewports (shortest side ≥ 600dp,
  /// Material's standard breakpoint) — used to decide when a form should
  /// stop stretching edge-to-edge.
  bool get isTablet => MediaQuery.sizeOf(this).shortestSide >= 600;

  /// Shows a themed, accessible snackbar and replaces any currently visible
  /// one rather than queuing behind it — repeated errors (e.g. retapping
  /// "Resend OTP") should replace the message, not stack notifications.
  void showSnackBar(String message, {bool isError = false}) {
    final ColorScheme colorScheme = colors;
    ScaffoldMessenger.of(this)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: isError ? colorScheme.error : null,
          behavior: SnackBarBehavior.floating,
        ),
      );
  }
}
