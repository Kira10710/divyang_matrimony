import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';
import '../entities/session_info.dart';

/// Lists active device sessions for the current user (`GET /auth/sessions`),
/// backing the "Logout from all devices" / session list settings screen
/// (Architecture §4.13).
class GetSessionsUseCase {
  const GetSessionsUseCase(this._repository);

  final AuthRepository _repository;

  Future<List<SessionInfo>> call() => _repository.getSessions();
}

final Provider<GetSessionsUseCase> getSessionsUseCaseProvider =
    Provider<GetSessionsUseCase>((Ref ref) {
      return GetSessionsUseCase(ref.watch(authRepositoryProvider));
    });
