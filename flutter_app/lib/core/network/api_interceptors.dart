import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:logger/logger.dart';
import 'package:uuid/uuid.dart';

import '../../features/auth/data/models/auth_tokens_model.dart';
import '../../services/session/session_manager.dart';
import '../constants/api_endpoints.dart';

/// Stamps every outgoing request with a unique `X-Request-ID`, echoed back
/// by the backend's `RequestIDMiddleware` — this is what makes a single
/// failed request traceable across client and server logs (Architecture §18).
class RequestIdInterceptor extends Interceptor {
  const RequestIdInterceptor();

  static const Uuid _uuid = Uuid();

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    options.headers['X-Request-ID'] = _uuid.v4();
    handler.next(options);
  }
}

/// Debug-only request/response/error logging. A no-op in release builds.
class LoggingInterceptor extends Interceptor {
  LoggingInterceptor([Logger? logger])
    : _logger = logger ?? Logger(printer: PrettyPrinter(methodCount: 0));

  final Logger _logger;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    if (kDebugMode) {
      _logger.d('→ ${options.method} ${options.uri}');
    }
    handler.next(options);
  }

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    if (kDebugMode) {
      _logger.d('← ${response.statusCode} ${response.requestOptions.uri}');
    }
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (kDebugMode) {
      _logger.w(
        '✗ ${err.requestOptions.method} ${err.requestOptions.uri} — '
        '${err.response?.statusCode ?? err.type}',
      );
    }
    handler.next(err);
  }
}

/// Retries idempotent GET requests on transient network failure —
/// exponential backoff, max 3 attempts (Architecture §2.6). Mutations
/// (POST/PATCH/DELETE) are never auto-retried: the caller must see the
/// error and decide, to avoid duplicate side effects.
class RetryInterceptor extends Interceptor {
  RetryInterceptor(
    this._dio, {
    this.maxAttempts = 3,
    this.baseDelay = const Duration(milliseconds: 500),
  });

  final Dio _dio;
  final int maxAttempts;
  final Duration baseDelay;

  static const String _attemptKey = 'retry_attempt';

  static bool _isTransient(DioException err) {
    return err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.connectionError;
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final RequestOptions options = err.requestOptions;
    final bool isGet = options.method.toUpperCase() == 'GET';

    if (!isGet || !_isTransient(err)) {
      handler.next(err);
      return;
    }

    final int attempt = (options.extra[_attemptKey] as int?) ?? 0;
    if (attempt >= maxAttempts) {
      handler.next(err);
      return;
    }

    final int delayMs = baseDelay.inMilliseconds * pow(2, attempt).toInt();
    await Future<void>.delayed(Duration(milliseconds: delayMs));

    options.extra[_attemptKey] = attempt + 1;
    try {
      final Response<dynamic> response = await _dio.fetch<dynamic>(options);
      handler.resolve(response);
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }
}

/// Attaches the current access token to every request and transparently
/// rotates it on a 401.
///
/// Deliberately does NOT depend on `AuthRepository` — that would be
/// circular (the repository's remote datasource calls through the same
/// [Dio] instance this interceptor lives on). Instead it talks to the
/// refresh endpoint directly via a bare [Dio] client with no interceptors
/// of its own, then updates [SessionManager] and lets [SessionManager]
/// notify the rest of the app (`onSessionExpired`) if the refresh fails.
class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required Dio dio,
    required SessionManager sessionManager,
    Dio? refreshDio,
  }) : _dio = dio,
       _sessionManager = sessionManager,
       _refreshDio =
           refreshDio ?? Dio(BaseOptions(baseUrl: dio.options.baseUrl));

  static const String _retriedKey = 'auth_retried';

  final Dio _dio;
  final Dio _refreshDio;
  final SessionManager _sessionManager;

  Completer<bool>? _refreshCompleter;

  static bool _isAuthPath(String path) {
    return path.contains(ApiEndpoints.sendOtp) ||
        path.contains(ApiEndpoints.verifyOtp) ||
        path.contains(ApiEndpoints.adminLogin) ||
        path.contains(ApiEndpoints.refreshToken);
  }

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final String? token = _sessionManager.currentAccessToken;
    if (token != null && !options.headers.containsKey('Authorization')) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final RequestOptions options = err.requestOptions;
    final bool isUnauthorized = err.response?.statusCode == 401;
    final bool alreadyRetried = options.extra[_retriedKey] == true;

    if (!isUnauthorized || alreadyRetried || _isAuthPath(options.path)) {
      handler.next(err);
      return;
    }

    final bool refreshed = await _refreshSession();
    if (!refreshed) {
      handler.next(err);
      return;
    }

    options.extra[_retriedKey] = true;
    final String? newToken = _sessionManager.currentAccessToken;
    if (newToken != null) {
      options.headers['Authorization'] = 'Bearer $newToken';
    }

    try {
      final Response<dynamic> response = await _dio.fetch<dynamic>(options);
      handler.resolve(response);
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  /// Coalesces concurrent refresh attempts — if five requests 401 at once,
  /// only one `/auth/refresh` call is made; the rest await its result.
  Future<bool> _refreshSession() {
    final Completer<bool>? inFlight = _refreshCompleter;
    if (inFlight != null) return inFlight.future;

    final Completer<bool> completer = Completer<bool>();
    _refreshCompleter = completer;
    unawaited(
      _performRefresh().then(completer.complete).whenComplete(() {
        _refreshCompleter = null;
      }),
    );
    return completer.future;
  }

  Future<bool> _performRefresh() async {
    final String? refreshToken = _sessionManager.currentRefreshToken;
    if (refreshToken == null) {
      await _sessionManager.forceExpire();
      return false;
    }

    try {
      final Response<dynamic> response = await _refreshDio.post<dynamic>(
        ApiEndpoints.refreshToken,
        data: <String, dynamic>{'refresh_token': refreshToken},
      );
      final Map<String, dynamic> body = response.data as Map<String, dynamic>;
      final bool success = body['success'] as bool? ?? false;
      if (!success) {
        await _sessionManager.forceExpire();
        return false;
      }
      final Map<String, dynamic> data = body['data'] as Map<String, dynamic>;
      await _sessionManager.updateTokens(AuthTokensModel.fromJson(data));
      return true;
    } catch (_) {
      // Covers both a rejected refresh (DioException) and an unexpected
      // response shape — either way the session can no longer be trusted,
      // and the in-flight completer above must always resolve.
      await _sessionManager.forceExpire();
      return false;
    }
  }
}
