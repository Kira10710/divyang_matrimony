import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../theme/design_tokens.dart';
import '../providers/accessibility_provider.dart';

/// Text size and contrast; applied app-wide from app.dart.
class AccessibilitySettingsScreen extends ConsumerWidget {
  const AccessibilitySettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final double scale = ref.watch(textScaleProvider);
    final bool highContrast = ref.watch(highContrastProvider);
    final TextTheme text = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Accessibility')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: ListView(
            padding: const EdgeInsets.all(Spacing.md),
            children: <Widget>[
              Text('Text size', style: text.titleMedium),
              Slider(
                value: scale,
                min: 0.85,
                max: 1.6,
                divisions: 15,
                label: '${(scale * 100).round()}%',
                semanticFormatterCallback: (v) =>
                    '${(v * 100).round()} percent',
                onChanged: (v) =>
                    ref.read(textScaleProvider.notifier).state = v,
              ),
              Text(
                'The quick brown fox jumps over the lazy dog.',
                style: text.bodyLarge,
              ),
              const SizedBox(height: Spacing.md),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('High contrast'),
                subtitle: const Text(
                  'Stronger colours and larger touch targets',
                ),
                value: highContrast,
                onChanged: (v) =>
                    ref.read(highContrastProvider.notifier).state = v,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
