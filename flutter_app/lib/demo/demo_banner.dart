import 'package:flutter/material.dart';

import '../theme/design_tokens.dart';

/// Slim strip labelling the showcase build, so nobody mistakes the sample
/// profiles and disabled actions for a live service.
class DemoBanner extends StatelessWidget {
  const DemoBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label:
          'Demo preview. Profiles are fictional and nothing is sent or saved.',
      child: Container(
        width: double.infinity,
        color: const Color(0xFF2B1700),
        padding: const EdgeInsets.symmetric(
          horizontal: Spacing.md,
          vertical: Spacing.sm,
        ),
        child: const Text(
          'DEMO PREVIEW · fictional profiles · nothing is sent or saved',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Color(0xFFF5C977),
            fontSize: 13,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.4,
          ),
        ),
      ),
    );
  }
}
