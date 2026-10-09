import 'package:equatable/equatable.dart';

/// The authenticated account — end user or admin.
///
/// Mirrors the backend's `UserOut` schema (backend/app/schemas/auth.py) minus
/// anything server-internal (no password hash, no soft-delete timestamp).
/// [UserModel] (lib/models/user_model.dart) is the concrete, JSON-capable
/// implementation used everywhere this entity is actually constructed.
class AuthUser extends Equatable {
  const AuthUser({
    required this.id,
    required this.platformId,
    required this.isActive,
    required this.isBanned,
    required this.isPhoneVerified,
    required this.isEmailVerified,
    required this.createdAt,
    this.phone,
    this.email,
    this.role,
    this.lastLoginAt,
  });

  final String id;
  final String? phone;
  final String? email;

  /// One of `SUPER_ADMIN` / `ADMIN` / `SUPPORT`, or null for a regular end user.
  final String? role;
  final String platformId;
  final bool isActive;
  final bool isBanned;
  final bool isPhoneVerified;
  final bool isEmailVerified;
  final DateTime? lastLoginAt;
  final DateTime createdAt;

  bool get isAdmin => role != null;

  @override
  List<Object?> get props => <Object?>[
    id,
    phone,
    email,
    role,
    platformId,
    isActive,
    isBanned,
    isPhoneVerified,
    isEmailVerified,
    lastLoginAt,
    createdAt,
  ];
}
