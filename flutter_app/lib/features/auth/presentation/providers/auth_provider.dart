import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/providers/repository_providers.dart';
import '../../domain/entities/auth_session.dart';
import '../../domain/entities/auth_user.dart';
import '../../domain/usecases/get_current_user_usecase.dart';
import '../../domain/usecases/logout_all_usecase.dart';
import '../../domain/usecases/logout_usecase.dart';
import '../../domain/usecases/restore_session_usecase.dart';

/// Global authentication state — the single source of truth for "is
/// someone logged in right now." Watched by route guards
/// (`routing/guards/auth_guard.dart`) and any provider/widget that needs
/// to react to sign-in/sign-out.
///
/// Distinct from `login_provider.dart`'s [LoginNotifier], which tracks the
/// ephemeral phone/OTP entry flow for the login screen and delegates the
/// actual session mutation back here via [setSession] — this notifier
/// never knows about phone numbers or OTP codes, only "who is logged in."
class AuthNotifier extends AsyncNotifier<AuthUser?> {
  @override
  Future<AuthUser?> build() async {
    final Stream<void> sessionExpired = ref
        .read(authRepositoryProvider)
        .onSessionExpired;
    final sub = sessionExpired.listen((_) {
      state = const AsyncData<AuthUser?>(null);
      // Distinguishes an involuntary expiry from an explicit logout() call
      // so the router can send the user to the Session Expired screen
      // instead of quietly landing on Welcome — see app_router.dart.
      ref.read(sessionExpiredEventProvider.notifier).state++;
    });
    ref.onDispose(() => sub.cancel());

    return ref.read(restoreSessionUseCaseProvider).call();
  }

  /// Called by [LoginNotifier] once `verify-otp`/admin-login succeeds — the
  /// repository has already persisted the session, this just publishes it.
  void setSession(AuthSession session) {
    state = AsyncData<AuthUser?>(session.user);
  }

  /// Refetches the user from `GET /auth/me` — e.g. after editing a profile
  /// field that also lives on the `users` row.
  Future<void> refreshCurrentUser() async {
    state = const AsyncLoading<AuthUser?>().copyWithPrevious(state);
    state = await AsyncValue.guard(
      () => ref.read(getCurrentUserUseCaseProvider).call(),
    );
  }

  Future<void> logout() async {
    state = const AsyncLoading<AuthUser?>().copyWithPrevious(state);
    state = await AsyncValue.guard(() async {
      await ref.read(logoutUseCaseProvider).call();
      return null;
    });
  }

  /// Revokes every session for this user (Architecture §7.7) and signs out
  /// this device too.
  Future<void> logoutAll() async {
    state = const AsyncLoading<AuthUser?>().copyWithPrevious(state);
    state = await AsyncValue.guard(() async {
      await ref.read(logoutAllUseCaseProvider).call();
      return null;
    });
  }
}

final AsyncNotifierProvider<AuthNotifier, AuthUser?> authProvider =
    AsyncNotifierProvider<AuthNotifier, AuthUser?>(AuthNotifier.new);

/// True once a user is confirmed logged in. False while the initial
/// session-restore is still loading — consumers that need to distinguish
/// "loading" from "definitely logged out" should watch [authProvider]
/// directly instead.
final Provider<bool> isAuthenticatedProvider = Provider<bool>((Ref ref) {
  return ref.watch(authProvider).valueOrNull != null;
});

final Provider<AuthUser?> currentUserProvider = Provider<AuthUser?>((Ref ref) {
  return ref.watch(authProvider).valueOrNull;
});

final Provider<bool> isAdminProvider = Provider<bool>((Ref ref) {
  return ref.watch(currentUserProvider)?.isAdmin ?? false;
});

/// Bumped each time [AuthNotifier] observes an *involuntary* session
/// expiry (a rejected refresh token) rather than an explicit [AuthNotifier.logout].
/// `routing/app_router.dart` listens to this to imperatively navigate to
/// [RouteNames] `sessionExpired` — a plain state flip to "unauthenticated"
/// isn't enough to distinguish "you logged out" from "you were logged out."
final StateProvider<int> sessionExpiredEventProvider = StateProvider<int>(
  (Ref ref) => 0,
);
