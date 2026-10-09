import '../../../../core/constants/api_endpoints.dart';
import '../../../../core/network/api_client.dart';
import '../../../../models/user_model.dart';
import '../models/auth_response_model.dart';
import '../models/auth_tokens_model.dart';
import '../models/session_model.dart';

/// Talks to `backend/app/api/v1/auth.py` — one method per endpoint, no
/// business logic. [AuthRepositoryImpl] is the only caller.
abstract class AuthRemoteDataSource {
  Future<void> sendOtp({required String phone, String? platformId});

  Future<AuthResponseModel> verifyOtp({
    required String phone,
    required String otp,
    String? platformId,
    String? deviceInfo,
    String? fcmToken,
  });

  Future<AuthResponseModel> adminLogin({
    required String email,
    required String password,
    String? platformId,
    String? deviceInfo,
  });

  Future<AuthTokensModel> refreshTokens({required String refreshToken});

  Future<void> logout({required String refreshToken});

  Future<int> logoutAll();

  Future<List<SessionModel>> getSessions();

  Future<UserModel> getCurrentUser();
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  const AuthRemoteDataSourceImpl(this._apiClient);

  final ApiClient _apiClient;

  @override
  Future<void> sendOtp({required String phone, String? platformId}) async {
    await _apiClient.post(
      ApiEndpoints.sendOtp,
      data: <String, dynamic>{
        'phone': phone,
        if (platformId != null) 'platform_id': platformId,
      },
    );
  }

  @override
  Future<AuthResponseModel> verifyOtp({
    required String phone,
    required String otp,
    String? platformId,
    String? deviceInfo,
    String? fcmToken,
  }) async {
    final Object? data = await _apiClient.post(
      ApiEndpoints.verifyOtp,
      data: <String, dynamic>{
        'phone': phone,
        'otp': otp,
        if (platformId != null) 'platform_id': platformId,
        if (deviceInfo != null) 'device_info': deviceInfo,
        if (fcmToken != null) 'fcm_token': fcmToken,
      },
    );
    return AuthResponseModel.fromJson(data as Map<String, dynamic>);
  }

  @override
  Future<AuthResponseModel> adminLogin({
    required String email,
    required String password,
    String? platformId,
    String? deviceInfo,
  }) async {
    final Object? data = await _apiClient.post(
      ApiEndpoints.adminLogin,
      data: <String, dynamic>{
        'email': email,
        'password': password,
        if (platformId != null) 'platform_id': platformId,
        if (deviceInfo != null) 'device_info': deviceInfo,
      },
    );
    return AuthResponseModel.fromJson(data as Map<String, dynamic>);
  }

  @override
  Future<AuthTokensModel> refreshTokens({required String refreshToken}) async {
    final Object? data = await _apiClient.post(
      ApiEndpoints.refreshToken,
      data: <String, dynamic>{'refresh_token': refreshToken},
    );
    return AuthTokensModel.fromJson(data as Map<String, dynamic>);
  }

  @override
  Future<void> logout({required String refreshToken}) async {
    await _apiClient.post(
      ApiEndpoints.logout,
      data: <String, dynamic>{'refresh_token': refreshToken},
    );
  }

  @override
  Future<int> logoutAll() async {
    final Object? data = await _apiClient.post(ApiEndpoints.logoutAll);
    return (data as Map<String, dynamic>)['revoked_sessions'] as int;
  }

  @override
  Future<List<SessionModel>> getSessions() async {
    final Object? data = await _apiClient.get(ApiEndpoints.sessions);
    final List<dynamic> rawSessions =
        (data as Map<String, dynamic>)['sessions'] as List<dynamic>;
    return rawSessions
        .map((dynamic e) => SessionModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<UserModel> getCurrentUser() async {
    final Object? data = await _apiClient.get(ApiEndpoints.me);
    return UserModel.fromJson(data as Map<String, dynamic>);
  }
}
