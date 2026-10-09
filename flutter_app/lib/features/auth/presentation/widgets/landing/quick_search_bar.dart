import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../../core/constants/profile_options.dart';
import '../../../../../models/enums/disability_type.dart';
import '../../../../../models/enums/gender.dart';
import '../../../../../shared/widgets/app_dropdown.dart';
import '../../../../../theme/design_tokens.dart';
import '../../../../profile/presentation/providers/registration_draft_provider.dart';

/// "I'm looking for a … aged … to … " quick-start bar. Searching needs an
/// account, so "Let's begin" stores the choices (they pre-fill partner
/// preferences later) and hands the visitor to the registration card.
class QuickSearchBar extends ConsumerWidget {
  const QuickSearchBar({required this.onBegin, super.key});

  final VoidCallback onBegin;

  static final List<int> _ages = <int>[
    for (int a = ProfileOptions.minAge; a <= 70; a++) a,
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final RegistrationDraft draft = ref.watch(registrationDraftProvider);
    final RegistrationDraftNotifier notifier = ref.read(
      registrationDraftProvider.notifier,
    );
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;

    final List<Widget> fields = <Widget>[
      AppDropdown<Gender>(
        label: "I'm looking for a",
        value: draft.lookingFor,
        hintText: 'Bride or groom',
        items: const <Gender>[Gender.female, Gender.male],
        itemLabel: (Gender g) => g == Gender.female ? 'Bride' : 'Groom',
        onChanged: (Gender? g) =>
            notifier.update((RegistrationDraft d) => d.copyWith(lookingFor: g)),
      ),
      Row(
        children: <Widget>[
          Expanded(
            child: AppDropdown<int>(
              label: 'Aged',
              value: draft.ageMin,
              items: _ages,
              itemLabel: (int a) => '$a',
              onChanged: (int? a) {
                if (a == null) return;
                notifier.update(
                  (RegistrationDraft d) => d.copyWith(
                    ageMin: a,
                    ageMax: d.ageMax < a ? a : d.ageMax,
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Spacing.sm),
            child: Text('to', style: text.bodyMedium),
          ),
          Expanded(
            child: AppDropdown<int>(
              label: 'Up to',
              value: draft.ageMax,
              items: _ages.where((int a) => a >= draft.ageMin).toList(),
              itemLabel: (int a) => '$a',
              onChanged: (int? a) {
                if (a == null) return;
                notifier.update((RegistrationDraft d) => d.copyWith(ageMax: a));
              },
            ),
          ),
        ],
      ),
      AppDropdown<String>(
        label: 'Mother tongue',
        value: draft.motherTongue,
        hintText: 'Any',
        items: ProfileOptions.motherTongues,
        itemLabel: (String s) => s,
        onChanged: (String? s) => notifier.update(
          (RegistrationDraft d) => d.copyWith(motherTongue: s),
        ),
      ),
      AppDropdown<DisabilityType?>(
        label: "Partner's disability",
        value: draft.partnerDisability,
        items: <DisabilityType?>[null, ...DisabilityType.values],
        itemLabel: (DisabilityType? t) => t?.displayName ?? 'Open to all',
        onChanged: (DisabilityType? t) => notifier.update(
          (RegistrationDraft d) => d.copyWith(
            partnerDisability: t,
            clearPartnerDisability: t == null,
          ),
        ),
      ),
    ];

    final Widget beginButton = FilledButton.icon(
      onPressed: onBegin,
      icon: const Icon(Icons.favorite_rounded),
      label: const Text("Let's begin"),
    );

    return Material(
      color: colors.surface,
      elevation: 10,
      shadowColor: Colors.black.withValues(alpha: 0.3),
      borderRadius: BorderRadius.circular(AppRadius.xl),
      child: Padding(
        padding: const EdgeInsets.all(Spacing.md),
        child: LayoutBuilder(
          builder: (BuildContext context, BoxConstraints c) {
            if (c.maxWidth >= 860) {
              return Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: <Widget>[
                  Expanded(flex: 3, child: fields[0]),
                  const SizedBox(width: Spacing.sm),
                  Expanded(flex: 4, child: fields[1]),
                  const SizedBox(width: Spacing.sm),
                  Expanded(flex: 3, child: fields[2]),
                  const SizedBox(width: Spacing.sm),
                  Expanded(flex: 4, child: fields[3]),
                  const SizedBox(width: Spacing.md),
                  SizedBox(width: 170, child: beginButton),
                ],
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                for (final Widget f in fields) ...<Widget>[
                  f,
                  const SizedBox(height: Spacing.sm + 4),
                ],
                beginButton,
              ],
            );
          },
        ),
      ),
    );
  }
}
