import '../../../../models/user_model.dart';
import '../../domain/entities/auth_session.dart';
import 'auth_tokens_model.dart';

/// JSON-capable [AuthSession] — deserializes the backend's `LoginResponse`
/// schema, returned by `/auth/verify-otp` and `/auth/login-admin`.
class AuthResponseModel {
  const AuthResponseModel({
    required this.user,
    required this.tokens,
    required this.isNewUser,
  });

  factory AuthResponseModel.fromJson(Map<String, dynamic> json) {
    return AuthResponseModel(
      user: UserModel.fromJson(json['user'] as Map<String, dynamic>),
      tokens: AuthTokensModel.fromJson(json['tokens'] as Map<String, dynamic>),
      isNewUser: json['is_new_user'] as bool? ?? false,
    );
  }

  final UserModel user;
  final AuthTokensModel tokens;
  final bool isNewUser;

  AuthSession toEntity() =>
      AuthSession(user: user, tokens: tokens, isNewUser: isNewUser);
}
