import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failures.dart';
import '../../domain/usecases/admin_login_usecase.dart';
import 'auth_provider.dart';

/// State for the Admin Login screen (`POST /auth/login-admin`).
///
/// Simpler than [LoginNotifier]'s phone/OTP flow — email+password is a
/// single-step submit, so this is just idle → submitting → success/error.
/// On success it hands the session to [AuthNotifier], same as
/// [LoginNotifier] does, so the rest of the app never needs to know which
/// login path was used.
sealed class AdminLoginState {
  const AdminLoginState();
}

class AdminLoginIdle extends AdminLoginState {
  const AdminLoginIdle();
}

class AdminLoginSubmitting extends AdminLoginState {
  const AdminLoginSubmitting();
}

class AdminLoginSuccess extends AdminLoginState {
  const AdminLoginSuccess();
}

class AdminLoginFailed extends AdminLoginState {
  const AdminLoginFailed(this.message);

  final String message;
}

class AdminLoginNotifier extends Notifier<AdminLoginState> {
  @override
  AdminLoginState build() => const AdminLoginIdle();

  Future<void> submit({required String email, required String password}) async {
    state = const AdminLoginSubmitting();
    try {
      final session = await ref
          .read(adminLoginUseCaseProvider)
          .call(email: email, password: password);
      ref.read(authProvider.notifier).setSession(session);
      state = const AdminLoginSuccess();
    } on Failure catch (e) {
      state = AdminLoginFailed(e.message);
    }
  }

  void reset() => state = const AdminLoginIdle();
}

final NotifierProvider<AdminLoginNotifier, AdminLoginState> adminLoginProvider =
    NotifierProvider<AdminLoginNotifier, AdminLoginState>(
      AdminLoginNotifier.new,
    );
