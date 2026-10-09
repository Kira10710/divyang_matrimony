import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'config/env/env_config.dart';
import 'config/env/flavor.dart';

/// Production entry point.
/// Use: flutter run -t lib/main_prod.dart --release
void main() {
  WidgetsFlutterBinding.ensureInitialized();

  EnvConfig.initialize(Flavor.prod);

  runApp(const ProviderScope(child: DivyangMatrimonyApp()));
}
