import '../features/auth/domain/entities/auth_session.dart';
import '../features/auth/domain/entities/auth_user.dart';
import '../features/auth/domain/entities/session_info.dart';

/// Abstract contract for the authentication feature.
///
/// Presentation-layer code (usecases, [AuthNotifier]) depends on this
/// interface, never on [AuthRepositoryImpl] — see Architecture §2.4.
/// Every method throws a [Failure] (core/errors/failures.dart) on error;
/// callers use `AsyncValue.guard` or `on Failure catch (e)`.
abstract class AuthRepository {
  /// Step 1 of phone login/registration: `POST /auth/send-otp`.
  /// The backend does not distinguish register vs. login — the account is
  /// created on first successful [verifyOtp] call for a new phone number.
  Future<void> sendOtp({required String phone});

  /// Step 2: `POST /auth/verify-otp`. Persists the returned session locally
  /// on success.
  Future<AuthSession> verifyOtp({
    required String phone,
    required String otp,
    String? deviceInfo,
    String? fcmToken,
  });

  /// `POST /auth/login-admin` — email+password, admin accounts only
  /// (Architecture §6, §7.8). Persists the returned session locally on
  /// success.
  Future<AuthSession> adminLogin({
    required String email,
    required String password,
    String? deviceInfo,
  });

  /// `POST /auth/logout` — revokes the current device's refresh token.
  /// Local session is always cleared, even if the network call fails.
  Future<void> logout();

  /// `POST /auth/logout-all` — revokes every session for this user
  /// (Architecture §7.7). Returns the number of sessions revoked.
  Future<int> logoutAll();

  /// `GET /auth/sessions` — active device sessions for the current user.
  Future<List<SessionInfo>> getSessions();

  /// `GET /auth/me` — refetches and re-caches the current user.
  Future<AuthUser> getCurrentUser();

  /// Reads whatever session is cached locally, transparently refreshing an
  /// expired access token, for use at app startup. Returns `null` if there
  /// is no session or it could not be restored (e.g. refresh token revoked).
  Future<AuthUser?> restoreSession();

  /// Fires when the session is invalidated by the API layer itself (a
  /// refresh attempt was rejected) rather than by an explicit [logout] —
  /// [AuthNotifier] listens to this to drop back to unauthenticated.
  Stream<void> get onSessionExpired;
}
