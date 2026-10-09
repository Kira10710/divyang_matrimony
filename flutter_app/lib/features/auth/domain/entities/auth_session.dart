import 'package:equatable/equatable.dart';

import 'auth_tokens.dart';
import 'auth_user.dart';

/// Result of a successful login/verify-otp/admin-login call — bundles the
/// user, the issued tokens, and whether this was a first-ever login.
/// Mirrors the backend's `LoginResponse` schema.
class AuthSession extends Equatable {
  const AuthSession({
    required this.user,
    required this.tokens,
    this.isNewUser = false,
  });

  final AuthUser user;
  final AuthTokens tokens;
  final bool isNewUser;

  @override
  List<Object?> get props => <Object?>[user, tokens, isNewUser];
}
