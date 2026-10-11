import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/profile/presentation/providers/registration_draft_provider.dart';

import '../features/auth/domain/entities/auth_user.dart';
import '../features/auth/presentation/providers/auth_provider.dart';
import '../models/photo_model.dart';
import 'sample_profiles.dart';
import '../models/profile_model.dart';
import '../models/user_model.dart';
import '../repositories/photo_repository.dart';
import '../repositories/profile_repository.dart';
import '../repositories/providers/repository_providers.dart';

/// Showcase build only: `--dart-define=DEMO_MODE=true`.
///
/// Skips login/OTP and serves a sample profile from memory so the main
/// screens can be shown without a backend. Off by default; never enable for
/// a build that talks to real users or data.
const bool kDemoMode = bool.fromEnvironment('DEMO_MODE');

final UserModel _demoUser = UserModel(
  id: 'demo-user',
  phone: '+919999999999',
  platformId: 'divyang_matrimony',
  isActive: true,
  isBanned: false,
  isPhoneVerified: true,
  isEmailVerified: false,
  createdAt: DateTime(2026),
);

final _DemoProfileRepository _demoProfiles = _DemoProfileRepository();

List<Override> demoOverrides() => <Override>[
  authProvider.overrideWith(DemoAuthNotifier.new),
  profileRepositoryProvider.overrideWithValue(_demoProfiles),
  photoRepositoryProvider.overrideWithValue(_DemoPhotoRepository()),
];

/// Signs in as the sample user, using the name typed on the landing page.
/// No OTP is sent and nothing leaves the browser.
void demoSignIn(WidgetRef ref) {
  final String? name = ref.read(registrationDraftProvider).fullName?.trim();
  if (name != null && name.isNotEmpty) _demoProfiles.setName(name);
  (ref.read(authProvider.notifier) as DemoAuthNotifier).signIn();
}

class DemoAuthNotifier extends AuthNotifier {
  @override
  Future<AuthUser?> build() async => null;

  void signIn() => state = AsyncData<AuthUser?>(_demoUser);

  @override
  Future<void> logout() async => state = const AsyncData<AuthUser?>(null);

  @override
  Future<void> logoutAll() async => state = const AsyncData<AuthUser?>(null);

  @override
  Future<void> refreshCurrentUser() async {}
}

class _DemoProfileRepository implements ProfileRepository {
  final Map<String, dynamic> _profile = <String, dynamic>{
    'id': 'demo-profile',
    'first_name': 'Aarav',
    'last_name': 'Sharma',
    'gender': 'MALE',
    'date_of_birth': '1994-05-12',
    'marital_status': 'NEVER_MARRIED',
    'height_cm': 175,
    'education': 'B.Tech, Computer Science',
    'occupation': 'Software Engineer',
    'annual_income': '10-15 LPA',
    'mother_tongue': 'Hindi',
    'age': 32,
    'city': 'Pune',
    'state': 'Maharashtra',
    'pincode': '411001',
    'bio':
        'Easy-going and curious. I love cricket, cooking and long drives. '
        'Looking for someone kind and honest to share life with.',
    'disability_type': 'PHYSICAL',
    'completeness_score': 92,
    'verification_status': 'APPROVED',
  };
  final Map<String, dynamic> _sensitive = <String, dynamic>{
    'disability_percentage': 40,
    'disability_since': 'Since childhood',
    'health_conditions': 'None other',
    'mobility_aid': 'Walking stick',
  };
  final Map<String, dynamic> _preferences = <String, dynamic>{
    'age_min': 26,
    'age_max': 33,
    'preferred_gender': 'FEMALE',
    'preferred_marital_statuses': <String>['NEVER_MARRIED'],
    'preferred_disability_types': <String>['PHYSICAL', 'HEARING'],
    'preferred_mother_tongue': 'Hindi',
  };

  void setName(String fullName) {
    final List<String> parts = fullName.split(RegExp(r'\s+'));
    _profile['first_name'] = parts.first;
    _profile['last_name'] = parts.length > 1
        ? parts.sublist(1).join(' ')
        : null;
  }

  ProfileModel _build() => ProfileModel.fromOwnProfileJson(<String, dynamic>{
    'profile': _profile,
    'sensitive_data': _sensitive,
    'partner_preferences': <String, dynamic>{
      'id': 'demo-pref',
      'profile_id': 'demo-profile',
      ..._preferences,
    },
  });

  @override
  Future<ProfileModel?> getMyProfile() async => _build();

  @override
  Future<ProfileModel> getProfileById(String id) async =>
      sampleProfileById(id) ?? _build();

  @override
  Future<void> createProfile(Map<String, dynamic> body) async =>
      _profile.addAll(body);

  @override
  Future<void> updateProfile(Map<String, dynamic> body) async =>
      _profile.addAll(body);

  @override
  Future<void> updateSensitiveData(Map<String, dynamic> body) async =>
      _sensitive.addAll(body);

  @override
  Future<void> updatePartnerPreferences(Map<String, dynamic> body) async =>
      _preferences.addAll(body);
}

class _DemoPhotoRepository implements PhotoRepository {
  @override
  Future<List<PhotoModel>> getMyPhotos() async => <PhotoModel>[];

  @override
  Future<Map<String, dynamic>> createUploadSession() =>
      throw UnsupportedError('Photo upload is disabled in demo mode.');

  @override
  Future<PhotoModel> registerPhoto(Map<String, dynamic> body) =>
      throw UnsupportedError('Photo upload is disabled in demo mode.');

  @override
  Future<void> deletePhoto(String photoId) async {}

  @override
  Future<void> setPrimaryPhoto(String photoId) async {}
}
