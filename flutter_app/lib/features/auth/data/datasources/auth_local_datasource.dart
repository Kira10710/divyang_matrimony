import '../../../../models/user_model.dart';
import '../../../../services/session/session_manager.dart';
import '../models/auth_tokens_model.dart';

/// Persists/reads the current session. A thin, mockable wrapper around
/// [SessionManager] — kept as its own datasource (rather than having
/// [AuthRepositoryImpl] talk to [SessionManager] directly) purely so the
/// repository stays testable via the standard Clean Architecture seam.
abstract class AuthLocalDataSource {
  Future<void> init();

  Future<void> cacheSession({
    required UserModel user,
    required AuthTokensModel tokens,
  });

  Future<UserModel?> getCachedUser();

  Future<AuthTokensModel?> getCachedTokens();

  Future<void> updateTokens(AuthTokensModel tokens);

  Future<void> updateUser(UserModel user);

  Future<void> clearSession();

  Stream<void> get onSessionExpired;
}

class AuthLocalDataSourceImpl implements AuthLocalDataSource {
  const AuthLocalDataSourceImpl(this._sessionManager);

  final SessionManager _sessionManager;

  @override
  Future<void> init() => _sessionManager.init();

  @override
  Future<void> cacheSession({
    required UserModel user,
    required AuthTokensModel tokens,
  }) {
    return _sessionManager.saveSession(tokens: tokens, user: user);
  }

  @override
  Future<UserModel?> getCachedUser() async {
    await _sessionManager.init();
    return _sessionManager.currentUser;
  }

  @override
  Future<AuthTokensModel?> getCachedTokens() async {
    await _sessionManager.init();
    return _sessionManager.currentTokens;
  }

  @override
  Future<void> updateTokens(AuthTokensModel tokens) =>
      _sessionManager.updateTokens(tokens);

  @override
  Future<void> updateUser(UserModel user) => _sessionManager.updateUser(user);

  @override
  Future<void> clearSession() => _sessionManager.clear();

  @override
  Stream<void> get onSessionExpired => _sessionManager.onSessionExpired;
}
