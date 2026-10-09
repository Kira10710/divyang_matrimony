import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';

/// Logs out the current device (`POST /auth/logout`). Local session is
/// always cleared, even if the network call fails — see
/// [AuthRepositoryImpl.logout].
class LogoutUseCase {
  const LogoutUseCase(this._repository);

  final AuthRepository _repository;

  Future<void> call() => _repository.logout();
}

final Provider<LogoutUseCase> logoutUseCaseProvider = Provider<LogoutUseCase>((
  Ref ref,
) {
  return LogoutUseCase(ref.watch(authRepositoryProvider));
});
