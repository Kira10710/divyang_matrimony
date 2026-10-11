import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'features/settings/presentation/providers/accessibility_provider.dart';
import 'demo/demo_mode.dart';
import 'routing/app_router.dart';
import 'theme/high_contrast_theme.dart';
import 'theme/app_theme.dart';

/// Root widget — ProviderScope wraps this in main.dart.
/// Holds MaterialApp.router with GoRouter (reading Riverpod auth state via
/// [routerProvider]) and theme configuration.
class DivyangMatrimonyApp extends ConsumerWidget {
  const DivyangMatrimonyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'Divyang Matrimony',
      debugShowCheckedModeBanner: false,
      theme: ref.watch(highContrastProvider)
          ? HighContrastTheme.light()
          : AppTheme.light(),
      darkTheme: ref.watch(highContrastProvider)
          ? HighContrastTheme.dark()
          : AppTheme.dark(),
      builder: (BuildContext context, Widget? child) =>
          MediaQuery.withClampedTextScaling(
            minScaleFactor: ref.watch(textScaleProvider),
            maxScaleFactor: ref.watch(textScaleProvider),
            child: child!,
          ),
      // The showcase follows the brand look in every state, not system dark.
      themeMode: kDemoMode ? ThemeMode.light : ThemeMode.system,
      routerConfig: ref.watch(routerProvider),
    );
  }
}
