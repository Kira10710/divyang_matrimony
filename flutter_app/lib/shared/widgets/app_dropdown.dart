import 'package:flutter/material.dart';

/// Themed dropdown used by every pick-list in the app — same label/error
/// treatment as [AccessibleTextField].
class AppDropdown<T> extends StatelessWidget {
  const AppDropdown({
    required this.label,
    required this.items,
    required this.itemLabel,
    required this.onChanged,
    super.key,
    this.value,
    this.validator,
    this.hintText,
    this.enabled = true,
  });

  final String label;
  final T? value;
  final List<T> items;
  final String Function(T item) itemLabel;
  final ValueChanged<T?> onChanged;
  final FormFieldValidator<T>? validator;
  final String? hintText;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<T>(
      // Re-keyed on value so an externally driven change (e.g. a landing-page
      // language chip) is reflected — initialValue is only read once.
      key: ValueKey<Object?>(value),
      initialValue: value,
      isExpanded: true,
      validator: validator,
      onChanged: enabled ? onChanged : null,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
        color: Theme.of(context).colorScheme.onSurface,
      ),
      decoration: InputDecoration(labelText: label, hintText: hintText),
      items: <DropdownMenuItem<T>>[
        for (final T item in items)
          DropdownMenuItem<T>(
            value: item,
            child: Text(itemLabel(item), overflow: TextOverflow.ellipsis),
          ),
      ],
    );
  }
}
