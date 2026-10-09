import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/env/env_config.dart';
import '../../services/local_storage/secure_storage_service.dart';
import '../../services/session/session_manager.dart';
import '../network/api_client.dart';
import '../network/api_interceptors.dart';
import '../network/network_info.dart';

/// Infrastructure-level providers: storage, session, connectivity, and the
/// configured Dio/[ApiClient] instances. This is the bottom of the
/// dependency graph — `repositories/providers/repository_providers.dart`
/// builds feature repositories on top of these (Architecture §2.4).

final Provider<SecureStorageService> secureStorageServiceProvider =
    Provider<SecureStorageService>((Ref ref) {
      return const SecureStorageService();
    });

/// Single source of truth for "is there a logged-in session." Kept alive
/// for the app's lifetime — losing it would mean losing the in-memory
/// token cache the [AuthInterceptor] relies on.
final Provider<SessionManager> sessionManagerProvider =
    Provider<SessionManager>((Ref ref) {
      final SessionManager manager = SessionManager(
        ref.watch(secureStorageServiceProvider),
      );
      ref.onDispose(manager.dispose);
      return manager;
    });

final Provider<Connectivity> connectivityProvider = Provider<Connectivity>(
  (Ref ref) => Connectivity(),
);

final Provider<NetworkInfo> networkInfoProvider = Provider<NetworkInfo>((
  Ref ref,
) {
  return NetworkInfoImpl(ref.watch(connectivityProvider));
});

/// The single configured [Dio] instance every repository's remote
/// datasource is built on. Interceptor order: request ID → auth
/// (attach/refresh token) → retry (idempotent GETs) → logging (debug only).
final Provider<Dio> dioProvider = Provider<Dio>((Ref ref) {
  final SessionManager sessionManager = ref.watch(sessionManagerProvider);
  final Dio dio = Dio(
    BaseOptions(
      baseUrl: EnvConfig.instance.apiBaseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 15),
      contentType: 'application/json',
    ),
  );
  dio.interceptors.addAll(<Interceptor>[
    const RequestIdInterceptor(),
    AuthInterceptor(dio: dio, sessionManager: sessionManager),
    RetryInterceptor(dio),
    LoggingInterceptor(),
  ]);
  return dio;
});

final Provider<ApiClient> apiClientProvider = Provider<ApiClient>((Ref ref) {
  return ApiClient(ref.watch(dioProvider));
});
