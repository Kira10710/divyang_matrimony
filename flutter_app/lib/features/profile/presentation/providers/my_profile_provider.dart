import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failures.dart';
import '../../../../models/profile_model.dart';
import '../../../../repositories/providers/repository_providers.dart';
import '../../../auth/presentation/providers/auth_provider.dart';

/// The signed-in user's own profile; `null` data means "no profile yet" and
/// sends the user into the profile wizard. Re-fetches whenever the signed-in
/// account changes.
final FutureProvider<ProfileModel?> myProfileProvider =
    FutureProvider<ProfileModel?>((Ref ref) async {
      final String? userId = ref.watch(
        currentUserProvider.select((user) => user?.id),
      );
      if (userId == null) return null;
      return ref.read(profileRepositoryProvider).getMyProfile();
    });

/// Everything the wizard collected, already shaped as the three backend
/// request bodies.
class ProfileSubmission {
  const ProfileSubmission({
    required this.profile,
    required this.sensitive,
    required this.preferences,
  });

  final Map<String, dynamic> profile;
  final Map<String, dynamic> sensitive;
  final Map<String, dynamic> preferences;
}

/// Submits the wizard: create profile → sensitive data → partner preferences.
///
/// The three calls aren't atomic server-side, so a retry after a partial
/// failure must not re-POST the profile (the backend answers 409) — it
/// remembers the profile was created and resumes from the next call.
class ProfileSubmitNotifier extends AsyncNotifier<void> {
  bool _profileCreated = false;

  @override
  Future<void> build() async {}

  Future<bool> submit(ProfileSubmission submission) async {
    state = const AsyncLoading<void>();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(profileRepositoryProvider);
      if (!_profileCreated) {
        try {
          await repo.createProfile(submission.profile);
        } on ServerFailure catch (e) {
          if (e.statusCode != 409) rethrow;
        }
        _profileCreated = true;
      }
      await repo.updateSensitiveData(submission.sensitive);
      await repo.updatePartnerPreferences(submission.preferences);
    });
    if (state.hasError) return false;
    ref.invalidate(myProfileProvider);
    return true;
  }
}

final AsyncNotifierProvider<ProfileSubmitNotifier, void> profileSubmitProvider =
    AsyncNotifierProvider<ProfileSubmitNotifier, void>(
      ProfileSubmitNotifier.new,
    );

class EditBasicDetailsNotifier extends AsyncNotifier<void> {
  @override
  Future<void> build() async {}

  Future<bool> updateProfile(Map<String, dynamic> body) async {
    state = const AsyncLoading<void>();
    state = await AsyncValue.guard(() async {
      await ref.read(profileRepositoryProvider).updateProfile(body);
    });
    if (state.hasError) return false;
    ref.invalidate(myProfileProvider);
    return true;
  }
}

final editBasicDetailsProvider =
    AsyncNotifierProvider<EditBasicDetailsNotifier, void>(
      EditBasicDetailsNotifier.new,
    );

class EditDisabilityDetailsNotifier extends AsyncNotifier<void> {
  @override
  Future<void> build() async {}

  Future<bool> updateDisabilityAndHealth({
    required Map<String, dynamic> profileBody,
    required Map<String, dynamic> sensitiveBody,
  }) async {
    state = const AsyncLoading<void>();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(profileRepositoryProvider);
      if (profileBody.isNotEmpty) {
        await repo.updateProfile(profileBody);
      }
      if (sensitiveBody.isNotEmpty) {
        await repo.updateSensitiveData(sensitiveBody);
      }
    });
    if (state.hasError) return false;
    ref.invalidate(myProfileProvider);
    return true;
  }
}

final editDisabilityDetailsProvider =
    AsyncNotifierProvider<EditDisabilityDetailsNotifier, void>(
      EditDisabilityDetailsNotifier.new,
    );

class EditPartnerPreferencesNotifier extends AsyncNotifier<void> {
  @override
  Future<void> build() async {}

  Future<bool> updatePreferences(Map<String, dynamic> body) async {
    state = const AsyncLoading<void>();
    state = await AsyncValue.guard(() async {
      await ref.read(profileRepositoryProvider).updatePartnerPreferences(body);
    });
    if (state.hasError) return false;
    ref.invalidate(myProfileProvider);
    return true;
  }
}

final editPartnerPreferencesProvider =
    AsyncNotifierProvider<EditPartnerPreferencesNotifier, void>(
      EditPartnerPreferencesNotifier.new,
    );

