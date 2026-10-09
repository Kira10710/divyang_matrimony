import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'config/env/env_config.dart';
import 'config/env/flavor.dart';

/// Dev-specific entry point.
/// Use: flutter run -t lib/main_dev.dart
void main() {
  WidgetsFlutterBinding.ensureInitialized();

  EnvConfig.initialize(Flavor.dev);

  runApp(const ProviderScope(child: DivyangMatrimonyApp()));
}
