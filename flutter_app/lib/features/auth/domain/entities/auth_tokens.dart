import 'package:equatable/equatable.dart';

/// Access + refresh token pair, mirroring the backend's `TokenPair` schema.
///
/// [issuedAt] is set client-side the moment the tokens are received — the
/// backend never sends an absolute expiry timestamp, only a TTL in seconds
/// (`access_token_expires_in`), so the client has to compute it locally.
class AuthTokens extends Equatable {
  const AuthTokens({
    required this.accessToken,
    required this.refreshToken,
    required this.accessTokenExpiresIn,
    required this.issuedAt,
    this.tokenType = 'Bearer',
  });

  final String accessToken;
  final String refreshToken;
  final String tokenType;

  /// Access token TTL in seconds, as returned by the backend.
  final int accessTokenExpiresIn;
  final DateTime issuedAt;

  DateTime get accessTokenExpiresAt =>
      issuedAt.add(Duration(seconds: accessTokenExpiresIn));

  /// True once the access token is expired or within [skew] of expiring —
  /// used to proactively refresh rather than waiting for a 401.
  bool isAccessTokenExpired({Duration skew = const Duration(seconds: 30)}) =>
      DateTime.now().isAfter(accessTokenExpiresAt.subtract(skew));

  @override
  List<Object?> get props => <Object?>[
    accessToken,
    refreshToken,
    tokenType,
    accessTokenExpiresIn,
    issuedAt,
  ];
}
