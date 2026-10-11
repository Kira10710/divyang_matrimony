import 'package:flutter/material.dart';

/// Privacy toggles. Local state only in the showcase build.
class PrivacySettingsScreen extends StatefulWidget {
  const PrivacySettingsScreen({super.key});

  @override
  State<PrivacySettingsScreen> createState() => _PrivacySettingsScreenState();
}

class _PrivacySettingsScreenState extends State<PrivacySettingsScreen> {
  bool _photosOnlyMutual = true;
  bool _hideContact = true;
  bool _showDisabilityDetails = false;
  bool _appearInSearch = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Privacy')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: ListView(
            children: <Widget>[
              SwitchListTile(
                title: const Text('Show my photos only after mutual interest'),
                value: _photosOnlyMutual,
                onChanged: (v) => setState(() => _photosOnlyMutual = v),
              ),
              SwitchListTile(
                title: const Text('Hide phone number and email'),
                subtitle: const Text('Shared only when both sides accept'),
                value: _hideContact,
                onChanged: (v) => setState(() => _hideContact = v),
              ),
              SwitchListTile(
                title: const Text('Show detailed disability information'),
                subtitle: const Text(
                  'Percentage and aids, visible to approved matches',
                ),
                value: _showDisabilityDetails,
                onChanged: (v) => setState(() => _showDisabilityDetails = v),
              ),
              SwitchListTile(
                title: const Text('Appear in search results'),
                value: _appearInSearch,
                onChanged: (v) => setState(() => _appearInSearch = v),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
