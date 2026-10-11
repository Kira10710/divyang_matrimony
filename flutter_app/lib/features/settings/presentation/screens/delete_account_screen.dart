import 'package:flutter/material.dart';

import '../../../../theme/design_tokens.dart';

/// Explains the 30-day cooling-off and asks for confirmation. Nothing is
/// deleted in the showcase build.
class DeleteAccountScreen extends StatelessWidget {
  const DeleteAccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Delete account')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Padding(
            padding: const EdgeInsets.all(Spacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Icon(
                  Icons.warning_amber_rounded,
                  size: 48,
                  color: colors.error,
                ),
                const SizedBox(height: Spacing.md),
                Text('Delete your account?', style: text.headlineSmall),
                const SizedBox(height: Spacing.sm),
                const Text(
                  'Your profile is hidden immediately. You have 30 days to '
                  'change your mind by logging in again; after that your '
                  'profile, photos and interests are permanently removed.',
                ),
                const SizedBox(height: Spacing.xl),
                FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: colors.error,
                    foregroundColor: colors.onError,
                  ),
                  onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Account deletion is disabled in this preview.',
                      ),
                    ),
                  ),
                  child: const Text('Delete my account'),
                ),
                const SizedBox(height: Spacing.sm),
                OutlinedButton(
                  onPressed: () => Navigator.of(context).maybePop(),
                  child: const Text('Keep my account'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
