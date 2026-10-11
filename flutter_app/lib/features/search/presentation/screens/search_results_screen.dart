import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../models/profile_model.dart';
import '../../../../theme/design_tokens.dart';
import '../../../interests/presentation/providers/interests_provider.dart';
import '../providers/search_providers.dart';
import '../widgets/profile_result_card.dart';

class SearchResultsScreen extends ConsumerWidget {
  const SearchResultsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final List<ProfileModel> results = ref.watch(searchResultsProvider);
    final InterestsState interests = ref.watch(interestsProvider);

    return Scaffold(
      appBar: AppBar(title: Text('${results.length} matches')),
      body: results.isEmpty
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(Spacing.lg),
                child: Text(
                  'No profiles match these filters. Try widening them.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          : Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: ListView.separated(
                  padding: const EdgeInsets.all(Spacing.md),
                  itemCount: results.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: Spacing.sm),
                  itemBuilder: (BuildContext context, int i) {
                    final ProfileModel p = results[i];
                    final bool sent = interests.hasSentTo(p.id);
                    return ProfileResultCard(
                      profile: p,
                      actions: <Widget>[
                        FilledButton.tonalIcon(
                          icon: Icon(
                            sent
                                ? Icons.check_rounded
                                : Icons.favorite_border_rounded,
                          ),
                          label: Text(sent ? 'Interest sent' : 'Send interest'),
                          onPressed: sent
                              ? null
                              : () {
                                  ref
                                      .read(interestsProvider.notifier)
                                      .send(p.id);
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text(
                                        'Interest sent to ${p.firstName}',
                                      ),
                                    ),
                                  );
                                },
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
    );
  }
}
