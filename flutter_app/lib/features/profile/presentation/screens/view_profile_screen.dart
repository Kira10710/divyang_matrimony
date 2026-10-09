import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../models/profile_model.dart';
import '../../../../models/photo_model.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/profile_provider.dart';
import '../widgets/disability_details_form.dart';
import '../../../../core/constants/profile_options.dart';

class ViewProfileScreen extends ConsumerWidget {
  const ViewProfileScreen({super.key, required this.profileId});

  final String profileId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<ProfileModel> profileState = ref.watch(
      profileProvider(profileId),
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: profileState.when(
        loading: () => const LoadingIndicator(),
        error: (Object e, _) => Center(
          child: ErrorView(
            message: 'Could not load profile.',
            onRetry: () => ref.invalidate(profileProvider(profileId)),
          ),
        ),
        data: (ProfileModel profile) => _ProfileDetails(profile: profile),
      ),
    );
  }
}

class _ProfileDetails extends StatelessWidget {
  const _ProfileDetails({required this.profile});

  final ProfileModel profile;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;

    final bool isVerified = profile.verificationStatus == 'APPROVED';
    final List<PhotoModel> approvedPhotos = profile.photos
        .where((p) => p.moderationStatus == 'APPROVED' && p.mediumUrl != null)
        .toList();
    approvedPhotos.sort((a, b) => a.displayOrder.compareTo(b.displayOrder));

    return SingleChildScrollView(
      padding: const EdgeInsets.all(Spacing.lg),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              // Photos header
              if (approvedPhotos.isNotEmpty)
                SizedBox(
                  height: 300,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: approvedPhotos.length,
                    separatorBuilder: (_, __) =>
                        const SizedBox(width: Spacing.md),
                    itemBuilder: (context, index) {
                      return ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: Image.network(
                          approvedPhotos[index].mediumUrl!,
                          width: 250,
                          height: 300,
                          fit: BoxFit.cover,
                        ),
                      );
                    },
                  ),
                ),
              if (approvedPhotos.isNotEmpty) const SizedBox(height: Spacing.lg),

              // Basic details
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${profile.firstName} ${profile.lastName ?? ''}'
                              .trim(),
                          style: text.headlineMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: Spacing.xs),
                        Wrap(
                          spacing: Spacing.sm,
                          runSpacing: Spacing.xs,
                          children: [
                            if (profile.age != null)
                              Text(
                                '${profile.age} yrs',
                                style: text.titleMedium,
                              ),
                            if (profile.gender != null)
                              Text(
                                '• ${profile.gender!.displayName}',
                                style: text.titleMedium,
                              ),
                            if (profile.city != null)
                              Text(
                                '• ${profile.city}',
                                style: text.titleMedium,
                              ),
                            if (profile.state != null)
                              Text(
                                ', ${profile.state}',
                                style: text.titleMedium,
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  if (isVerified)
                    Chip(
                      avatar: const Icon(Icons.verified_rounded, size: 18),
                      label: const Text('Verified'),
                      backgroundColor: colors.primaryContainer,
                    ),
                ],
              ),
              const SizedBox(height: Spacing.lg),

              if (profile.disabilityType != null) ...[
                _SectionHeader(title: 'Disability Details'),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(Spacing.md),
                    child: Row(
                      children: [
                        Icon(
                          DisabilityDetailsForm.iconFor(
                            profile.disabilityType!,
                          ),
                          size: 32,
                        ),
                        const SizedBox(width: Spacing.md),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                profile.disabilityType!.displayName,
                                style: text.titleMedium,
                              ),
                              if (profile.sensitiveData?.disabilityPercentage !=
                                  null)
                                Text(
                                  '${profile.sensitiveData!.disabilityPercentage}% severity',
                                  style: text.bodyMedium,
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: Spacing.lg),
              ],

              if (profile.sensitiveData != null) ...[
                _SectionHeader(title: 'Health & Support'),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(Spacing.md),
                    child: Column(
                      children: [
                        if (profile.sensitiveData?.disabilitySince != null)
                          _InfoRow(
                            label: 'Since',
                            value: profile.sensitiveData!.disabilitySince!,
                          ),
                        if (profile.sensitiveData?.mobilityAidRequired != null)
                          _InfoRow(
                            label: 'Mobility Aid',
                            value: profile.sensitiveData!.mobilityAidRequired!
                                ? 'Required'
                                : 'Not required',
                          ),
                        if (profile.sensitiveData?.healthConditions != null)
                          _InfoRow(
                            label: 'Health Conditions',
                            value: profile.sensitiveData!.healthConditions!,
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: Spacing.lg),
              ],

              if (profile.partnerPreferences != null) ...[
                _SectionHeader(title: 'Looking For'),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(Spacing.md),
                    child: Column(
                      children: [
                        _InfoRow(
                          label: 'Age',
                          value:
                              '${profile.partnerPreferences!.ageMin ?? ProfileOptions.minAge} to ${profile.partnerPreferences!.ageMax ?? 70} years',
                        ),
                        if (profile.partnerPreferences!.preferredGender != null)
                          _InfoRow(
                            label: 'Gender',
                            value: profile
                                .partnerPreferences!
                                .preferredGender!
                                .displayName,
                          ),
                        if (profile
                                    .partnerPreferences!
                                    .preferredMaritalStatus !=
                                null &&
                            profile
                                .partnerPreferences!
                                .preferredMaritalStatus!
                                .isNotEmpty)
                          _InfoRow(
                            label: 'Marital Status',
                            value: profile
                                .partnerPreferences!
                                .preferredMaritalStatus!
                                .map((m) => m.displayName)
                                .join(', '),
                          ),
                        if (profile
                                    .partnerPreferences!
                                    .preferredDisabilityTypes !=
                                null &&
                            profile
                                .partnerPreferences!
                                .preferredDisabilityTypes!
                                .isNotEmpty)
                          _InfoRow(
                            label: 'Disability Types',
                            value: profile
                                .partnerPreferences!
                                .preferredDisabilityTypes!
                                .map((d) => d.displayName)
                                .join(', '),
                          )
                        else
                          _InfoRow(
                            label: 'Disability Types',
                            value: 'Open to everyone',
                          ),
                      ],
                    ),
                  ),
                ),
              ],
              const SizedBox(height: Spacing.xxl),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.sm),
      child: Text(
        title,
        style: Theme.of(
          context,
        ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 140,
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(
            child: Text(value, style: Theme.of(context).textTheme.bodyLarge),
          ),
        ],
      ),
    );
  }
}
