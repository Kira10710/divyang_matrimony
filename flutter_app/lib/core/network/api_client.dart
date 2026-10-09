import 'package:dio/dio.dart';

import '../errors/exceptions.dart';

/// Dio-based HTTP client wrapper.
///
/// Configured with base URL from [EnvConfig] and the interceptor stack from
/// `api_interceptors.dart` (see `core/providers/core_providers.dart` for
/// where those are wired together). Every repository/datasource calls
/// through this — never construct a raw [Dio] instance directly.
///
/// [get]/[post]/[patch]/[delete] unwrap the backend's standard response
/// envelope (Architecture §3.8: `{success, message, data, errors}`) and
/// return just the `data` payload, throwing a typed [Exception] (see
/// `core/errors/exceptions.dart`) for every failure case instead of making
/// every datasource re-parse the envelope and re-map Dio errors.
class ApiClient {
  const ApiClient(this._dio);

  final Dio _dio;

  /// Escape hatch for calls that need raw Dio features (e.g. multipart
  /// uploads in the profile-photo feature) — everything auth-related uses
  /// the typed methods below.
  Dio get dio => _dio;

  Future<dynamic> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Map<String, String>? headers,
  }) {
    return _send(
      () => _dio.get<dynamic>(
        path,
        queryParameters: queryParameters,
        options: Options(headers: headers),
      ),
    );
  }

  Future<dynamic> post(
    String path, {
    Object? data,
    Map<String, String>? headers,
  }) {
    return _send(
      () => _dio.post<dynamic>(
        path,
        data: data,
        options: Options(headers: headers),
      ),
    );
  }

  Future<dynamic> patch(
    String path, {
    Object? data,
    Map<String, String>? headers,
  }) {
    return _send(
      () => _dio.patch<dynamic>(
        path,
        data: data,
        options: Options(headers: headers),
      ),
    );
  }

  Future<dynamic> put(
    String path, {
    Object? data,
    Map<String, String>? headers,
  }) {
    return _send(
      () => _dio.put<dynamic>(
        path,
        data: data,
        options: Options(headers: headers),
      ),
    );
  }

  Future<dynamic> delete(
    String path, {
    Object? data,
    Map<String, String>? headers,
  }) {
    return _send(
      () => _dio.delete<dynamic>(
        path,
        data: data,
        options: Options(headers: headers),
      ),
    );
  }

  Future<dynamic> _send(Future<Response<dynamic>> Function() request) async {
    try {
      final Response<dynamic> response = await request();
      return _unwrap(response);
    } on DioException catch (e) {
      throw _mapDioException(e);
    }
  }

  dynamic _unwrap(Response<dynamic> response) {
    final Object? raw = response.data;
    if (raw is! Map<String, dynamic>) return null;
    return raw['data'];
  }

  Exception _mapDioException(DioException e) {
    final Response<dynamic>? response = e.response;
    if (response == null) {
      return const NetworkException();
    }

    final Object? rawBody = response.data;
    final Map<String, dynamic> body = rawBody is Map<String, dynamic>
        ? rawBody
        : <String, dynamic>{};
    final String message =
        body['message'] as String? ?? 'Something went wrong. Please try again.';
    final List<dynamic> rawErrors =
        body['errors'] as List<dynamic>? ?? <dynamic>[];
    final List<ApiFieldError> errors = rawErrors
        .whereType<Map<String, dynamic>>()
        .map(ApiFieldError.fromJson)
        .toList();
    final String? code = errors.isNotEmpty ? errors.first.code : null;
    final int? statusCode = response.statusCode;

    switch (code) {
      case 'OTP_INVALID':
        return OtpException(message);
      case 'OTP_RATE_LIMIT':
        return OtpRateLimitException(message);
      case 'ACCOUNT_LOCKED':
        return AccountLockedException(message);
      case 'ACCOUNT_BANNED':
        return AccountBannedException(message);
      case 'TOKEN_EXPIRED':
        return TokenExpiredException(message);
      case 'INVALID_TOKEN':
        return InvalidTokenException(message);
    }

    if (statusCode == 401) return UnauthorizedException(message);
    if (statusCode == 422 || statusCode == 400) {
      return ValidationException(message, errors: errors);
    }
    return ServerException(message, statusCode: statusCode, code: code);
  }
}
