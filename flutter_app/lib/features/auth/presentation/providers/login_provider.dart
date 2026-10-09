import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failures.dart';
import '../../domain/usecases/login_usecase.dart';
import '../../domain/usecases/verify_otp_usecase.dart';
import 'auth_provider.dart';

/// Login state management — the phone-entry → OTP-sent → verifying →
/// success/error flow for the login screen.
///
/// Deliberately separate from [AuthNotifier] ("global authentication
/// state"): this is ephemeral UI-flow state that resets every time the
/// screen is entered, whereas [AuthNotifier] is the durable "who is
/// logged in" state the rest of the app reacts to. On success, this
/// notifier hands the resulting session to [AuthNotifier] via
/// [AuthNotifier.setSession] rather than keeping its own copy.
sealed class LoginState {
  const LoginState();
}

class LoginIdle extends LoginState {
  const LoginIdle();
}

class LoginSendingOtp extends LoginState {
  const LoginSendingOtp();
}

class LoginOtpSent extends LoginState {
  const LoginOtpSent(this.phone);

  final String phone;
}

class LoginVerifying extends LoginState {
  const LoginVerifying(this.phone);

  final String phone;
}

class LoginSuccess extends LoginState {
  const LoginSuccess({required this.isNewUser});

  final bool isNewUser;
}

class LoginFailed extends LoginState {
  const LoginFailed({required this.message, required this.retryState});

  final String message;

  /// The state to fall back to (e.g. re-show the OTP field vs. the phone
  /// field) once the error has been acknowledged.
  final LoginState retryState;
}

class LoginNotifier extends Notifier<LoginState> {
  @override
  LoginState build() => const LoginIdle();

  String? get _pendingPhone {
    return switch (state) {
      LoginOtpSent(:final phone) => phone,
      LoginVerifying(:final phone) => phone,
      LoginFailed(retryState: LoginOtpSent(:final phone)) => phone,
      _ => null,
    };
  }

  Future<void> sendOtp(String phone) async {
    state = const LoginSendingOtp();
    try {
      await ref.read(loginUseCaseProvider).call(phone);
      state = LoginOtpSent(phone);
    } on Failure catch (e) {
      state = LoginFailed(message: e.message, retryState: const LoginIdle());
    }
  }

  /// Re-sends the OTP to the phone number already entered for this flow.
  Future<void> resendOtp() async {
    final String? phone = _pendingPhone;
    if (phone == null) return;
    await sendOtp(phone);
  }

  Future<void> verifyOtp(
    String otp, {
    String? deviceInfo,
    String? fcmToken,
  }) async {
    final String? phone = _pendingPhone;
    if (phone == null) return;

    state = LoginVerifying(phone);
    try {
      final session = await ref
          .read(verifyOtpUseCaseProvider)
          .call(
            phone: phone,
            otp: otp,
            deviceInfo: deviceInfo,
            fcmToken: fcmToken,
          );
      ref.read(authProvider.notifier).setSession(session);
      state = LoginSuccess(isNewUser: session.isNewUser);
    } on Failure catch (e) {
      state = LoginFailed(message: e.message, retryState: LoginOtpSent(phone));
    }
  }

  void reset() => state = const LoginIdle();
}

final NotifierProvider<LoginNotifier, LoginState> loginProvider =
    NotifierProvider<LoginNotifier, LoginState>(LoginNotifier.new);
