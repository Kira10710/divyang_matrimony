import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';
import '../entities/auth_user.dart';

/// Refetches the current user from the backend (`GET /auth/me`) and
/// re-caches it locally.
class GetCurrentUserUseCase {
  const GetCurrentUserUseCase(this._repository);

  final AuthRepository _repository;

  Future<AuthUser> call() => _repository.getCurrentUser();
}

final Provider<GetCurrentUserUseCase> getCurrentUserUseCaseProvider =
    Provider<GetCurrentUserUseCase>((Ref ref) {
      return GetCurrentUserUseCase(ref.watch(authRepositoryProvider));
    });
