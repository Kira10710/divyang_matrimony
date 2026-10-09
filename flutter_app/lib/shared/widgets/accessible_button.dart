import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

/// Visual treatment for [AccessibleButton].
enum AccessibleButtonVariant { filled, outlined, text }

/// A button that bakes in the accessibility/loading conventions every auth
/// screen needs, instead of re-deriving them per screen:
///
/// - Meets the minimum touch target via `AppTheme`'s button themes.
/// - Replaces its label with a spinner (without changing size/layout) while
///   [isLoading] — and disables itself, so a slow network call can't be
///   double-submitted.
/// - Exposes a [Semantics] label distinct from the visible text when the
///   two need to differ (e.g. an icon-only affordance).
class AccessibleButton extends StatelessWidget {
  const AccessibleButton({
    required this.label,
    super.key,
    this.onPressed,
    this.isLoading = false,
    this.variant = AccessibleButtonVariant.filled,
    this.icon,
    this.semanticLabel,
    this.expand = true,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool isLoading;
  final AccessibleButtonVariant variant;
  final IconData? icon;
  final String? semanticLabel;

  /// Whether the button stretches to fill its parent's width — the default,
  /// since every primary auth action is a full-width button.
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final bool disabled = onPressed == null || isLoading;
    final ColorScheme colors = Theme.of(context).colorScheme;

    final Color spinnerColor = switch (variant) {
      AccessibleButtonVariant.filled => colors.onPrimary,
      AccessibleButtonVariant.outlined ||
      AccessibleButtonVariant.text => colors.primary,
    };

    final Widget child = isLoading
        ? SizedBox(
            height: 20,
            width: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              valueColor: AlwaysStoppedAnimation<Color>(spinnerColor),
            ),
          )
        : icon == null
        ? Text(label)
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(icon, size: 20),
              const SizedBox(width: Spacing.sm),
              Text(label),
            ],
          );

    final Widget button = switch (variant) {
      AccessibleButtonVariant.filled => FilledButton(
        onPressed: disabled ? null : onPressed,
        child: child,
      ),
      AccessibleButtonVariant.outlined => OutlinedButton(
        onPressed: disabled ? null : onPressed,
        child: child,
      ),
      AccessibleButtonVariant.text => TextButton(
        onPressed: disabled ? null : onPressed,
        child: child,
      ),
    };

    return Semantics(
      button: true,
      enabled: !disabled,
      label: semanticLabel ?? label,
      excludeSemantics: true,
      child: expand ? SizedBox(width: double.infinity, child: button) : button,
    );
  }
}
