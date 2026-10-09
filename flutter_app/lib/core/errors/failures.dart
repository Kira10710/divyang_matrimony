// Domain-level failure types thrown from repositories/usecases.
//
// Repository implementations catch data-layer [Exception]s and throw one of
// these instead — the presentation layer (Riverpod notifiers) catches
// [Failure] and never sees a raw Dio/storage exception.

/// Base type for every domain failure. Deliberately not an [Exception] —
/// it is always caught and inspected via `catch (e)`/`on Failure`, never
/// left to propagate as an uncaught error.
abstract class Failure {
  const Failure(this.message);

  final String message;
}

class ServerFailure extends Failure {
  const ServerFailure(super.message, {this.statusCode, this.code});

  final int? statusCode;
  final String? code;
}

class NetworkFailure extends Failure {
  const NetworkFailure([super.message = 'No internet connection']);
}

class CacheFailure extends Failure {
  const CacheFailure([super.message = 'Cache read/write error']);
}

/// Generic authentication failure (unauthorized, invalid/expired token).
class AuthFailure extends Failure {
  const AuthFailure(super.message);
}

class ValidationFailure extends Failure {
  const ValidationFailure(super.message, {this.fieldErrors});

  final Map<String, String>? fieldErrors;
}

/// Wrong/expired OTP code (`OTP_INVALID`).
class OtpFailure extends Failure {
  const OtpFailure([super.message = 'Invalid or expired OTP']);
}

/// Too many OTP requests for this phone number (`OTP_RATE_LIMIT`).
class OtpRateLimitFailure extends Failure {
  const OtpRateLimitFailure([
    super.message =
        'Too many OTP requests. Please wait before requesting another.',
  ]);
}

/// Account temporarily locked after repeated failed attempts (`ACCOUNT_LOCKED`,
/// Architecture §7.7).
class AccountLockedFailure extends Failure {
  const AccountLockedFailure([
    super.message =
        'Account temporarily locked due to too many failed attempts',
  ]);
}

/// Account banned by an admin (`ACCOUNT_BANNED`).
class AccountBannedFailure extends Failure {
  const AccountBannedFailure([
    super.message = 'This account has been suspended',
  ]);
}
