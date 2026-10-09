import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/domain/entities/auth_user.dart';
import '../../features/auth/presentation/providers/auth_provider.dart';
import '../route_names.dart';

/// Routes reachable without an active session. Everything else redirects
/// to [RouteNames.welcome] when unauthenticated.
const Set<String> _publicRoutes = <String>{
  RouteNames.welcome,
  RouteNames.login,
  RouteNames.register,
  RouteNames.otp,
  RouteNames.adminLogin,
  RouteNames.forgotPassword,
  RouteNames.sessionExpired,
};

/// Builds the `GoRouter.redirect` callback that enforces [authProvider]'s
/// state on every navigation:
///
/// - Session still restoring at app boot → stay on/return to splash.
/// - Unauthenticated → confined to [_publicRoutes]; anything else (splash
///   included, once restore finishes) funnels to [RouteNames.welcome].
/// - Authenticated → bounced out of splash/welcome/login/otp/admin-login
///   into [RouteNames.home].
///
/// Wired up in `routing/app_router.dart` alongside a `refreshListenable`
/// so a login/logout re-runs this without the caller needing to trigger
/// navigation manually.
GoRouterRedirect authGuard(Ref ref) {
  return (BuildContext context, GoRouterState state) {
    final AsyncValue<AuthUser?> authState = ref.read(authProvider);
    final String location = state.matchedLocation;

    if (authState.isLoading) {
      return location == RouteNames.splash ? null : RouteNames.splash;
    }

    final bool isAuthenticated = authState.valueOrNull != null;
    final bool isPublicRoute = _publicRoutes.contains(location);

    if (!isAuthenticated) {
      return isPublicRoute ? null : RouteNames.welcome;
    }

    if (location == RouteNames.splash || isPublicRoute) {
      return RouteNames.home;
    }

    return null;
  };
}
