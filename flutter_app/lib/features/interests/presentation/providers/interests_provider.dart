import 'package:flutter_riverpod/flutter_riverpod.dart';

/// In-memory interest state for the showcase build: ids of sample profiles.
class InterestsState {
  const InterestsState({
    this.sent = const <String>[],
    this.received = const <String>[],
    this.mutual = const <String>[],
  });

  final List<String> sent;
  final List<String> received;
  final List<String> mutual;

  InterestsState copyWith({
    List<String>? sent,
    List<String>? received,
    List<String>? mutual,
  }) => InterestsState(
    sent: sent ?? this.sent,
    received: received ?? this.received,
    mutual: mutual ?? this.mutual,
  );

  bool hasSentTo(String id) => sent.contains(id) || mutual.contains(id);
}

class InterestsNotifier extends Notifier<InterestsState> {
  @override
  InterestsState build() => const InterestsState(
    sent: <String>['p5', 'p7'],
    received: <String>['p1', 'p2', 'p4'],
    mutual: <String>['p6'],
  );

  void send(String id) {
    if (state.hasSentTo(id)) return;
    state = state.copyWith(sent: <String>[...state.sent, id]);
  }

  void withdraw(String id) =>
      state = state.copyWith(sent: state.sent.where((e) => e != id).toList());

  void accept(String id) => state = state.copyWith(
    received: state.received.where((e) => e != id).toList(),
    mutual: <String>[...state.mutual, id],
  );

  void decline(String id) => state = state.copyWith(
    received: state.received.where((e) => e != id).toList(),
  );
}

final NotifierProvider<InterestsNotifier, InterestsState> interestsProvider =
    NotifierProvider<InterestsNotifier, InterestsState>(InterestsNotifier.new);
