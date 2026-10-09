import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../../../../models/profile_model.dart';
import '../../../../routing/route_names.dart';
import '../../../../shared/widgets/app_logo_mark.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../theme/design_tokens.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../profile/presentation/providers/my_profile_provider.dart';
import '../../../profile/presentation/widgets/disability_details_form.dart';

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
            onPressed: () => ref.read(authProvider.notifier).logout(),
            child: const Text('Log out'),
          ),
        ],
      ),
      body: profile.when(
        loading: () => const LoadingIndicator(),
        error: (Object e, _) => Center(
          child: ErrorView(
            message: e is Failure ? e.message : 'Could not load your profile.',
            onRetry: () => ref.invalidate(myProfileProvider),
          ),
        ),
        data: (ProfileModel? p) {
          if (p == null) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (context.mounted) context.go(RouteNames.profileWizard);
            });
            return const LoadingIndicator();
          }
          return _Dashboard(profile: p);
        },
      ),
    );
  }
}

class _Dashboard extends StatelessWidget {
  const _Dashboard({required this.profile});

  final ProfileModel profile;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;
    final bool searchable =
        profile.completenessScore >= AppConstants.profileCompletenessThreshold;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(Spacing.lg),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Semantics(
                header: true,
                child: Text(
                  'Namaste, ${profile.firstName}!',
                  style: text.headlineMedium,
                ),
              ),
              const SizedBox(height: Spacing.lg),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(Spacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'Profile ${profile.completenessScore}% complete',
                        style: text.titleLarge,
                      ),
                      const SizedBox(height: Spacing.sm),
                      Semantics(
                        label: 'Profile completeness',
                        value: '${profile.completenessScore} percent',
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: LinearProgressIndicator(
                            value: profile.completenessScore / 100,
                            minHeight: 10,
                          ),
                        ),
                      ),
                      const SizedBox(height: Spacing.sm),
                      Text(
                        searchable
                            ? 'Your profile is visible in search. Adding photos will get you more responses.'
                            : 'Profiles need to be at least ${AppConstants.profileCompletenessThreshold}% complete to appear in search.',
                        style: text.bodyMedium?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: Spacing.md),
                      Wrap(
                        spacing: Spacing.sm,
                        runSpacing: Spacing.sm,
                        children: <Widget>[
                          if (profile.disabilityType != null)
                            Chip(
                              avatar: Icon(
                                DisabilityDetailsForm.iconFor(
                                  profile.disabilityType!,
                                ),
                                size: 18,
                              ),
                              label: Text(profile.disabilityType!.displayName),
                            ),
                          if (profile.age != null)
                            Chip(label: Text('${profile.age} years')),
                          if (profile.city != null)
                            Chip(label: Text(profile.city!)),
                          Chip(
                            avatar: Icon(
                              profile.verificationStatus == 'APPROVED'
                                  ? Icons.verified_rounded
                                  : Icons.hourglass_top_rounded,
                              size: 18,
                            ),
                            label: Text(
                              profile.verificationStatus == 'APPROVED'
                                  ? 'Verified'
                                  : 'Verification pending',
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: Spacing.md),
              Card(
                elevation: 0,
                color: colors.surfaceContainerLow,
                child: Padding(
                  padding: const EdgeInsets.all(Spacing.lg),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.favorite_rounded,
                        color: colors.primary,
                        size: 32,
                      ),
                      const SizedBox(width: Spacing.md),
                      Expanded(
                        child: Text(
                          'Matches, search and interests are coming soon. '
                          "We'll let you know as soon as they're ready.",
                          style: text.bodyLarge,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
