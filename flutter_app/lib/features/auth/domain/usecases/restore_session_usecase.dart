import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../repositories/auth_repository.dart';
import '../../../../repositories/providers/repository_providers.dart';
import '../entities/auth_user.dart';

/// Reads whatever session is cached on-device at app startup, transparently
/// refreshing an expired access token. Returns `null` if there is no
/// session, or it could not be restored (e.g. the refresh token was
/// revoked server-side while the app was closed). Backs [AuthNotifier]'s
/// initial state.
class RestoreSessionUseCase {
  const RestoreSessionUseCase(this._repository);

  final AuthRepository _repository;

  Future<AuthUser?> call() => _repository.restoreSession();
}

final Provider<RestoreSessionUseCase> restoreSessionUseCaseProvider =
    Provider<RestoreSessionUseCase>((Ref ref) {
      return RestoreSessionUseCase(ref.watch(authRepositoryProvider));
    });
