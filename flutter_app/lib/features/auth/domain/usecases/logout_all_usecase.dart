import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';

/// Revokes every session for the current user (`POST /auth/logout-all`,
/// Architecture §7.7) — used after a password change or reported account
/// compromise. Returns the number of sessions revoked.
class LogoutAllUseCase {
  const LogoutAllUseCase(this._repository);

  final AuthRepository _repository;

  Future<int> call() => _repository.logoutAll();
}

final Provider<LogoutAllUseCase> logoutAllUseCaseProvider =
    Provider<LogoutAllUseCase>((Ref ref) {
      return LogoutAllUseCase(ref.watch(authRepositoryProvider));
    });
