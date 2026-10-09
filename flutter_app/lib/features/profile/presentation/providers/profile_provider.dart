import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../models/profile_model.dart';
import '../../../../repositories/providers/repository_providers.dart';

/// Fetches a profile by ID, applying the viewer's visibility tier rules server-side.
final FutureProviderFamily<ProfileModel, String> profileProvider =
    FutureProvider.family<ProfileModel, String>((Ref ref, String id) async {
      return ref.read(profileRepositoryProvider).getProfileById(id);
    });
