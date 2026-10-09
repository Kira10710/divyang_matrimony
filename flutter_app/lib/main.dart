import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'config/env/env_config.dart';
import 'config/env/flavor.dart';

/// Default entry point — uses the environment specified by --dart-define=FLAVOR
/// Falls back to [Flavor.dev] if not set.
void main() {
  WidgetsFlutterBinding.ensureInitialized();

  final flavor = Flavor.fromString(
    const String.fromEnvironment('FLAVOR', defaultValue: 'dev'),
  );

  EnvConfig.initialize(flavor);

  runApp(const ProviderScope(child: DivyangMatrimonyApp()));
}
