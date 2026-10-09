import '../../domain/entities/auth_tokens.dart';

/// JSON-capable [AuthTokens] — deserializes the backend's `TokenPair` schema.
///
/// [issuedAt] is not part of the wire format; it defaults to "now" at
/// deserialization time, which is the correct anchor since the client
/// receives the token pair immediately after the backend issues it.
class AuthTokensModel extends AuthTokens {
  AuthTokensModel({
    required super.accessToken,
    required super.refreshToken,
    required super.accessTokenExpiresIn,
    DateTime? issuedAt,
    super.tokenType,
  }) : super(issuedAt: issuedAt ?? DateTime.now());

  factory AuthTokensModel.fromJson(Map<String, dynamic> json) {
    return AuthTokensModel(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      tokenType: json['token_type'] as String? ?? 'Bearer',
      accessTokenExpiresIn: json['access_token_expires_in'] as int,
    );
  }

  /// Round-trips through [SecureStorageService] — the only place we need to
  /// reconstruct [issuedAt] from a stored value rather than defaulting to now.
  factory AuthTokensModel.fromStorageJson(Map<String, dynamic> json) {
    return AuthTokensModel(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      tokenType: json['token_type'] as String? ?? 'Bearer',
      accessTokenExpiresIn: json['access_token_expires_in'] as int,
      issuedAt: DateTime.parse(json['issued_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'access_token': accessToken,
      'refresh_token': refreshToken,
      'token_type': tokenType,
      'access_token_expires_in': accessTokenExpiresIn,
      'issued_at': issuedAt.toIso8601String(),
    };
  }
}
