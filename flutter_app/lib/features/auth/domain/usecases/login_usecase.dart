import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';

/// Login screen's phone-entry step: requests an OTP for a (presumably)
/// existing account. The backend endpoint is identical to [RegisterUseCase]
/// — `POST /auth/send-otp` does not distinguish new vs. returning users,
/// see [AuthRepository.sendOtp].
class LoginUseCase {
  const LoginUseCase(this._repository);

  final AuthRepository _repository;

  Future<void> call(String phone) => _repository.sendOtp(phone: phone);
}

final Provider<LoginUseCase> loginUseCaseProvider = Provider<LoginUseCase>((
  Ref ref,
) {
  return LoginUseCase(ref.watch(authRepositoryProvider));
});
