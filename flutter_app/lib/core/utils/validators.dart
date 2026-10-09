import '../constants/app_constants.dart';

/// Form validators shared by every auth screen.
///
/// Mirrors the backend's own validation (`backend/app/schemas/auth.py`)
/// closely enough to catch obvious mistakes client-side, but the backend
/// remains the source of truth — these never replace server-side checks,
/// they just avoid a pointless round trip for "0000000000" or an empty OTP.
class Validators {
  Validators._();

  /// 10-digit Indian mobile number, optionally already prefixed with `+91`.
  /// Matches `backend/app/schemas/auth.py::_validate_phone`.
  static final RegExp _indianPhone = RegExp(r'^(\+91)?[6-9]\d{9}$');

  static final RegExp _email = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  static String? phone(String? value) {
    final String trimmed = (value ?? '').replaceAll(RegExp(r'\s+'), '');
    if (trimmed.isEmpty) return 'Enter your phone number';
    if (!_indianPhone.hasMatch(trimmed)) {
      return 'Enter a valid 10-digit mobile number';
    }
    return null;
  }

  /// Normalizes an already-[phone]-validated value to E.164 (`+91XXXXXXXXXX`)
  /// before it's sent to the backend.
  static String phoneToE164(String value) {
    final String trimmed = value.replaceAll(RegExp(r'\s+'), '');
    return trimmed.startsWith('+91') ? trimmed : '+91$trimmed';
  }

  static String? otp(String? value, {int length = AppConstants.otpLength}) {
    final String trimmed = value ?? '';
    if (trimmed.isEmpty) return 'Enter the code sent to your phone';
    if (trimmed.length != length || !RegExp(r'^\d+$').hasMatch(trimmed)) {
      return 'Enter the $length-digit code sent to your phone';
    }
    return null;
  }

  static String? email(String? value) {
    final String trimmed = (value ?? '').trim();
    if (trimmed.isEmpty) return 'Enter your email address';
    if (!_email.hasMatch(trimmed)) return 'Enter a valid email address';
    return null;
  }

  /// Matches the backend's admin password rule
  /// (`AdminLoginRequest.password`, `min_length=8`).
  static String? password(String? value, {int minLength = 8}) {
    final String v = value ?? '';
    if (v.isEmpty) return 'Enter your password';
    if (v.length < minLength)
      return 'Password must be at least $minLength characters';
    return null;
  }

  static String? required(
    String? value, {
    String message = 'This field is required',
  }) {
    if ((value ?? '').trim().isEmpty) return message;
    return null;
  }
}
