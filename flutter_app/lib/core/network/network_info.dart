import 'package:connectivity_plus/connectivity_plus.dart';

/// Network connectivity checker.
///
/// Wraps [Connectivity] and exposes it as a simple bool + stream, used by
/// `connectivity_service.dart` to show/hide offline banners and by the
/// retry interceptor to decide whether a failure is network-related.
abstract class NetworkInfo {
  Future<bool> get isConnected;

  Stream<bool> get onConnectivityChanged;
}

class NetworkInfoImpl implements NetworkInfo {
  const NetworkInfoImpl(this._connectivity);

  final Connectivity _connectivity;

  static bool _hasConnection(List<ConnectivityResult> results) =>
      results.any((ConnectivityResult r) => r != ConnectivityResult.none);

  @override
  Future<bool> get isConnected async {
    final List<ConnectivityResult> results = await _connectivity
        .checkConnectivity();
    return _hasConnection(results);
  }

  @override
  Stream<bool> get onConnectivityChanged =>
      _connectivity.onConnectivityChanged.map(_hasConnection);
}
