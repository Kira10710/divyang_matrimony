import 'package:flutter/material.dart';

import '../../../../theme/design_tokens.dart';

class _Plan {
  const _Plan(
    this.name,
    this.price,
    this.period,
    this.features, {
    this.popular = false,
  });

  final String name;
  final String price;
  final String period;
  final List<String> features;
  final bool popular;
}

const List<_Plan> _plans = <_Plan>[
  _Plan('Free', '₹0', 'forever', <String>[
    'Create and verify your profile',
    'Search with basic filters',
    'Send up to 3 interests a month',
  ]),
  _Plan('Silver', '₹999', '3 months', <String>[
    'Everything in Free',
    'Send up to 30 interests a month',
    'See who viewed your profile',
    'WhatsApp hand-off on mutual interest',
  ], popular: true),
  _Plan('Gold', '₹1,999', '6 months', <String>[
    'Everything in Silver',
    'Unlimited interests',
    'Priority listing in search',
    'Dedicated support for parents and guardians',
  ]),
];

/// Plan comparison. Sample plans for the showcase build; checkout is disabled.
class SubscriptionPlansScreen extends StatelessWidget {
  const SubscriptionPlansScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Plans')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(Spacing.lg),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Text('Choose what suits you', style: text.headlineSmall),
                const SizedBox(height: Spacing.xs),
                Text(
                  'Prices are sample values for this preview.',
                  style: text.bodyMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: Spacing.lg),
                for (final _Plan p in _plans) ...<Widget>[
                  Card(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(AppRadius.card),
                      side: p.popular
                          ? BorderSide(color: colors.primary, width: 2)
                          : BorderSide.none,
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(Spacing.lg),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Row(
                            children: <Widget>[
                              Text(p.name, style: text.titleLarge),
                              const Spacer(),
                              if (p.popular)
                                Chip(
                                  label: const Text('Most popular'),
                                  backgroundColor: colors.primaryContainer,
                                ),
                            ],
                          ),
                          Text.rich(
                            TextSpan(
                              children: <InlineSpan>[
                                TextSpan(
                                  text: p.price,
                                  style: text.headlineMedium,
                                ),
                                TextSpan(
                                  text: ' / ${p.period}',
                                  style: text.bodyMedium,
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: Spacing.md),
                          for (final String f in p.features)
                            Padding(
                              padding: const EdgeInsets.only(
                                bottom: Spacing.sm,
                              ),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Icon(
                                    Icons.check_circle_rounded,
                                    size: 20,
                                    color: colors.primary,
                                  ),
                                  const SizedBox(width: Spacing.sm),
                                  Expanded(child: Text(f)),
                                ],
                              ),
                            ),
                          const SizedBox(height: Spacing.sm),
                          SizedBox(
                            width: double.infinity,
                            child: p.price == '₹0'
                                ? const OutlinedButton(
                                    onPressed: null,
                                    child: Text('Current plan'),
                                  )
                                : FilledButton(
                                    onPressed: () =>
                                        ScaffoldMessenger.of(
                                          context,
                                        ).showSnackBar(
                                          const SnackBar(
                                            content: Text(
                                              'Payments are disabled in this preview.',
                                            ),
                                          ),
                                        ),
                                    child: Text('Choose ${p.name}'),
                                  ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: Spacing.md),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
