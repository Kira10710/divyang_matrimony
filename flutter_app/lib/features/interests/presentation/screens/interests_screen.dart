import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../demo/sample_profiles.dart';
import '../../../../models/profile_model.dart';
import '../../../../theme/design_tokens.dart';
import '../../../search/presentation/widgets/profile_result_card.dart';
import '../providers/interests_provider.dart';

/// Sent / Received / Mutual interests (sample data in the showcase build).
class InterestsScreen extends ConsumerWidget {
  const InterestsScreen({super.key, this.initialTab = 0});

  final int initialTab;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final InterestsState s = ref.watch(interestsProvider);
    final InterestsNotifier n = ref.read(interestsProvider.notifier);

    return DefaultTabController(
      length: 3,
      initialIndex: initialTab,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Interests'),
          bottom: TabBar(
            tabs: <Widget>[
              Tab(text: 'Received (${s.received.length})'),
              Tab(text: 'Sent (${s.sent.length})'),
              Tab(text: 'Mutual (${s.mutual.length})'),
            ],
          ),
        ),
        body: TabBarView(
          children: <Widget>[
            _List(
              ids: s.received,
              empty: 'No pending interests right now.',
              actionsFor: (ProfileModel p) => <Widget>[
                FilledButton(
                  onPressed: () => n.accept(p.id),
                  child: const Text('Accept'),
                ),
                OutlinedButton(
                  onPressed: () => n.decline(p.id),
                  child: const Text('Decline'),
                ),
              ],
            ),
            _List(
              ids: s.sent,
              empty: 'You have not sent any interests yet.',
              actionsFor: (ProfileModel p) => <Widget>[
                OutlinedButton(
                  onPressed: () => n.withdraw(p.id),
                  child: const Text('Withdraw'),
                ),
              ],
            ),
            _List(
              ids: s.mutual,
              empty: 'No mutual interests yet.',
              actionsFor: (ProfileModel p) => <Widget>[
                FilledButton.tonalIcon(
                  icon: const Icon(Icons.chat_rounded),
                  label: const Text('Continue on WhatsApp'),
                  onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'WhatsApp hand-off is disabled in the demo.',
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _List extends StatelessWidget {
  const _List({
    required this.ids,
    required this.empty,
    required this.actionsFor,
  });

  final List<String> ids;
  final String empty;
  final List<Widget> Function(ProfileModel) actionsFor;

  @override
  Widget build(BuildContext context) {
    final List<ProfileModel> profiles = ids
        .map(sampleProfileById)
        .whereType<ProfileModel>()
        .toList();
    if (profiles.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(Spacing.lg),
          child: Text(empty, textAlign: TextAlign.center),
        ),
      );
    }
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: ListView.separated(
          padding: const EdgeInsets.all(Spacing.md),
          itemCount: profiles.length,
          separatorBuilder: (_, __) => const SizedBox(height: Spacing.sm),
          itemBuilder: (_, int i) => ProfileResultCard(
            profile: profiles[i],
            actions: actionsFor(profiles[i]),
          ),
        ),
      ),
    );
  }
}
