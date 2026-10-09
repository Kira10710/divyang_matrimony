/// Named route path constants.
///
/// Every screen references these instead of raw path strings.
class RouteNames {
  RouteNames._();

  static const String splash = '/';
  static const String welcome = '/welcome';
  static const String login = '/login';
  static const String register = '/register';
  static const String otp = '/otp';
  static const String adminLogin = '/admin-login';
  static const String forgotPassword = '/forgot-password';
  static const String sessionExpired = '/session-expired';

  static const String home = '/home';
  static const String createProfile = '/profile/create';
  static const String editProfile = '/profile/edit';
  static const String profileWizard = '/profile/wizard';
  static String viewProfile(String id) => '/profile/$id';

  static const String partnerPreferences = '/preferences';

  static const String search = '/search';
  static const String searchResults = '/search/results';

  static const String interestsSent = '/interests/sent';
  static const String interestsReceived = '/interests/received';
  static const String interestsMutual = '/interests/mutual';

  static const String chatHandoff = '/chat';

  static const String notifications = '/notifications';

  static const String subscriptionPlans = '/subscription/plans';
  static const String paymentHistory = '/payments/history';

  static const String settings = '/settings';
  static const String privacySettings = '/settings/privacy';
  static const String accessibilitySettings = '/settings/accessibility';
  static const String deleteAccount = '/settings/delete-account';

  static const String reportUser = '/report';
}
