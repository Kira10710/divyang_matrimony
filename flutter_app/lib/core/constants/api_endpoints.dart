/// Centralized API endpoint paths.
///
/// Every endpoint the Flutter app calls is listed here — no raw strings
/// scattered across repositories. Change a path in one place.
class ApiEndpoints {
  ApiEndpoints._();

  static const String basePrefix = '/api/v1';

  // --- Auth (mirrors backend/app/api/v1/auth.py exactly) ---
  static const String sendOtp = '$basePrefix/auth/send-otp';
  static const String verifyOtp = '$basePrefix/auth/verify-otp';
  static const String adminLogin = '$basePrefix/auth/login-admin';
  static const String refreshToken = '$basePrefix/auth/refresh';
  static const String logout = '$basePrefix/auth/logout';
  static const String logoutAll = '$basePrefix/auth/logout-all';
  static const String sessions = '$basePrefix/auth/sessions';
  static const String me = '$basePrefix/auth/me';

  // --- Profile ---
  static const String profiles = '$basePrefix/profiles';
  static const String myProfile = '$basePrefix/profiles/me';
  static String profileById(String id) => '$basePrefix/profiles/$id';
  static const String myPhotos = '$basePrefix/profiles/me/photos';
  static const String mySensitiveData = '$basePrefix/profiles/me/sensitive';

  // --- Partner Preferences ---
  static const String myPreferences = '$basePrefix/profiles/me/preferences';

  // --- Search ---
  static const String search = '$basePrefix/search';

  // --- Interests ---
  static const String interests = '$basePrefix/interests';
  static const String interestsSent = '$basePrefix/interests/sent';
  static const String interestsReceived = '$basePrefix/interests/received';
  static const String interestsMutual = '$basePrefix/interests/mutual';

  // --- Chat (v1 WhatsApp handoff) ---
  static String whatsappLink(String profileId) =>
      '$basePrefix/chat/whatsapp-link/$profileId';

  // --- Payments & Subscriptions ---
  static const String subscriptionPlans = '$basePrefix/subscriptions/plans';
  static const String mySubscription = '$basePrefix/subscriptions/me';
  static const String createPaymentOrder = '$basePrefix/payments/create-order';
  static const String verifyPayment = '$basePrefix/payments/verify';
  static const String paymentHistory = '$basePrefix/payments/history';

  // --- Notifications ---
  static const String notifications = '$basePrefix/notifications';
  static const String notificationPreferences =
      '$basePrefix/notifications/preferences';

  // --- Reports ---
  static const String reports = '$basePrefix/reports';
  static const String myReports = '$basePrefix/reports/me';

  // --- Verification ---
  static const String verifications = '$basePrefix/verifications';
  static const String myVerifications = '$basePrefix/verifications/me';

  // --- Settings ---
  static const String settings = '$basePrefix/settings';
  static const String privacySettings = '$basePrefix/settings/privacy';
  static const String accessibilitySettings =
      '$basePrefix/settings/accessibility';
  static const String deleteAccount = '$basePrefix/settings/delete-account';
  static const String exportData = '$basePrefix/settings/export-data';

  // --- Analytics ---
  static const String analyticsEvents = '$basePrefix/analytics/events';
}
