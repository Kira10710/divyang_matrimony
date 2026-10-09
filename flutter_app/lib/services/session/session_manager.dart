import 'dart:async';
import 'dart:convert';

import '../../features/auth/data/models/auth_tokens_model.dart';
import '../../models/user_model.dart';
import '../local_storage/secure_storage_service.dart';

/// Single source of truth for "is there a logged-in session right now."
///
/// Sits below the auth feature (repository, [AuthNotifier], route guards,
/// the API interceptor) and above [SecureStorageService] — it is what
/// makes the current tokens/user available *synchronously* and *before*
/// Riverpod's provider tree is even relevant, which matters for two
/// specific consumers that cannot `ref.watch` an [AsyncNotifier]:
///
/// 1. [AuthInterceptor] — attaches the access token to every request and
///    needs to read/replace tokens without depending on the repository
///    (which itself depends on the API client the interceptor lives in —
///    that dependency would be circular).
/// 2. App boot — [init] hydrates in-memory state from secure storage once,
///    before the widget tree/provider graph is built.
///
/// [AuthNotifier] (features/auth/presentation/providers/auth_provider.dart)
/// is still the state Riverpod consumers watch — it just delegates the
/// actual persistence to this class via [AuthRepository].
class SessionManager {
  SessionManager(this._storage);

  static const String _accessTokenKey = 'session_access_token';
  static const String _refreshTokenKey = 'session_refresh_token';
  static const String _tokenTypeKey = 'session_token_type';
  static const String _accessExpiresInKey = 'session_access_expires_in';
  static const String _issuedAtKey = 'session_issued_at';
  static const String _userKey = 'session_user';

  final SecureStorageService _storage;

  final StreamController<void> _sessionExpiredController =
      StreamController<void>.broadcast();

  AuthTokensModel? _tokens;
  UserModel? _user;
  bool _initialized = false;

  /// Emits whenever the session is invalidated by something other than an
  /// explicit, user-initiated logout — i.e. the refresh token was rejected
  /// by the backend. [AuthNotifier] listens to this to drop back to the
  /// unauthenticated state and let the router redirect to login.
  Stream<void> get onSessionExpired => _sessionExpiredController.stream;

  AuthTokensModel? get currentTokens => _tokens;
  UserModel? get currentUser => _user;
  String? get currentAccessToken => _tokens?.accessToken;
  String? get currentRefreshToken => _tokens?.refreshToken;
  bool get hasSession => _tokens != null;

  /// Hydrates in-memory state from secure storage. Safe to call multiple
  /// times — only does the storage reads once.
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    final String? accessToken = await _storage.read(_accessTokenKey);
    final String? refreshToken = await _storage.read(_refreshTokenKey);
    if (accessToken == null || refreshToken == null) return;

    final String tokenType = await _storage.read(_tokenTypeKey) ?? 'Bearer';
    final String? expiresInRaw = await _storage.read(_accessExpiresInKey);
    final String? issuedAtRaw = await _storage.read(_issuedAtKey);

    _tokens = AuthTokensModel(
      accessToken: accessToken,
      refreshToken: refreshToken,
      tokenType: tokenType,
      accessTokenExpiresIn: int.tryParse(expiresInRaw ?? '') ?? 0,
      issuedAt: issuedAtRaw == null
          ? DateTime.now()
          : DateTime.parse(issuedAtRaw),
    );

    final String? userRaw = await _storage.read(_userKey);
    if (userRaw != null) {
      _user = UserModel.fromJson(jsonDecode(userRaw) as Map<String, dynamic>);
    }
  }

  /// Persists a fresh login/registration result (tokens + user).
  Future<void> saveSession({
    required AuthTokensModel tokens,
    required UserModel user,
  }) async {
    _tokens = tokens;
    _user = user;
    await Future.wait(<Future<void>>[
      _storage.write(_accessTokenKey, tokens.accessToken),
      _storage.write(_refreshTokenKey, tokens.refreshToken),
      _storage.write(_tokenTypeKey, tokens.tokenType),
      _storage.write(
        _accessExpiresInKey,
        tokens.accessTokenExpiresIn.toString(),
      ),
      _storage.write(_issuedAtKey, tokens.issuedAt.toIso8601String()),
      _storage.write(_userKey, jsonEncode(user.toJson())),
    ]);
  }

  /// Refreshes just the cached user (e.g. after `GET /auth/me`), leaving
  /// the current tokens untouched.
  Future<void> updateUser(UserModel user) async {
    _user = user;
    await _storage.write(_userKey, jsonEncode(user.toJson()));
  }

  /// Persists a rotated token pair after a successful `/auth/refresh` call,
  /// keeping the already-cached user untouched.
  Future<void> updateTokens(AuthTokensModel tokens) async {
    _tokens = tokens;
    await Future.wait<void>(<Future<void>>[
      _storage.write(_accessTokenKey, tokens.accessToken),
      _storage.write(_refreshTokenKey, tokens.refreshToken),
      _storage.write(_tokenTypeKey, tokens.tokenType),
      _storage.write(
        _accessExpiresInKey,
        tokens.accessTokenExpiresIn.toString(),
      ),
      _storage.write(_issuedAtKey, tokens.issuedAt.toIso8601String()),
    ]);
  }

  /// Explicit, user-initiated logout — clears state without emitting
  /// [onSessionExpired] (the caller already knows the session is gone).
  Future<void> clear() async {
    _tokens = null;
    _user = null;
    await Future.wait<void>(<Future<void>>[
      _storage.delete(_accessTokenKey),
      _storage.delete(_refreshTokenKey),
      _storage.delete(_tokenTypeKey),
      _storage.delete(_accessExpiresInKey),
      _storage.delete(_issuedAtKey),
      _storage.delete(_userKey),
    ]);
  }

  /// Called by [AuthInterceptor] when a refresh attempt is rejected by the
  /// backend (revoked/expired refresh token) — an involuntary logout.
  Future<void> forceExpire() async {
    await clear();
    _sessionExpiredController.add(null);
  }

  void dispose() => unawaited(_sessionExpiredController.close());
}
