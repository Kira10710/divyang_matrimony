import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../../core/constants/app_constants.dart';
import '../../../../../routing/route_names.dart';
import '../../../../../theme/app_colors.dart';
import '../../../../../theme/design_tokens.dart';
import 'landing_hero.dart';

/// Shared heading block for each landing section.
class _SectionHeading extends StatelessWidget {
  const _SectionHeading({
    required this.eyebrow,
    required this.title,
    this.subtitle,
  });

  final String eyebrow;
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    return Column(
      children: <Widget>[
        Text(
          eyebrow.toUpperCase(),
          style: text.labelLarge?.copyWith(
            color: AppColors.primary,
            letterSpacing: 1.6,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: Spacing.sm),
        Semantics(
          header: true,
          child: Text(
            title,
            textAlign: TextAlign.center,
            style: text.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
        ),
        if (subtitle != null) ...<Widget>[
          const SizedBox(height: Spacing.sm),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: Text(
              subtitle!,
              textAlign: TextAlign.center,
              style: text.bodyLarge?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                height: 1.5,
              ),
            ),
          ),
        ],
        const SizedBox(height: Spacing.xl),
      ],
    );
  }
}

/// Lays [children] out in up to [maxColumns] equal columns, dropping to
/// fewer as the viewport narrows.
class _ResponsiveGrid extends StatelessWidget {
  const _ResponsiveGrid({
    required this.children,
    this.maxColumns = 3,
    this.minItemWidth = 280,
  });

  final List<Widget> children;
  final int maxColumns;
  final double minItemWidth;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints c) {
        final int columns = (c.maxWidth / minItemWidth).floor().clamp(
          1,
          maxColumns,
        );
        final double itemWidth =
            (c.maxWidth - (columns - 1) * Spacing.md) / columns;
        return Wrap(
          spacing: Spacing.md,
          runSpacing: Spacing.md,
          children: <Widget>[
            for (final Widget child in children)
              SizedBox(width: itemWidth, child: child),
          ],
        );
      },
    );
  }
}

/// Thin value strip under the hero — honest claims only, no inflated stats.
class TrustStrip extends StatelessWidget {
  const TrustStrip({super.key});

