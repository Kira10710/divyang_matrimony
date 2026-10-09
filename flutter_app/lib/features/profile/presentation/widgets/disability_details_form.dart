import 'package:flutter/material.dart';

import '../../../../core/constants/profile_options.dart';
import '../../../../models/enums/disability_type.dart';
import '../../../../shared/widgets/accessible_text_field.dart';
import '../../../../shared/widgets/chip_choice_field.dart';
import '../../../../theme/design_tokens.dart';

/// Everything the disability step collects. [type] and [since] are
/// mandatory; the rest is optional.
class DisabilityDetails {
  const DisabilityDetails({
    this.type,
    this.since,
    this.hasCertificate = false,
    this.percentage = 40,
    this.mobilityAids = const <String>{},
  });

  final DisabilityType? type;
  final String? since;
  final bool hasCertificate;
  final int percentage;
  final Set<String> mobilityAids;

  DisabilityDetails copyWith({
    DisabilityType? type,
    String? since,
    bool? hasCertificate,
    int? percentage,
    Set<String>? mobilityAids,
  }) {
    return DisabilityDetails(
      type: type ?? this.type,
      since: since ?? this.since,
      hasCertificate: hasCertificate ?? this.hasCertificate,
      percentage: percentage ?? this.percentage,
      mobilityAids: mobilityAids ?? this.mobilityAids,
    );
  }
}

/// The disability step of the profile wizard. Must sit inside a [Form] —
/// type and onset are validated with it.
class DisabilityDetailsForm extends StatelessWidget {
  const DisabilityDetailsForm({
    required this.value,
    required this.onChanged,
    required this.detailsController,
    required this.healthController,
    required this.isSelf,
    super.key,
  });

  final DisabilityDetails value;
  final ValueChanged<DisabilityDetails> onChanged;
  final TextEditingController detailsController;
  final TextEditingController healthController;

  /// Switches copy between "your" and "their".
  final bool isSelf;

