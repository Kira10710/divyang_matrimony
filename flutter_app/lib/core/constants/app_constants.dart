/// Application-wide constants.
///
/// Static values and enums that do not change per-environment.
/// Environment-specific values belong in [EnvConfig], not here.
class AppConstants {
  AppConstants._();

  static const String appName = 'Divyang Matrimony';
  static const String supportEmail = 'support@divyangmatrimony.com';
  static const int maxPhotosPerProfile = 6;
  static const int maxBioLength = 500;
  static const int otpLength = 6;
  static const int otpExpiryMinutes = 5;
  static const int otpMaxAttempts = 3;
  static const int profileCompletenessThreshold =
      40; // % below which excluded from search
  static const double minTouchTargetSize = 48; // dp — Material Design minimum
}
