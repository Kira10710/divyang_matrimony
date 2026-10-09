import '../../domain/entities/session_info.dart';

/// JSON-capable [SessionInfo] — deserializes the backend's `SessionOut` schema.
class SessionModel extends SessionInfo {
  const SessionModel({
    required super.id,
    required super.createdAt,
    required super.expiresAt,
    super.deviceInfo,
    super.ipAddress,
    super.lastUsedAt,
    super.isCurrent,
  });

  factory SessionModel.fromJson(Map<String, dynamic> json) {
    return SessionModel(
      id: json['id'] as String,
      deviceInfo: json['device_info'] as String?,
      ipAddress: json['ip_address'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      lastUsedAt: json['last_used_at'] == null
          ? null
          : DateTime.parse(json['last_used_at'] as String),
      expiresAt: DateTime.parse(json['expires_at'] as String),
      isCurrent: json['is_current'] as bool? ?? false,
    );
  }
}
