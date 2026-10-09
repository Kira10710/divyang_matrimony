import 'package:equatable/equatable.dart';

/// One active device session, as returned by `GET /auth/sessions`
/// (backend `SessionOut` schema). Architecture §7.7 — sessions are
/// individually enumerable and revocable.
class SessionInfo extends Equatable {
  const SessionInfo({
    required this.id,
    required this.createdAt,
    required this.expiresAt,
    this.deviceInfo,
    this.ipAddress,
    this.lastUsedAt,
    this.isCurrent = false,
  });

  final String id;
  final String? deviceInfo;
  final String? ipAddress;
  final DateTime createdAt;
  final DateTime? lastUsedAt;
  final DateTime expiresAt;

  /// True if this is the session making the current request.
  final bool isCurrent;

  @override
  List<Object?> get props => <Object?>[
    id,
    deviceInfo,
    ipAddress,
    createdAt,
    lastUsedAt,
    expiresAt,
    isCurrent,
  ];
}