  static const List<(IconData, String)> _items = <(IconData, String)>[
    (Icons.currency_rupee_rounded, 'Free to register'),
    (Icons.lock_rounded, 'Disability details encrypted'),
    (Icons.translate_rounded, 'English · हिन्दी · मराठी'),
    (Icons.chat_rounded, 'Chat on WhatsApp after a mutual match'),
  ];

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    return Container(
      width: double.infinity,
      color: AppColors.heroStart,
      padding: const EdgeInsets.symmetric(vertical: Spacing.md),
      child: LandingContainer(
        child: Wrap(
          alignment: WrapAlignment.center,
          spacing: Spacing.xl,
          runSpacing: Spacing.sm,
          children: <Widget>[
            for (final (IconData icon, String label) in _items)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(icon, size: 18, color: AppColors.heroGold),
                  const SizedBox(width: Spacing.sm),
                  Text(
                    label,
                    style: text.bodyMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

/// BharatMatrimony-style "browse by language" chips; picking one sets the
/// quick-search mother tongue.
class LanguageStrip extends StatelessWidget {
  const LanguageStrip({
    required this.languages,
    required this.onPick,
    super.key,
  });

  final List<String> languages;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColors.blush,
      padding: const EdgeInsets.symmetric(vertical: Spacing.xxl),
      child: LandingContainer(
        child: Column(
          children: <Widget>[
            const _SectionHeading(
              eyebrow: 'Matches in your language',
              title: 'Find someone who speaks your language',
              subtitle: 'Pick a mother tongue to start your search there.',
            ),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: Spacing.sm,
              runSpacing: Spacing.sm,
              children: <Widget>[
                for (final String lang in languages)
                  ActionChip(
                    avatar: const Icon(
                      Icons.favorite_border_rounded,
                      size: 18,
                      color: AppColors.primary,
                    ),
                    label: Text(lang),
                    tooltip: 'Search $lang matches',
                    backgroundColor: Colors.white,
                    onPressed: () => onPick(lang),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class HowItWorksSection extends StatelessWidget {
  const HowItWorksSection({super.key});

  static const List<(IconData, String, String)>
  _steps = <(IconData, String, String)>[
    (
      Icons.phone_iphone_rounded,
      'Register with your mobile',
      'No passwords. A one-time code confirms your number — for yourself, or for a family member.',
    ),
    (
      Icons.edit_note_rounded,
      'Tell your story, your way',
      'Share your disability, interests and family. Sensitive details stay private until you choose otherwise.',
    ),
    (
      Icons.favorite_rounded,
      'Connect when it’s mutual',
      'Send interest to profiles you like. When they accept, continue the conversation on WhatsApp.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Spacing.xxl + 16),
      child: LandingContainer(
        child: Column(
          children: <Widget>[
            const _SectionHeading(
              eyebrow: 'How it works',
              title: 'Three simple steps',
            ),
            _ResponsiveGrid(
              children: <Widget>[
                for (int i = 0; i < _steps.length; i++)
                  Semantics(
                    container: true,
                    label: 'Step ${i + 1}',
                    child: Column(
                      children: <Widget>[
                        Stack(
                          clipBehavior: Clip.none,
                          children: <Widget>[
                            CircleAvatar(
                              radius: 36,
                              backgroundColor: AppColors.blush,
                              child: Icon(
                                _steps[i].$1,
                                size: 34,
                                color: AppColors.primary,
                              ),
                            ),
                            Positioned(
                              right: -4,
                              top: -4,
                              child: CircleAvatar(
                                radius: 13,
                                backgroundColor: AppColors.secondary,
                                child: Text(
                                  '${i + 1}',
                                  style: text.labelLarge?.copyWith(
                                    color: AppColors.onSecondary,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: Spacing.md),
                        Text(
                          _steps[i].$2,
                          textAlign: TextAlign.center,
                          style: text.titleLarge,
                        ),
                        const SizedBox(height: Spacing.sm),
                        Text(
                          _steps[i].$3,
                          textAlign: TextAlign.center,
                          style: text.bodyLarge?.copyWith(
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurfaceVariant,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Explains the backend's visibility tiers (visibility_service.py) in plain
/// words — the single biggest worry when asked to disclose a disability.
class PrivacyLadderSection extends StatelessWidget {
  const PrivacyLadderSection({super.key});

  static const List<(IconData, String, String)>
  _tiers = <(IconData, String, String)>[
    (
      Icons.public_rounded,
      'Everyone',
      'First name, age, city and type of disability',
    ),
    (
      Icons.workspace_premium_rounded,
      'Premium members',
      'Disability percentage, since when, mobility aid, religion and family background',
    ),
    (
      Icons.handshake_rounded,
      'Only mutual matches',
      'Your personal note about your disability and health, phone and WhatsApp number',
    ),
    (
      Icons.lock_rounded,
      'Only you',
      'Exact date of birth, income and PIN code',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: AppColors.blush,
      padding: const EdgeInsets.symmetric(vertical: Spacing.xxl + 16),
      child: LandingContainer(
        child: Column(
          children: <Widget>[
            const _SectionHeading(
              eyebrow: 'Your privacy',
              title:
                  'Your disability is part of your story. You decide who reads it.',
              subtitle:
                  'We ask about your disability so the right people find you — '
                  'but details are revealed step by step, never all at once.',
            ),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760),
              child: Column(
                children: <Widget>[
                  for (int i = 0; i < _tiers.length; i++)
                    Padding(
                      padding: const EdgeInsets.only(bottom: Spacing.sm + 4),
                      child: Material(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(AppRadius.xl),
                        child: Padding(
                          padding: const EdgeInsets.all(Spacing.md),
                          child: Row(
                            children: <Widget>[
                              Container(
                                width: 52,
                                height: 52,
                                decoration: BoxDecoration(
                                  color: Color.lerp(
                                    AppColors.blush,
                                    AppColors.primary,
                                    i / (_tiers.length - 1),
                                  ),
                                  borderRadius: BorderRadius.circular(
                                    AppRadius.lg,
                                  ),
                                ),
                                child: Icon(
                                  _tiers[i].$1,
                                  color: i >= 2
                                      ? Colors.white
                                      : AppColors.primary,
                                ),
                              ),
                              const SizedBox(width: Spacing.md),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Text(
                                      _tiers[i].$2,
                                      style: text.titleMedium?.copyWith(
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      _tiers[i].$3,
                                      style: text.bodyMedium?.copyWith(
                                        color: colors.onSurfaceVariant,
                                        height: 1.4,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class FeaturesSection extends StatelessWidget {
  const FeaturesSection({super.key});

  static const List<(IconData, String, String)>
  _features = <(IconData, String, String)>[
    (
      Icons.accessibility_new_rounded,
      'Accessible by design',
      'Works with TalkBack and screen readers, large text and a high-contrast mode. Big, easy-to-tap buttons throughout.',
    ),
    (
      Icons.family_restroom_rounded,
      'Families welcome',
      'Parents, siblings or guardians can create and manage a profile — clearly marked, so everyone knows who they’re talking to.',
    ),
    (
      Icons.verified_user_rounded,
      'Verified, moderated profiles',
      'Our team reviews profiles and UDID documents, and every profile can be reported in one tap.',
    ),
    (
      Icons.tune_rounded,
      'Matches that fit your life',
      'Filter by disability type, language, location and more — or stay open to everyone.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Spacing.xxl + 16),
      child: LandingContainer(
        child: Column(
          children: <Widget>[
            const _SectionHeading(
              eyebrow: 'Why us',
              title: 'Designed around you',
            ),
            _ResponsiveGrid(
              maxColumns: 4,
              minItemWidth: 250,
              children: <Widget>[
                for (final (IconData icon, String title, String body)
                    in _features)
                  Card(
                    elevation: 0,
                    color: Theme.of(context).colorScheme.surfaceContainerLow,
                    child: Padding(
                      padding: const EdgeInsets.all(Spacing.lg),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Icon(icon, size: 36, color: AppColors.primary),
                          const SizedBox(height: Spacing.md),
                          Text(title, style: text.titleLarge),
                          const SizedBox(height: Spacing.sm),
                          Text(
                            body,
                            style: text.bodyMedium?.copyWith(
                              color: Theme.of(
                                context,
                              ).colorScheme.onSurfaceVariant,
                              height: 1.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Closing call-to-action band.
class ClosingCta extends StatelessWidget {
  const ClosingCta({required this.onRegister, super.key});

  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: <Color>[AppColors.heroMid, AppColors.heroEnd],
        ),
      ),
      padding: const EdgeInsets.symmetric(vertical: Spacing.xxl),
      child: LandingContainer(
        child: Column(
          children: <Widget>[
            Semantics(
              header: true,
              child: Text(
                'Your person is out there.',
                textAlign: TextAlign.center,
                style: text.headlineMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const SizedBox(height: Spacing.sm),
            Text(
              'Creating a profile takes about five minutes.',
              textAlign: TextAlign.center,
              style: text.titleMedium?.copyWith(
                color: Colors.white.withValues(alpha: 0.9),
              ),
            ),
            const SizedBox(height: Spacing.lg),
            FilledButton(
              style: FilledButton.styleFrom(
                minimumSize: const Size(240, 56),
                backgroundColor: AppColors.secondary,
                foregroundColor: AppColors.onSecondary,
              ),
              onPressed: onRegister,
              child: const Text('Register free'),
            ),
          ],
        ),
      ),
    );
  }
}

class LandingFooter extends StatelessWidget {
  const LandingFooter({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final TextStyle? muted = text.bodyMedium?.copyWith(color: Colors.white70);
    return Container(
      width: double.infinity,
      color: const Color(0xFF24121A),
      padding: const EdgeInsets.symmetric(vertical: Spacing.xl),
      child: LandingContainer(
        child: Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: Spacing.lg,
          runSpacing: Spacing.md,
          children: <Widget>[
            Text(
              '© ${DateTime.now().year} ${AppConstants.appName}',
              style: muted,
            ),
            Text('Help: ${AppConstants.supportEmail}', style: muted),
            TextButton(
              style: TextButton.styleFrom(foregroundColor: Colors.white),
              onPressed: () => context.go(RouteNames.adminLogin),
              child: const Text('Staff sign in'),
            ),
          ],
        ),
      ),
    );
  }
}
