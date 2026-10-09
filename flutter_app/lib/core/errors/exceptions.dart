// Data-layer exceptions thrown by datasources.
//
// These are caught by repository implementations and mapped to [Failure] types
// before reaching the domain/presentation layer.

/// One field-level error, mirroring the backend's `ErrorDetail`
/// (Architecture Section 3.8: `{ "field": ..., "code": ..., "message": ... }`).
class ApiFieldError {
  const ApiFieldError({required this.code, required this.message, this.field});

  factory ApiFieldError.fromJson(Map<String, dynamic> json) {
    return ApiFieldError(
      field: json['field'] as String?,
      code: json['code'] as String? ?? 'UNKNOWN',
      message: json['message'] as String? ?? 'Unknown error',
    );
  }

  final String? field;
  final String code;
  final String message;
}

/// Generic server-side failure (non-2xx response that isn't one of the
/// more specific cases below).
class ServerException implements Exception {
  const ServerException(this.message, {this.statusCode, this.code});

  final String message;
  final int? statusCode;
  final String? code;
}

/// 422 / validation errors from the standard response envelope's `errors` array.
class ValidationException implements Exception {
  const ValidationException(this.message, {this.errors = const []});

  final String message;
  final List<ApiFieldError> errors;
}

class NetworkException implements Exception {
  const NetworkException([this.message = 'No internet connection']);

  final String message;
}

class CacheException implements Exception {
  const CacheException([this.message = 'Cache error']);

  final String message;
}

/// 401 with no more specific code — missing/malformed Authorization header.
class UnauthorizedException implements Exception {
  const UnauthorizedException([this.message = 'Unauthorized']);

  final String message;
}

/// `INVALID_TOKEN` — JWT signature/shape invalid.
class InvalidTokenException implements Exception {
  const InvalidTokenException([this.message = 'Invalid or malformed token']);

  final String message;
}

/// `TOKEN_EXPIRED` — JWT expired (access or refresh).
class TokenExpiredException implements Exception {
  const TokenExpiredException([this.message = 'Token has expired']);

  final String message;
}

/// `ACCOUNT_LOCKED` — too many failed OTP/login attempts (Architecture §7.7).
class AccountLockedException implements Exception {
  const AccountLockedException([
    this.message = 'Account temporarily locked due to too many failed attempts',
  ]);

  final String message;
}

/// `ACCOUNT_BANNED` — admin-banned account.
class AccountBannedException implements Exception {
  const AccountBannedException([
    this.message = 'This account has been suspended',
  ]);

  final String message;
}

/// `OTP_INVALID` — wrong/expired OTP code.
class OtpException implements Exception {
  const OtpException([this.message = 'Invalid or expired OTP']);

  final String message;
}

/// `OTP_RATE_LIMIT` — too many OTP send requests for this phone number.
class OtpRateLimitException implements Exception {
  const OtpRateLimitException([
    this.message =
        'Too many OTP requests. Please wait before requesting another.',
  ]);

  final String message;
}
