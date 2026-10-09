import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../../core/constants/app_constants.dart';
import '../../../../../routing/route_names.dart';
import '../../../../../shared/widgets/app_logo_mark.dart';
import '../../../../../theme/app_colors.dart';
import '../../../../../theme/design_tokens.dart';

/// Max width of every landing section's content column.
const double kLandingMaxWidth = 1180;

/// Centers [child] in a column no wider than [kLandingMaxWidth], with
/// side padding that shrinks on phones.
class LandingContainer extends StatelessWidget {
  const LandingContainer({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final double gutter = MediaQuery.sizeOf(context).width < 600
        ? Spacing.md
        : Spacing.lg;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: kLandingMaxWidth),
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: gutter),
          child: child,
        ),
      ),
    );
  }
}

class LandingTopBar extends StatelessWidget {
  const LandingTopBar({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final bool narrow = MediaQuery.sizeOf(context).width < 520;
    return Container(
      color: Theme.of(context).colorScheme.surface,
      padding: const EdgeInsets.symmetric(vertical: Spacing.sm),
      child: LandingContainer(
        child: Row(
          children: <Widget>[
            const AppLogoMark(size: 40),
            const SizedBox(width: Spacing.sm + 4),
            Flexible(
              child: Semantics(
                header: true,
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    AppConstants.appName,
                    style: text.titleLarge?.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
            const Spacer(),
            if (!narrow)
              TextButton(
                onPressed: () => showAboutDialog(
                  context: context,
                  applicationName: AppConstants.appName,
                  children: const <Widget>[
                    Text(
                      'A matrimony platform for people with disabilities and their families. '
                      'Need help? Write to ${AppConstants.supportEmail}.',
                    ),
                  ],
                ),
                child: const Text('Help'),
              ),
            const SizedBox(width: Spacing.sm),
            OutlinedButton(
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(96, AppConstants.minTouchTargetSize),
              ),
              onPressed: () => context.go(RouteNames.login),
              child: const Text('Log in'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Full-width gradient hero: pitch + trust badge on the left, sign-up card
/// on the right (stacked on narrow screens), quick-search bar below.
class LandingHero extends StatelessWidget {
  const LandingHero({
    required this.registrationCard,
    required this.quickSearch,
    super.key,
  });

  final Widget registrationCard;
  final Widget quickSearch;

  @override
  Widget build(BuildContext context) {
    final double width = MediaQuery.sizeOf(context).width;
    final bool wide = width >= 1000;

    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[
            AppColors.heroStart,
            AppColors.heroMid,
            AppColors.heroEnd,
          ],
        ),
      ),
      child: CustomPaint(
        painter: _RangoliPainter(),
        child: Padding(
          padding: EdgeInsets.symmetric(
            vertical: wide ? Spacing.xxl + 16 : Spacing.xl,
          ),
          child: LandingContainer(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                if (wide)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: <Widget>[
                      const Expanded(child: _HeroPitch(large: true)),
                      const SizedBox(width: Spacing.xxl),
                      SizedBox(width: 420, child: registrationCard),
                    ],
                  )
                else ...<Widget>[
                  const _HeroPitch(large: false),
                  const SizedBox(height: Spacing.xl),
                  Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 480),
                      child: registrationCard,
                    ),
                  ),
                ],
                const SizedBox(height: Spacing.xl),
                quickSearch,
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HeroPitch extends StatelessWidget {
  const _HeroPitch({required this.large});

  final bool large;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final TextStyle? headline = (large ? text.displayLarge : text.headlineLarge)
        ?.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.w700,
          height: 1.1,
          fontSize: large ? 54 : 34,
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const _ConfidentialBadge(),
        const SizedBox(height: Spacing.lg),
        Semantics(
          header: true,
          child: Text.rich(
            TextSpan(
              children: <InlineSpan>[
                const TextSpan(text: 'A life partner who '),
                TextSpan(
                  text: 'truly understands',
                  style: headline?.copyWith(color: AppColors.heroGold),
                ),
                const TextSpan(text: ' your journey.'),
              ],
            ),
            style: headline,
          ),
        ),
        const SizedBox(height: Spacing.md),
        Text(
          'India’s matrimony service made for people with disabilities — '
          'and the families who search alongside them.',
          style: (large ? text.titleLarge : text.titleMedium)?.copyWith(
            color: Colors.white.withValues(alpha: 0.92),
            height: 1.45,
            fontWeight: FontWeight.w400,
          ),
        ),
        const SizedBox(height: Spacing.lg),
        const Wrap(
          spacing: Spacing.sm,
          runSpacing: Spacing.sm,
          children: <Widget>[
            _HeroChip(
              icon: Icons.verified_rounded,
              label: 'Every profile reviewed',
            ),
            _HeroChip(
              icon: Icons.accessibility_new_rounded,
              label: 'Screen-reader & large-text friendly',
            ),
            _HeroChip(
              icon: Icons.family_restroom_rounded,
              label: 'Parents can manage profiles',
            ),
          ],
        ),
      ],
    );
  }
}

/// Elite-style gold "confidential" pill, reworded for disability privacy.
class _ConfidentialBadge extends StatelessWidget {
  const _ConfidentialBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: Spacing.md,
        vertical: Spacing.sm,
      ),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(100),
        gradient: const LinearGradient(
          colors: <Color>[Color(0xFFF7D98F), Color(0xFFE2AE4F)],
        ),
        border: Border.all(color: const Color(0xFFFFE9B5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          const Icon(Icons.shield_outlined, size: 20, color: Color(0xFF3D2300)),
          const SizedBox(width: Spacing.sm),
          Flexible(
            child: Text(
              'Private & respectful — you control who sees your details',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: const Color(0xFF3D2300),
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _HeroChip extends StatelessWidget {
  const _HeroChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: Spacing.sm + 4,
        vertical: Spacing.sm,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(100),
        border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, size: 18, color: AppColors.heroGold),
          const SizedBox(width: Spacing.xs + 2),
          Text(
            label,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.white),
          ),
        ],
      ),
    );
  }
}

/// Faint concentric petal rings — a nod to rangoli, drawn so the hero has
/// texture without shipping a photo.
class _RangoliPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final Paint ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = AppColors.heroGold.withValues(alpha: 0.10);
    final Paint petal = Paint()..color = Colors.white.withValues(alpha: 0.035);

    void motif(Offset c, double r) {
      for (double k = 0.35; k <= 1.0; k += 0.22) {
        canvas.drawCircle(c, r * k, ring);
      }
      for (int i = 0; i < 12; i++) {
        final double a = i * math.pi / 6;
        final Offset p = c + Offset(math.cos(a), math.sin(a)) * r * 0.68;
        canvas.drawCircle(p, r * 0.16, petal);
      }
    }

    motif(
      Offset(size.width * 0.02, size.height * 0.08),
      size.shortestSide * 0.55,
    );
    motif(
      Offset(size.width * 0.98, size.height * 0.95),
      size.shortestSide * 0.7,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
