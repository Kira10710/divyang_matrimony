import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';
import 'accessible_button.dart';

/// Full-screen/full-section error state — icon, message, and an optional
/// retry action. Used where a screen has nothing else to show (e.g. the
/// splash screen if session restore genuinely fails).
class ErrorView extends StatelessWidget {
  const ErrorView({
    required this.message,
    super.key,
    this.onRetry,
    this.retryLabel = 'Try again',
    this.icon = Icons.error_outline,
  });

  final String message;
  final VoidCallback? onRetry;
  final String retryLabel;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(Spacing.lg),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, size: 48, color: colors.error, semanticLabel: 'Error'),
          const SizedBox(height: Spacing.md),
          Text(
            message,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          if (onRetry != null) ...<Widget>[
            const SizedBox(height: Spacing.lg),
            AccessibleButton(
              label: retryLabel,
              onPressed: onRetry,
              expand: false,
              variant: AccessibleButtonVariant.outlined,
            ),
          ],
        ],
      ),
    );
  }
}

/// A compact, inline error banner for form-level failures (e.g. "Invalid or
/// expired OTP") — announced to screen readers as soon as it appears via
/// `liveRegion`, without needing a SnackBar's transient timing.
class InlineErrorBanner extends StatelessWidget {
  const InlineErrorBanner({required this.message, super.key});

  final String message;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(Spacing.md),
        decoration: BoxDecoration(
          color: colors.errorContainer,
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(Icons.error_outline, color: colors.onErrorContainer, size: 20),
            const SizedBox(width: Spacing.sm),
            Expanded(
              child: Text(
                message,
                style: TextStyle(color: colors.onErrorContainer),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
