import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/presentation/providers/auth_provider.dart';
import '../features/auth/presentation/screens/admin_login_screen.dart';
import '../features/auth/presentation/screens/forgot_password_screen.dart';
import '../features/auth/presentation/screens/login_screen.dart';
import '../features/auth/presentation/screens/otp_screen.dart';
import '../features/auth/presentation/screens/session_expired_screen.dart';
import '../features/auth/presentation/screens/splash_screen.dart';
import '../features/auth/presentation/screens/welcome_screen.dart';
import '../features/matching/presentation/screens/home_screen.dart';
import '../features/profile/presentation/screens/profile_wizard_screen.dart';
import '../features/profile/presentation/screens/view_profile_screen.dart';
import '../features/profile/presentation/screens/edit_profile_screen.dart';
import '../features/profile/presentation/screens/manage_photos_screen.dart';
import '../features/profile/presentation/screens/edit_partner_preferences_screen.dart';
import '../features/profile/presentation/screens/edit_basic_details_screen.dart';
import '../features/profile/presentation/screens/edit_disability_details_screen.dart';
import '../demo/demo_mode.dart';
import '../features/interests/presentation/screens/interests_screen.dart';
import '../features/payments/presentation/screens/subscription_plans_screen.dart';
import '../features/search/presentation/screens/search_results_screen.dart';
import '../features/search/presentation/screens/search_screen.dart';
import '../features/settings/presentation/screens/accessibility_settings_screen.dart';
import '../features/settings/presentation/screens/delete_account_screen.dart';
import '../features/settings/presentation/screens/privacy_settings_screen.dart';
import '../features/settings/presentation/screens/settings_screen.dart';
import 'guards/auth_guard.dart';
import 'route_names.dart';

/// Notifies GoRouter to re-run [authGuard] whenever [authProvider] changes
/// (login, logout, or session-restore finishing) — without this, a
/// successful login wouldn't bounce the user off the login screen until
/// some unrelated navigation happened to trigger a redirect check.
class _AuthRouterRefresh extends ChangeNotifier {
  _AuthRouterRefresh(Ref ref) {
    ref.listen(authProvider, (_, __) => notifyListeners());
  }
}

/// Application router — GoRouter configuration.
///
/// Reads auth state from Riverpod ([authGuard]) and redirects unauthenticated
/// users to Welcome/login. Subscription-gated routes use `SubscriptionGuard`
/// once the payments/subscriptions feature lands.
///
/// Non-auth feature routes are added incrementally as screens are built.
/// [HomeScreen] forwards users without a profile to the profile wizard.
final Provider<GoRouter> routerProvider = Provider<GoRouter>((Ref ref) {
  final GoRouter router = GoRouter(
    initialLocation: RouteNames.splash,
    refreshListenable: _AuthRouterRefresh(ref),
    redirect: authGuard(ref),
    routes: <RouteBase>[
      GoRoute(
        path: RouteNames.splash,
        builder: (_, __) => const SplashScreen(),
      ),
      GoRoute(
        path: RouteNames.welcome,
        builder: (_, __) => const WelcomeScreen(),
      ),
      GoRoute(path: RouteNames.login, builder: (_, __) => const LoginScreen()),
      GoRoute(path: RouteNames.otp, builder: (_, __) => const OtpScreen()),
      GoRoute(
        path: RouteNames.adminLogin,
        builder: (_, __) => const AdminLoginScreen(),
      ),
      GoRoute(
        path: RouteNames.forgotPassword,
        builder: (_, GoRouterState state) =>
            ForgotPasswordScreen(prefilledEmail: state.extra as String?),
      ),
      GoRoute(
        path: RouteNames.sessionExpired,
        builder: (_, __) => const SessionExpiredScreen(),
      ),
      GoRoute(path: RouteNames.home, builder: (_, __) => const HomeScreen()),
      GoRoute(
        path: RouteNames.profileWizard,
        builder: (_, __) => const ProfileWizardScreen(),
      ),
      GoRoute(
        path: '/profile/edit', // RouteNames.editProfile
        builder: (_, __) => const EditProfileScreen(),
      ),
      GoRoute(
        path: '/profile/photos', // Should add to RouteNames
        builder: (_, __) => const ManagePhotosScreen(),
      ),
      GoRoute(
        path: '/profile/edit-basic-details',
        builder: (_, __) => const EditBasicDetailsScreen(),
      ),
      GoRoute(
        path: '/profile/edit-disability-details',
        builder: (_, __) => const EditDisabilityDetailsScreen(),
      ),
      GoRoute(
        path: '/profile/edit-partner-preferences',
        builder: (_, __) => const EditPartnerPreferencesScreen(),
      ),
      // Sample-data screens, registered only in the showcase build.
      if (kDemoMode) ...<RouteBase>[
        GoRoute(
          path: RouteNames.search,
          builder: (_, __) => const SearchScreen(),
        ),
        GoRoute(
          path: RouteNames.searchResults,
          builder: (_, __) => const SearchResultsScreen(),
        ),
        GoRoute(
          path: RouteNames.interestsReceived,
          builder: (_, __) => const InterestsScreen(initialTab: 0),
        ),
        GoRoute(
          path: RouteNames.interestsSent,
          builder: (_, __) => const InterestsScreen(initialTab: 1),
        ),
        GoRoute(
          path: RouteNames.interestsMutual,
          builder: (_, __) => const InterestsScreen(initialTab: 2),
        ),
        GoRoute(
          path: RouteNames.subscriptionPlans,
          builder: (_, __) => const SubscriptionPlansScreen(),
        ),
        GoRoute(
          path: RouteNames.settings,
          builder: (_, __) => const SettingsScreen(),
        ),
        GoRoute(
          path: RouteNames.privacySettings,
          builder: (_, __) => const PrivacySettingsScreen(),
        ),
        GoRoute(
          path: RouteNames.accessibilitySettings,
          builder: (_, __) => const AccessibilitySettingsScreen(),
        ),
        GoRoute(
          path: RouteNames.deleteAccount,
          builder: (_, __) => const DeleteAccountScreen(),
        ),
      ],
      GoRoute(
        path: '/profile/:id', // matches RouteNames.viewProfile
        builder: (_, GoRouterState state) =>
            ViewProfileScreen(profileId: state.pathParameters['id']!),
      ),
    ],
  );

  // A forced (non-logout) session expiry is a distinct event from plain
  // "unauthenticated" — auth_guard.dart alone can't tell them apart, so
  // this pushes the user to the dedicated screen directly. See
  // AuthNotifier.build() in auth_provider.dart for where this fires.
  ref.listen<int>(sessionExpiredEventProvider, (int? previous, int next) {
    if (previous != null && next > previous) {
      router.go(RouteNames.sessionExpired);
    }
  });

  return router;
});
