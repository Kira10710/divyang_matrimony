import 'package:flutter/material.dart';

import '../../core/constants/app_constants.dart';

/// Decorative brand mark used on the splash and welcome screens.
///
/// The project has no bundled logo asset yet (`assets/images/` is still
/// empty — see `AssetPaths.logo`), so this draws a themed placeholder
/// instead of shipping a broken `Image.asset` call. Swap the body of
/// [build] for an `Image.asset(AssetPaths.logo)` once real artwork lands;
/// every call site references this widget, not the asset path directly.
class AppLogoMark extends StatelessWidget {
  const AppLogoMark({super.key, this.size = 96});

  final double size;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Semantics(
      label: '${AppConstants.appName} logo',
      image: true,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              colors.primary,
              Color.lerp(colors.primary, Colors.black, 0.4)!,
            ],
          ),
        ),
        child: Icon(
          Icons.volunteer_activism_rounded,
          color: colors.onPrimary,
          size: size * 0.5,
        ),
      ),
    );
  }
}
