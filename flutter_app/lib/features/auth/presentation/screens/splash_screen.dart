import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../shared/widgets/app_logo_mark.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../domain/entities/auth_user.dart';
import '../providers/auth_provider.dart';

/// The app's initial route. Its only job is to render *something* branded
/// while [AuthNotifier] restores whatever session is cached on-device —
/// `routing/guards/auth_guard.dart` handles navigating away the moment that
/// finishes (to Welcome or Home), so this screen never navigates itself.
class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<AuthUser?> authState = ref.watch(authProvider);

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                const AppLogoMark(),
                const SizedBox(height: 24),
                Text(
                  AppConstants.appName,
                  style: Theme.of(context).textTheme.headlineMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 40),
                authState.when(
                  data: (_) => const SizedBox(height: 32, width: 32),
                  loading: () => const LoadingIndicator(),
                  error: (Object error, StackTrace stackTrace) => ErrorView(
                    message: 'Something went wrong while starting the app.',
                    onRetry: () => ref.invalidate(authProvider),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
