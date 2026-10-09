import '../models/profile_model.dart';

/// Abstract contract for the signed-in user's own profile
/// (backend/app/api/v1/profiles.py + partner_preferences.py).
/// Every method throws a [Failure] on error.
abstract class ProfileRepository {
  /// `GET /profiles/me`. Returns null when the user hasn't created a profile yet.
  Future<ProfileModel?> getMyProfile();

  /// `GET /profiles/{id}`. Fetches a profile by ID (applies visibility tiering).
  Future<ProfileModel> getProfileById(String id);

  /// `POST /profiles` — body matches `ProfileCreateRequest`.
  Future<void> createProfile(Map<String, dynamic> body);

  /// `PATCH /profiles/me` — body matches `ProfileUpdateRequest`.
  Future<void> updateProfile(Map<String, dynamic> body);

  /// `PUT /profiles/me/sensitive` — body matches `SensitiveDataUpdateRequest`.
  Future<void> updateSensitiveData(Map<String, dynamic> body);

  /// `PUT /profiles/me/preferences` — body matches `PartnerPreferenceUpdateRequest`.
  Future<void> updatePartnerPreferences(Map<String, dynamic> body);
}
