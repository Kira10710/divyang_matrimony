import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';

/// Register screen's phone-entry step: requests an OTP for a (presumably)
/// new account. See [LoginUseCase] — same backend call, distinct
/// presentation-layer entry point.
class RegisterUseCase {
  const RegisterUseCase(this._repository);

  final AuthRepository _repository;

  Future<void> call(String phone) => _repository.sendOtp(phone: phone);
}

final Provider<RegisterUseCase> registerUseCaseProvider =
    Provider<RegisterUseCase>((Ref ref) {
      return RegisterUseCase(ref.watch(authRepositoryProvider));
    });
