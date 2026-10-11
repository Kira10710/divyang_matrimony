import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../models/enums/disability_type.dart';
import '../../../../models/enums/gender.dart';
import '../../../../models/enums/marital_status.dart';
import '../../../../routing/route_names.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/search_providers.dart';

/// Filter form; "Search" opens [SearchResultsScreen] with the chosen filters.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  late SearchFilters _filters = ref.read(searchFiltersProvider);

  void _update(SearchFilters f) => setState(() => _filters = f);

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Search')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(Spacing.lg),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Text('Looking for', style: text.titleMedium),
                const SizedBox(height: Spacing.sm),
                SegmentedButton<Gender>(
                  segments: const <ButtonSegment<Gender>>[
                    ButtonSegment(value: Gender.female, label: Text('Bride')),
                    ButtonSegment(value: Gender.male, label: Text('Groom')),
                  ],
                  selected: <Gender>{_filters.gender},
                  onSelectionChanged: (s) => _update(
                    SearchFilters(
                      gender: s.first,
                      age: _filters.age,
                      disability: _filters.disability,
                      maritalStatus: _filters.maritalStatus,
                      motherTongue: _filters.motherTongue,
                    ),
                  ),
                ),
                const SizedBox(height: Spacing.lg),
                Text(
                  'Age: ${_filters.age.start.round()} to ${_filters.age.end.round()} years',
                  style: text.titleMedium,
                ),
                RangeSlider(
                  values: _filters.age,
                  min: 18,
                  max: 60,
                  divisions: 42,
                  labels: RangeLabels(
                    '${_filters.age.start.round()}',
                    '${_filters.age.end.round()}',
                  ),
                  onChanged: (v) => _update(
                    SearchFilters(
                      gender: _filters.gender,
                      age: v,
                      disability: _filters.disability,
                      maritalStatus: _filters.maritalStatus,
                      motherTongue: _filters.motherTongue,
                    ),
                  ),
                ),
                const SizedBox(height: Spacing.md),
                DropdownButtonFormField<DisabilityType?>(
                  initialValue: _filters.disability,
                  decoration: const InputDecoration(
                    labelText: "Partner's disability",
                  ),
                  items: <DropdownMenuItem<DisabilityType?>>[
                    const DropdownMenuItem(
                      value: null,
                      child: Text('Open to all'),
                    ),
                    for (final DisabilityType t in DisabilityType.values)
                      DropdownMenuItem(value: t, child: Text(t.displayName)),
                  ],
                  onChanged: (v) => _update(
                    SearchFilters(
                      gender: _filters.gender,
                      age: _filters.age,
                      disability: v,
                      maritalStatus: _filters.maritalStatus,
                      motherTongue: _filters.motherTongue,
                    ),
                  ),
                ),
                const SizedBox(height: Spacing.md),
                DropdownButtonFormField<MaritalStatus?>(
                  initialValue: _filters.maritalStatus,
                  decoration: const InputDecoration(
                    labelText: 'Marital status',
                  ),
                  items: <DropdownMenuItem<MaritalStatus?>>[
                    const DropdownMenuItem(value: null, child: Text('Any')),
                    for (final MaritalStatus m in MaritalStatus.values)
                      DropdownMenuItem(value: m, child: Text(m.displayName)),
                  ],
                  onChanged: (v) => _update(
                    SearchFilters(
                      gender: _filters.gender,
                      age: _filters.age,
                      disability: _filters.disability,
                      maritalStatus: v,
                      motherTongue: _filters.motherTongue,
                    ),
                  ),
                ),
                const SizedBox(height: Spacing.md),
                DropdownButtonFormField<String?>(
                  initialValue: _filters.motherTongue,
                  decoration: const InputDecoration(labelText: 'Mother tongue'),
                  items: <DropdownMenuItem<String?>>[
                    const DropdownMenuItem(value: null, child: Text('Any')),
                    for (final String l in sampleMotherTongues)
                      DropdownMenuItem(value: l, child: Text(l)),
                  ],
                  onChanged: (v) => _update(
                    SearchFilters(
                      gender: _filters.gender,
                      age: _filters.age,
                      disability: _filters.disability,
                      maritalStatus: _filters.maritalStatus,
                      motherTongue: v,
                    ),
                  ),
                ),
                const SizedBox(height: Spacing.xl),
                FilledButton.icon(
                  icon: const Icon(Icons.search_rounded),
                  label: const Text('Search'),
                  onPressed: () {
                    ref.read(searchFiltersProvider.notifier).state = _filters;
                    context.push(RouteNames.searchResults);
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
