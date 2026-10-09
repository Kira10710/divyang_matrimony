import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';
import '../entities/auth_session.dart';

/// Step 2 of phone login/registration: verifies the OTP and, on success,
/// yields an [AuthSession] with the session already persisted locally by
/// the repository.
class VerifyOtpUseCase {
  const VerifyOtpUseCase(this._repository);

  final AuthRepository _repository;

  Future<AuthSession> call({
    required String phone,
    required String otp,
    String? deviceInfo,
    String? fcmToken,
  }) {
    return _repository.verifyOtp(
      phone: phone,
      otp: otp,
      deviceInfo: deviceInfo,
      fcmToken: fcmToken,
    );
  }
}

final Provider<VerifyOtpUseCase> verifyOtpUseCaseProvider =
    Provider<VerifyOtpUseCase>((Ref ref) {
      return VerifyOtpUseCase(ref.watch(authRepositoryProvider));
    });
