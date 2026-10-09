import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../models/profile_model.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../providers/my_profile_provider.dart';

class EditProfileScreen extends ConsumerWidget {
  const EditProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<ProfileModel?> profileState = ref.watch(myProfileProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Edit Profile')),
      body: profileState.when(
        loading: () => const LoadingIndicator(),
        error: (Object e, _) => Center(
          child: ErrorView(
            message: 'Could not load your profile.',
            onRetry: () => ref.invalidate(myProfileProvider),
          ),
        ),
        data: (ProfileModel? profile) {
          if (profile == null) {
            return const Center(child: Text('No profile found to edit.'));
          }
          return _EditOptionsList(profile: profile);
        },
      ),
    );
  }
}

class _EditOptionsList extends StatelessWidget {
  const _EditOptionsList({required this.profile});

  final ProfileModel profile;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        ListTile(
          leading: const Icon(Icons.person_rounded),
          title: const Text('Basic Details'),
          subtitle: const Text('Name, gender, age, location'),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () {
            context.push('/profile/edit-basic-details');
          },
        ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.accessibility_new_rounded),
          title: const Text('Disability & Health'),
          subtitle: const Text('Disability type, severity, health conditions'),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () {
            context.push('/profile/edit-disability-details');
          },
        ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.favorite_rounded),
          title: const Text('Partner Preferences'),
          subtitle: const Text('Age, gender, disability preferences'),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () {
            context.push('/profile/edit-partner-preferences');
          },
        ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.photo_library_rounded),
          title: const Text('Manage Photos'),
          subtitle: const Text('Add or remove profile photos'),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () {
            context.push('/profile/photos');
          },
        ),
      ],
    );
  }
}
