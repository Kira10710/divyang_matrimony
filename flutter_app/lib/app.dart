import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'routing/app_router.dart';
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
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.system,
      routerConfig: ref.watch(routerProvider),
    );
  }
}