  static IconData iconFor(DisabilityType type) => switch (type) {
    DisabilityType.physical => Icons.accessible_rounded,
    DisabilityType.visual => Icons.visibility_off_rounded,
    DisabilityType.hearing => Icons.hearing_disabled_rounded,
    DisabilityType.intellectual => Icons.psychology_rounded,
    DisabilityType.multiple => Icons.diversity_3_rounded,
  };

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;
    final String your = isSelf ? 'your' : 'their';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        FormField<DisabilityType>(
          initialValue: value.type,
          validator: (DisabilityType? t) =>
              t == null ? 'Please choose the type of disability' : null,
          builder: (FormFieldState<DisabilityType> field) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Semantics(
                  header: true,
                  child: Text('Type of disability *', style: text.titleMedium),
                ),
                const SizedBox(height: Spacing.xs),
                Text(
                  'Shown on $your profile so people who search for it can find ${isSelf ? 'you' : 'them'}.',
                  style: text.bodySmall?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: Spacing.sm),
                LayoutBuilder(
                  builder: (BuildContext context, BoxConstraints c) {
                    final bool twoUp = c.maxWidth >= 520;
                    final double w = twoUp
                        ? (c.maxWidth - Spacing.sm) / 2
                        : c.maxWidth;
                    return Wrap(
                      spacing: Spacing.sm,
                      runSpacing: Spacing.sm,
                      children: <Widget>[
                        for (final DisabilityType t in DisabilityType.values)
                          SizedBox(
                            width: w,
                            child: _TypeCard(
                              type: t,
                              selected: field.value == t,
                              onTap: () {
                                field.didChange(t);
                                onChanged(value.copyWith(type: t));
                              },
                            ),
                          ),
                      ],
                    );
                  },
                ),
                if (field.errorText != null) ...<Widget>[
                  const SizedBox(height: Spacing.xs),
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      field.errorText!,
                      style: text.bodySmall?.copyWith(color: colors.error),
                    ),
                  ),
                ],
              ],
            );
          },
        ),
        const SizedBox(height: Spacing.lg),
        ChipChoiceField<String>(
          label: 'Since when? *',
          value: value.since,
          options: ProfileOptions.disabilitySince,
          optionLabel: (String s) => s,
          validator: (String? s) => s == null ? 'Please choose one' : null,
          onSelected: (String s) => onChanged(value.copyWith(since: s)),
        ),
        const SizedBox(height: Spacing.lg),
        Card(
          margin: EdgeInsets.zero,
          elevation: 0,
          color: colors.surfaceContainerLow,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: Spacing.sm),
            child: Column(
              children: <Widget>[
                SwitchListTile(
                  value: value.hasCertificate,
                  onChanged: (bool on) =>
                      onChanged(value.copyWith(hasCertificate: on)),
                  title: Text(
                    '${isSelf ? 'I have' : 'They have'} a disability certificate (UDID)',
                  ),
                  subtitle: const Text(
                    'Optional — you can upload it later to get a “Verified” badge.',
                  ),
                ),
                if (value.hasCertificate)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      Spacing.md,
                      0,
                      Spacing.md,
                      Spacing.sm,
                    ),
                    child: Row(
                      children: <Widget>[
                        Text('Percentage', style: text.bodyLarge),
                        Expanded(
                          child: Slider(
                            value: value.percentage.toDouble(),
                            max: 100,
                            divisions: 100,
                            label: '${value.percentage}%',
                            semanticFormatterCallback: (double v) =>
                                '${v.round()} percent',
                            onChanged: (double v) => onChanged(
                              value.copyWith(percentage: v.round()),
                            ),
                          ),
                        ),
                        SizedBox(
                          width: 52,
                          child: Text(
                            '${value.percentage}%',
                            textAlign: TextAlign.end,
                            style: text.titleMedium?.copyWith(
                              color: colors.primary,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: Spacing.lg),
        ChipMultiChoiceField<String>(
          label: 'Aids or support used (optional)',
          value: value.mobilityAids,
          options: ProfileOptions.mobilityAids,
          optionLabel: (String s) => s,
          onChanged: (Set<String> aids) {
            // "None" can't coexist with an actual aid: whichever was picked last wins.
            Set<String> next = aids;
            if (aids.contains('None') && aids.length > 1) {
              next = value.mobilityAids.contains('None')
                  ? (<String>{...aids}..remove('None'))
                  : <String>{'None'};
            }
            onChanged(value.copyWith(mobilityAids: next));
          },
        ),
        const SizedBox(height: Spacing.lg),
        AccessibleTextField(
          label: 'In ${isSelf ? 'your' : 'their'} own words (optional)',
          hintText:
              'e.g. I use a wheelchair outdoors and work from home as a designer.',
          helperText:
              'Encrypted, and shown only to people you both said yes to.',
          controller: detailsController,
          maxLength: 1000,
          keyboardType: TextInputType.multiline,
          textCapitalization: TextCapitalization.sentences,
          maxLines: 4,
        ),
        const SizedBox(height: Spacing.md),
        AccessibleTextField(
          label: 'Other health conditions (optional)',
          helperText: 'Encrypted, and shown only to mutual matches.',
          controller: healthController,
          maxLength: 500,
          textCapitalization: TextCapitalization.sentences,
        ),
      ],
    );
  }
}

class _TypeCard extends StatelessWidget {
  const _TypeCard({
    required this.type,
    required this.selected,
    required this.onTap,
  });

  final DisabilityType type;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final TextTheme text = Theme.of(context).textTheme;
    return Semantics(
      button: true,
      selected: selected,
      inMutuallyExclusiveGroup: true,
      label: '${type.displayName}. ${type.description}',
      excludeSemantics: true,
      child: Material(
        color: selected ? colors.primaryContainer : colors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          side: BorderSide(
            color: selected ? colors.primary : colors.outlineVariant,
            width: selected ? 2 : 1,
          ),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(Spacing.md),
            child: Row(
              children: <Widget>[
                Icon(
                  DisabilityDetailsForm.iconFor(type),
                  size: 30,
                  color: colors.primary,
                ),
                const SizedBox(width: Spacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        type.displayName,
                        style: text.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        type.description,
                        style: text.bodySmall?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                if (selected)
                  Icon(Icons.check_circle_rounded, color: colors.primary),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
