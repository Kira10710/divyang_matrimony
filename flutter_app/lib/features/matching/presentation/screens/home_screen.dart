import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../../../../demo/demo_banner.dart';
import '../../../../demo/demo_mode.dart';
import '../../../../demo/sample_profiles.dart';
import '../../../../models/enums/gender.dart';
import '../../../../models/profile_model.dart';
import '../../../../routing/route_names.dart';
import '../../../../shared/widgets/app_logo_mark.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/design_tokens.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../interests/presentation/providers/interests_provider.dart';
import '../../../profile/presentation/providers/my_profile_provider.dart';
import '../../../profile/presentation/widgets/disability_details_form.dart';
import '../../../search/presentation/widgets/profile_result_card.dart';

/// Signed-in landing screen. Users without a profile yet (fresh sign-ups,
/// or anyone who left the wizard half-way) are sent to the profile wizard.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<ProfileModel?> profile = ref.watch(myProfileProvider);

    return Scaffold(
      appBar: AppBar(
        centerTitle: false,
        title: const Row(
          children: <Widget>[
            AppLogoMark(size: 32),
            SizedBox(width: Spacing.sm),
            Flexible(
              child: Text(
                AppConstants.appName,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: <Widget>[
          TextButton(
            style: TextButton.styleFrom(foregroundColor: Colors.white),
            onPressed: () => ref.read(authProvider.notifier).logout(),
            child: const Text('Log out'),
          ),
        ],
      ),
      body: Column(
        children: <Widget>[
          if (kDemoMode) const DemoBanner(),
          Expanded(
            child: profile.when(
              loading: () => const LoadingIndicator(),
              error: (Object e, _) => Center(
                child: ErrorView(
                  message: e is Failure
                      ? e.message
                      : 'Could not load your profile.',
                  onRetry: () => ref.invalidate(myProfileProvider),
                ),
              ),
              data: (ProfileModel? p) {
                if (p == null) {
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (context.mounted) {
                      context.go(RouteNames.profileWizard);
                    }
                  });
                  return const LoadingIndicator();
                }
                return _Dashboard(profile: p);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _Dashboard extends ConsumerWidget {
  const _Dashboard({required this.profile});

  final ProfileModel profile;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bool wide = MediaQuery.sizeOf(context).width >= 700;
    final double gutter = wide ? Spacing.xl : Spacing.md;

    return SingleChildScrollView(
      child: Column(
        children: <Widget>[
          _WelcomeHeader(profile: profile, gutter: gutter),
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1000),
              child: Padding(
                padding: EdgeInsets.all(gutter),
                child: kDemoMode
                    ? _DemoSections(wide: wide)
                    : const _ComingSoonCard(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Burgundy header with the greeting and profile completeness, matching the
/// landing hero.
class _WelcomeHeader extends StatelessWidget {
  const _WelcomeHeader({required this.profile, required this.gutter});

  final ProfileModel profile;
  final double gutter;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final bool searchable =
        profile.completenessScore >= AppConstants.profileCompletenessThreshold;

    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(gutter, Spacing.lg, gutter, Spacing.xl),
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
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1000),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Semantics(
                header: true,
                child: Text.rich(
                  TextSpan(
                    children: <InlineSpan>[
                      const TextSpan(text: 'Namaste, '),
                      TextSpan(
                        text: '${profile.firstName}!',
                        style: const TextStyle(color: AppColors.heroGold),
                      ),
                    ],
                  ),
                  style: text.headlineLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(height: Spacing.sm),
              Text(
                searchable
                    ? 'Your profile is ready to be found. Adding photos helps.'
                    : 'Complete at least ${AppConstants.profileCompletenessThreshold}% of your profile to appear in search.',
                style: text.titleMedium?.copyWith(
                  color: Colors.white.withValues(alpha: 0.92),
                  fontWeight: FontWeight.w400,
                ),
              ),
              const SizedBox(height: Spacing.lg),
              Semantics(
                label: 'Profile completeness',
                value: '${profile.completenessScore} percent',
                child: Row(
                  children: <Widget>[
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: LinearProgressIndicator(
                          value: profile.completenessScore / 100,
                          minHeight: 10,
                          color: AppColors.heroGold,
                          backgroundColor: Colors.white.withValues(alpha: 0.2),
                        ),
                      ),
                    ),
                    const SizedBox(width: Spacing.md),
                    Text(
                      '${profile.completenessScore}% complete',
                      style: text.titleSmall?.copyWith(color: Colors.white),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: Spacing.md),
              Wrap(
                spacing: Spacing.sm,
                runSpacing: Spacing.sm,
                children: <Widget>[
                  if (profile.disabilityType != null)
                    _HeaderChip(
                      icon: DisabilityDetailsForm.iconFor(
                        profile.disabilityType!,
                      ),
                      label: profile.disabilityType!.displayName,
                    ),
                  if (profile.age != null)
                    _HeaderChip(
                      icon: Icons.cake_outlined,
                      label: '${profile.age} years',
                    ),
                  if (profile.city != null)
                    _HeaderChip(
                      icon: Icons.place_outlined,
                      label: profile.city!,
                    ),
                  _HeaderChip(
                    icon: kDemoMode
                        ? Icons.science_outlined
                        : profile.verificationStatus == 'APPROVED'
                        ? Icons.verified_rounded
                        : Icons.hourglass_top_rounded,
                    label: kDemoMode
                        ? 'Demo profile'
                        : profile.verificationStatus == 'APPROVED'
                        ? 'Verified'
                        : 'Verification pending',
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HeaderChip extends StatelessWidget {
  const _HeaderChip({required this.icon, required this.label});

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
          const SizedBox(width: Spacing.sm),
          Text(
            label,
            style: Theme.of(
              context,
            ).textTheme.labelLarge?.copyWith(color: Colors.white),
          ),
        ],
      ),
    );
  }
}

class _ComingSoonCard extends StatelessWidget {
  const _ComingSoonCard();

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(Spacing.lg),
        child: Row(
          children: <Widget>[
            Icon(Icons.favorite_rounded, color: colors.primary, size: 32),
            const SizedBox(width: Spacing.md),
            Expanded(
              child: Text(
                'Matches, search and interests are coming soon. '
                "We'll let you know as soon as they're ready.",
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Showcase-only sections: quick actions, interests summary and sample
/// suggested profiles.
class _DemoSections extends ConsumerWidget {
  const _DemoSections({required this.wide});

  final bool wide;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;
    final InterestsState interests = ref.watch(interestsProvider);
    final List<ProfileModel> suggested = sampleProfiles
        .where((ProfileModel p) => p.gender == Gender.female)
        .take(wide ? 4 : 3)
        .toList();

    final List<(IconData, String, String)> actions =
        <(IconData, String, String)>[
          (Icons.search_rounded, 'Search', RouteNames.search),
          (Icons.favorite_rounded, 'Interests', RouteNames.interestsReceived),
          (
            Icons.workspace_premium_rounded,
            'Plans',
            RouteNames.subscriptionPlans,
          ),
          (Icons.settings_rounded, 'Settings', RouteNames.settings),
          (
            Icons.person_rounded,
            'My profile',
            RouteNames.viewProfile('demo-profile'),
          ),
          (Icons.edit_rounded, 'Edit profile', RouteNames.editProfile),
        ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Text('Quick actions', style: text.titleLarge),
        const SizedBox(height: Spacing.sm),
        GridView.count(
          crossAxisCount: wide ? 6 : 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: Spacing.sm,
          crossAxisSpacing: Spacing.sm,
          childAspectRatio: wide ? 1.1 : 0.95,
          children: <Widget>[
            for (final (IconData icon, String label, String route) in actions)
              Card(
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  onTap: () => context.push(route),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      CircleAvatar(
                        backgroundColor: colors.primaryContainer,
                        foregroundColor: colors.primary,
                        child: Icon(icon),
                      ),
                      const SizedBox(height: Spacing.sm),
                      Text(
                        label,
                        textAlign: TextAlign.center,
                        style: text.labelLarge,
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: Spacing.lg),
        Card(
          color: colors.primaryContainer.withValues(alpha: 0.5),
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(
              horizontal: Spacing.lg,
              vertical: Spacing.sm,
            ),
            leading: Icon(
              Icons.mark_email_unread_rounded,
              color: colors.primary,
            ),
            title: Text(
              '${interests.received.length} interests waiting for your reply',
              style: text.titleMedium,
            ),
            subtitle: const Text('Sample interests from fictional profiles'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.push(RouteNames.interestsReceived),
          ),
        ),
        const SizedBox(height: Spacing.lg),
        Row(
          children: <Widget>[
            Expanded(child: Text('Suggested for you', style: text.titleLarge)),
            TextButton(
              onPressed: () => context.push(RouteNames.search),
              child: const Text('Search all'),
            ),
          ],
        ),
        const SizedBox(height: Spacing.sm),
        if (wide)
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints c) => Wrap(
              spacing: Spacing.md,
              runSpacing: Spacing.md,
              children: <Widget>[
                for (final ProfileModel p in suggested)
                  SizedBox(
                    width: (c.maxWidth - Spacing.md) / 2,
                    child: ProfileResultCard(profile: p),
                  ),
              ],
            ),
          )
        else
          for (final ProfileModel p in suggested) ...<Widget>[
            ProfileResultCard(profile: p),
            const SizedBox(height: Spacing.sm),
          ],
      ],
    );
  }
}
