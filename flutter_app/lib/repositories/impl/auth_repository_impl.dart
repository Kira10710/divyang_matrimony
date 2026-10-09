import '../../config/env/env_config.dart';
import '../../core/errors/exception_mapper.dart';
import '../../features/auth/data/datasources/auth_local_datasource.dart';
import '../../features/auth/data/datasources/auth_remote_datasource.dart';
import '../../features/auth/data/models/auth_response_model.dart';
import '../../features/auth/data/models/auth_tokens_model.dart';
import '../../features/auth/domain/entities/auth_session.dart';
import '../../features/auth/domain/entities/auth_user.dart';
import '../../features/auth/domain/entities/session_info.dart';
import '../../models/user_model.dart';
import '../auth_repository.dart';

class AuthRepositoryImpl implements AuthRepository {
  const AuthRepositoryImpl({
    required AuthRemoteDataSource remoteDataSource,
    required AuthLocalDataSource localDataSource,
  }) : _remote = remoteDataSource,
       _local = localDataSource;

  final AuthRemoteDataSource _remote;
  final AuthLocalDataSource _local;

  @override
  Future<void> sendOtp({required String phone}) {
    return _guard(
      () => _remote.sendOtp(
        phone: phone,
        platformId: EnvConfig.instance.platformId,
      ),
    );
  }

  @override
  Future<AuthSession> verifyOtp({
    required String phone,
    required String otp,
    String? deviceInfo,
    String? fcmToken,
  }) {
    return _guard(() async {
      final AuthResponseModel response = await _remote.verifyOtp(
        phone: phone,
        otp: otp,
        platformId: EnvConfig.instance.platformId,
        deviceInfo: deviceInfo,
        fcmToken: fcmToken,
      );
      await _local.cacheSession(user: response.user, tokens: response.tokens);
      return response.toEntity();
    });
  }

  @override
  Future<AuthSession> adminLogin({
    required String email,
    required String password,
    String? deviceInfo,
  }) {
    return _guard(() async {
      final AuthResponseModel response = await _remote.adminLogin(
        email: email,
        password: password,
        platformId: EnvConfig.instance.platformId,
        deviceInfo: deviceInfo,
      );
      await _local.cacheSession(user: response.user, tokens: response.tokens);
      return response.toEntity();
    });
  }

  @override
  Future<void> logout() {
    return _guard(() async {
      final AuthTokensModel? tokens = await _local.getCachedTokens();
      if (tokens != null) {
        try {
          await _remote.logout(refreshToken: tokens.refreshToken);
        } on Exception {
          // Best-effort: the user must never get stuck "logged in" locally
          // just because the revoke call failed offline. The refresh token
          // will simply expire naturally server-side.
        }
      }
      await _local.clearSession();
    });
  }

  @override
  Future<int> logoutAll() {
    return _guard(() async {
      final int revoked = await _remote.logoutAll();
      await _local.clearSession();
      return revoked;
    });
  }

  @override
  Future<List<SessionInfo>> getSessions() {
    return _guard(() => _remote.getSessions());
  }

  @override
  Future<AuthUser> getCurrentUser() {
    return _guard(() async {
      final UserModel user = await _remote.getCurrentUser();
      await _local.updateUser(user);
      return user;
    });
  }

  @override
  Future<AuthUser?> restoreSession() {
    return _guard(() async {
      await _local.init();
      final UserModel? cachedUser = await _local.getCachedUser();
      final AuthTokensModel? tokens = await _local.getCachedTokens();
      if (cachedUser == null || tokens == null) return null;

      if (!tokens.isAccessTokenExpired()) return cachedUser;

      try {
        final AuthTokensModel refreshed = await _remote.refreshTokens(
          refreshToken: tokens.refreshToken,
        );
        await _local.updateTokens(refreshed);
        return cachedUser;
      } on Exception {
        await _local.clearSession();
        return null;
      }
    });
  }

  @override
  Stream<void> get onSessionExpired => _local.onSessionExpired;

  Future<T> _guard<T>(Future<T> Function() body) async {
    try {
      return await body();
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }
}
