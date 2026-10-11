import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../routing/route_names.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: ListView(
            children: <Widget>[
              ListTile(
                leading: const Icon(Icons.person_outline_rounded),
                title: const Text('Edit my profile'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.push(RouteNames.editProfile),
              ),
              ListTile(
                leading: const Icon(Icons.lock_outline_rounded),
                title: const Text('Privacy'),
                subtitle: const Text(
                  'Who can see your photos and contact details',
                ),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.push(RouteNames.privacySettings),
              ),
              ListTile(
                leading: const Icon(Icons.accessibility_new_rounded),
                title: const Text('Accessibility'),
                subtitle: const Text('Text size and contrast'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.push(RouteNames.accessibilitySettings),
              ),
              ListTile(
                leading: const Icon(Icons.workspace_premium_outlined),
                title: const Text('Plans'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.push(RouteNames.subscriptionPlans),
              ),
              const Divider(),
              ListTile(
                leading: Icon(
                  Icons.delete_outline_rounded,
                  color: Theme.of(context).colorScheme.error,
                ),
                title: const Text('Delete account'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.push(RouteNames.deleteAccount),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
