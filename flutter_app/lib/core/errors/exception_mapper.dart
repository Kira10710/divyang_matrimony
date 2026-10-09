import 'exceptions.dart';
import 'failures.dart';

/// Maps a data-layer [Exception] to the domain [Failure] every repository
/// throws, so each repository implementation doesn't re-derive the table.
Failure mapExceptionToFailure(Object error) {
  if (error is Failure) return error;
  if (error is NetworkException) return NetworkFailure(error.message);
  if (error is OtpException) return OtpFailure(error.message);
  if (error is OtpRateLimitException) return OtpRateLimitFailure(error.message);
  if (error is AccountLockedException)
    return AccountLockedFailure(error.message);
  if (error is AccountBannedException)
    return AccountBannedFailure(error.message);
  if (error is TokenExpiredException || error is InvalidTokenException) {
    return const AuthFailure('Your session has expired. Please log in again.');
  }
  if (error is UnauthorizedException) return AuthFailure(error.message);
  if (error is ValidationException) {
    final Map<String, String> fieldErrors = <String, String>{
      for (final ApiFieldError e in error.errors)
        if (e.field != null) e.field!: e.message,
    };
    return ValidationFailure(
      error.message,
      fieldErrors: fieldErrors.isEmpty ? null : fieldErrors,
    );
  }
  if (error is ServerException) {
    return ServerFailure(
      error.message,
      statusCode: error.statusCode,
      code: error.code,
    );
  }
  if (error is CacheException) return CacheFailure(error.message);
  return ServerFailure(error.toString());
}
