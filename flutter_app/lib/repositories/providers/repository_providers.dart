import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers/core_providers.dart';
import '../../features/auth/data/datasources/auth_local_datasource.dart';
import '../../features/auth/data/datasources/auth_remote_datasource.dart';
import '../auth_repository.dart';
import '../impl/auth_repository_impl.dart';
import '../impl/profile_repository_impl.dart';
import '../impl/photo_repository_impl.dart';
import '../profile_repository.dart';
import '../photo_repository.dart';

/// Riverpod providers exposing repository implementations.
///
/// This IS the DI mechanism — no get_it/injectable needed.
/// Features depend on the abstract repository provider, not concrete implementations.
/// See Architecture Section 2.4.
///
/// Example:
///   final authRepo = ref.watch(authRepositoryProvider);

final Provider<AuthRemoteDataSource> authRemoteDataSourceProvider =
    Provider<AuthRemoteDataSource>((Ref ref) {
      return AuthRemoteDataSourceImpl(ref.watch(apiClientProvider));
    });

final Provider<AuthLocalDataSource> authLocalDataSourceProvider =
    Provider<AuthLocalDataSource>((Ref ref) {
      return AuthLocalDataSourceImpl(ref.watch(sessionManagerProvider));
    });

final Provider<AuthRepository> authRepositoryProvider =
    Provider<AuthRepository>((Ref ref) {
      return AuthRepositoryImpl(
        remoteDataSource: ref.watch(authRemoteDataSourceProvider),
        localDataSource: ref.watch(authLocalDataSourceProvider),
      );
    });

final Provider<ProfileRepository> profileRepositoryProvider =
    Provider<ProfileRepository>((Ref ref) {
      return ProfileRepositoryImpl(ref.watch(apiClientProvider));
    });

final Provider<PhotoRepository> photoRepositoryProvider =
    Provider<PhotoRepository>((Ref ref) {
      return PhotoRepositoryImpl(ref.watch(apiClientProvider));
    });
