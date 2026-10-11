import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../models/profile_model.dart';
import '../../../../routing/route_names.dart';
import '../../../../theme/design_tokens.dart';
import '../../../profile/presentation/widgets/disability_details_form.dart';

/// Compact profile summary used by search results and the interests tabs.
/// Tapping opens the full profile; [actions] render under the summary.
class ProfileResultCard extends StatelessWidget {
  const ProfileResultCard({super.key, required this.profile, this.actions});

  final ProfileModel profile;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;
    final String name = '${profile.firstName} ${profile.lastName ?? ''}'.trim();
    final String details = <String?>[
      if (profile.age != null) '${profile.age} yrs',
      if (profile.heightCm != null) '${profile.heightCm} cm',
      profile.city,
    ].whereType<String>().join(' • ');

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push(RouteNames.viewProfile(profile.id)),
        child: Padding(
          padding: const EdgeInsets.all(Spacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: colors.primaryContainer,
                    child: Text(
                      profile.firstName.substring(0, 1),
                      style: text.titleLarge?.copyWith(
                        color: colors.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(width: Spacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Row(
                          children: <Widget>[
                            Flexible(
                              child: Text(
                                name,
                                style: text.titleMedium,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            if (profile.verificationStatus ==
                                'APPROVED') ...<Widget>[
                              const SizedBox(width: Spacing.xs),
                              Icon(
                                Icons.verified_rounded,
                                size: 18,
                                color: colors.primary,
                                semanticLabel: 'Verified',
                              ),
                            ],
                          ],
                        ),
                        Text(
                          details,
                          style: text.bodyMedium?.copyWith(
                            color: colors.onSurfaceVariant,
                          ),
                        ),
                        if (profile.occupation != null)
                          Text(profile.occupation!, style: text.bodyMedium),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: Spacing.sm),
              Wrap(
                spacing: Spacing.sm,
                runSpacing: Spacing.xs,
                children: <Widget>[
                  if (profile.disabilityType != null)
                    Chip(
                      avatar: Icon(
                        DisabilityDetailsForm.iconFor(profile.disabilityType!),
                        size: 16,
                      ),
                      label: Text(profile.disabilityType!.displayName),
                    ),
                  if (profile.motherTongue != null)
                    Chip(label: Text(profile.motherTongue!)),
                ],
              ),
              if (actions != null && actions!.isNotEmpty) ...<Widget>[
                const SizedBox(height: Spacing.sm),
                Wrap(
                  spacing: Spacing.sm,
                  runSpacing: Spacing.sm,
                  children: actions!,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
