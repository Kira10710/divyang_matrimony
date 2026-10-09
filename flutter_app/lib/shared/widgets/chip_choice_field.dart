import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

/// A labelled group of chips that participates in [Form] validation.
///
/// Chips beat dropdowns for short option lists: every choice is visible at
/// once, each is a full-size touch target, and screen readers announce the
/// selected state per chip.
class ChipChoiceField<T> extends FormField<T> {
  ChipChoiceField({
    required String label,
    required List<T> options,
    required String Function(T) optionLabel,
    required ValueChanged<T> onSelected,
    super.key,
    T? value,
    String? helperText,
    super.validator,
  }) : super(
         initialValue: value,
         builder: (FormFieldState<T> field) {
           return _ChipGroupShell(
             label: label,
             helperText: helperText,
             errorText: field.errorText,
             chips: <Widget>[
               for (final T option in options)
                 ChoiceChip(
                   label: Text(optionLabel(option)),
                   selected: (value ?? field.value) == option,
                   onSelected: (_) {
                     field.didChange(option);
                     onSelected(option);
                   },
                 ),
             ],
           );
         },
       );
}

/// Multi-select variant of [ChipChoiceField].
class ChipMultiChoiceField<T> extends FormField<Set<T>> {
  ChipMultiChoiceField({
    required String label,
    required List<T> options,
    required String Function(T) optionLabel,
    required ValueChanged<Set<T>> onChanged,
    super.key,
    Set<T> value = const <Never>{},
    String? helperText,
    super.validator,
  }) : super(
         initialValue: value,
         builder: (FormFieldState<Set<T>> field) {
           // The parent owns the selection (it may normalise it), so render from
           // [value]; the field state only feeds validation.
           final Set<T> selected = value;
           return _ChipGroupShell(
             label: label,
             helperText: helperText,
             errorText: field.errorText,
             chips: <Widget>[
               for (final T option in options)
                 FilterChip(
                   label: Text(optionLabel(option)),
                   selected: selected.contains(option),
                   onSelected: (bool on) {
                     final Set<T> next = <T>{...selected};
                     on ? next.add(option) : next.remove(option);
                     field.didChange(next);
                     onChanged(next);
                   },
                 ),
             ],
           );
         },
       );
}

class _ChipGroupShell extends StatelessWidget {
  const _ChipGroupShell({
    required this.label,
    required this.chips,
    this.helperText,
    this.errorText,
  });

  final String label;
  final String? helperText;
  final String? errorText;
  final List<Widget> chips;

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Semantics(header: true, child: Text(label, style: text.titleMedium)),
        if (helperText != null) ...<Widget>[
          const SizedBox(height: Spacing.xs),
          Text(
            helperText!,
            style: text.bodySmall?.copyWith(color: colors.onSurfaceVariant),
          ),
        ],
        const SizedBox(height: Spacing.sm),
        Wrap(spacing: Spacing.sm, runSpacing: Spacing.sm, children: chips),
        if (errorText != null) ...<Widget>[
          const SizedBox(height: Spacing.xs),
          Semantics(
            liveRegion: true,
            child: Text(
              errorText!,
              style: text.bodySmall?.copyWith(color: colors.error),
            ),
          ),
        ],
      ],
    );
  }
}
