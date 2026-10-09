import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../routing/route_names.dart';
import '../../../../shared/widgets/accessible_button.dart';
import '../../../../shared/widgets/responsive_scaffold.dart';
import '../../../../theme/design_tokens.dart';

/// Shown when [SessionManager] forces a logout because a refresh-token call
/// was rejected by the backend (revoked/expired session) — distinct from a
/// user tapping "Log out." `routing/app_router.dart` navigates here
/// imperatively when `sessionExpiredEventProvider` fires; this screen is
/// purely informational and has no state of its own.
class SessionExpiredScreen extends StatelessWidget {
  const SessionExpiredScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;

    return ResponsiveScaffold(
      body: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(Icons.lock_clock_outlined, size: 56, color: colors.primary),
          const SizedBox(height: Spacing.lg),
          Text(
            'Your session has expired',
            style: textTheme.headlineSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: Spacing.sm),
          Text(
            'For your security, you were signed out. Please log in again to continue.',
            style: textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: Spacing.xl),
          AccessibleButton(
            label: 'Log in again',
            onPressed: () => context.go(RouteNames.welcome),
          ),
        ],
      ),
    );
  }
}
