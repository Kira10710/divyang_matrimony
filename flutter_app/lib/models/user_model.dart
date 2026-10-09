import '../features/auth/domain/entities/auth_user.dart';

/// JSON-capable [AuthUser] — the concrete type returned by every auth
/// datasource call and cached by [SessionManager]. Lives at the top level
/// (not under `features/auth/`) because other features (profile, admin)
/// also need to read basic user fields, per Architecture §2.1.
class UserModel extends AuthUser {
  const UserModel({
    required super.id,
    required super.platformId,
    required super.isActive,
    required super.isBanned,
    required super.isPhoneVerified,
    required super.isEmailVerified,
    required super.createdAt,
    super.phone,
    super.email,
    super.role,
    super.lastLoginAt,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String,
      phone: json['phone'] as String?,
      email: json['email'] as String?,
      role: json['role'] as String?,
      platformId: json['platform_id'] as String,
      isActive: json['is_active'] as bool,
      isBanned: json['is_banned'] as bool,
      isPhoneVerified: json['is_phone_verified'] as bool,
      isEmailVerified: json['is_email_verified'] as bool,
      lastLoginAt: json['last_login_at'] == null
          ? null
          : DateTime.parse(json['last_login_at'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  factory UserModel.fromEntity(AuthUser user) {
    if (user is UserModel) return user;
    return UserModel(
      id: user.id,
      phone: user.phone,
      email: user.email,
      role: user.role,
      platformId: user.platformId,
      isActive: user.isActive,
      isBanned: user.isBanned,
      isPhoneVerified: user.isPhoneVerified,
      isEmailVerified: user.isEmailVerified,
      lastLoginAt: user.lastLoginAt,
      createdAt: user.createdAt,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'phone': phone,
      'email': email,
      'role': role,
      'platform_id': platformId,
      'is_active': isActive,
      'is_banned': isBanned,
      'is_phone_verified': isPhoneVerified,
      'is_email_verified': isEmailVerified,
      'last_login_at': lastLoginAt?.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
    };
  }
}
