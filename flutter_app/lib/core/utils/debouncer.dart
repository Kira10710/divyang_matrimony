import 'dart:async';

/// A debouncer that delays execution until a pause in calls.
/// Used for search-as-you-type to avoid flooding the API.
class Debouncer {

  Debouncer({this.delay = const Duration(milliseconds: 500)});
  final Duration delay;
  Timer? _timer;

  void run(void Function() action) {
    _timer?.cancel();
    _timer = Timer(delay, action);
  }

  void dispose() {
    _timer?.cancel();
  }
}
