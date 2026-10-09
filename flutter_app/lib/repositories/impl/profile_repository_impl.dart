import '../../core/constants/api_endpoints.dart';
import '../../core/errors/exception_mapper.dart';
import '../../core/errors/exceptions.dart';
import '../../core/network/api_client.dart';
import '../../models/profile_model.dart';
import '../profile_repository.dart';

class ProfileRepositoryImpl implements ProfileRepository {
  const ProfileRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<ProfileModel?> getMyProfile() async {
    try {
      final Object? data = await _api.get(ApiEndpoints.myProfile);
      if (data is! Map<String, dynamic>) return null;
      return ProfileModel.fromOwnProfileJson(data);
    } on ServerException catch (e) {
      if (e.statusCode == 404) return null;
      throw mapExceptionToFailure(e);
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }

  @override
  Future<ProfileModel> getProfileById(String id) async {
    try {
      final Object? data = await _api.get(ApiEndpoints.profileById(id));
      if (data is! Map<String, dynamic>) {
        throw const ServerException('Invalid profile data');
      }
      return ProfileModel.fromOwnProfileJson(data); // Same structure
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }

  @override
  Future<void> createProfile(Map<String, dynamic> body) =>
      _guard(() => _api.post(ApiEndpoints.profiles, data: body));

  @override
  Future<void> updateProfile(Map<String, dynamic> body) =>
      _guard(() => _api.patch(ApiEndpoints.myProfile, data: body));

  @override
  Future<void> updateSensitiveData(Map<String, dynamic> body) =>
      _guard(() => _api.put(ApiEndpoints.mySensitiveData, data: body));

  @override
  Future<void> updatePartnerPreferences(Map<String, dynamic> body) =>
      _guard(() => _api.put(ApiEndpoints.myPreferences, data: body));

  Future<void> _guard(Future<dynamic> Function() body) async {
    try {
      await body();
    } on Exception catch (e) {
      throw mapExceptionToFailure(e);
    }
  }
}
