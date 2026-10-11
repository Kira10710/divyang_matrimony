import 'package:flutter_riverpod/flutter_riverpod.dart';

/// App-wide text scale (1.0 = system default), applied in app.dart.
final StateProvider<double> textScaleProvider = StateProvider<double>(
  (Ref ref) => 1.0,
);

final StateProvider<bool> highContrastProvider = StateProvider<bool>(
  (Ref ref) => false,
);
