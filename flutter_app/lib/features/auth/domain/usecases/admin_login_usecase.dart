import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';
import '../entities/auth_session.dart';

/// Admin email+password login (`POST /auth/login-admin`, Architecture §6).
/// Never used for regular end users — they authenticate via OTP only.
class AdminLoginUseCase {
  const AdminLoginUseCase(this._repository);

  final AuthRepository _repository;

  Future<AuthSession> call({
    required String email,
    required String password,
    String? deviceInfo,
  }) {
    return _repository.adminLogin(
      email: email,
      password: password,
      deviceInfo: deviceInfo,
    );
  }
}

final Provider<AdminLoginUseCase> adminLoginUseCaseProvider =
    Provider<AdminLoginUseCase>((Ref ref) {
      return AdminLoginUseCase(ref.watch(authRepositoryProvider));
    });
