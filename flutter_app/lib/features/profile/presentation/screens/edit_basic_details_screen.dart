import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/constants/profile_options.dart';
import '../../../../models/enums/gender.dart';
import '../../../../models/enums/marital_status.dart';
import '../../../../models/profile_model.dart';
import '../../../../shared/widgets/accessible_text_field.dart';
import '../../../../shared/widgets/app_dropdown.dart';
import '../../../../shared/widgets/chip_choice_field.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/my_profile_provider.dart';

class EditBasicDetailsScreen extends ConsumerStatefulWidget {
  const EditBasicDetailsScreen({super.key});

  @override
  ConsumerState<EditBasicDetailsScreen> createState() =>
      _EditBasicDetailsScreenState();
}

class _EditBasicDetailsScreenState
    extends ConsumerState<EditBasicDetailsScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _firstName = TextEditingController();
  final TextEditingController _lastName = TextEditingController();
  final TextEditingController _dobText = TextEditingController();
  final TextEditingController _city = TextEditingController();
  final TextEditingController _bio = TextEditingController();

  Gender? _gender;
  DateTime? _dob;
  MaritalStatus? _maritalStatus;
  String? _state;

  @override
  void initState() {
    super.initState();
    final ProfileModel? profile = ref.read(myProfileProvider).valueOrNull;
    if (profile != null) {
      _firstName.text = profile.firstName;
      _lastName.text = profile.lastName ?? '';
      _gender = profile.gender;
      _dob = profile.dateOfBirth;
      if (_dob != null) {
        _dobText.text = DateFormat('d MMMM yyyy').format(_dob!);
      }
      _maritalStatus = profile.maritalStatus;
      _city.text = profile.city ?? '';
      _state = profile.state;
      _bio.text = profile.bio ?? '';
    }
  }

  @override
  void dispose() {
    _firstName.dispose();
    _lastName.dispose();
    _dobText.dispose();
    _city.dispose();
    _bio.dispose();
    super.dispose();
  }

  Future<void> _pickDob() async {
    final DateTime now = DateTime.now();
    final DateTime latest = DateTime(
      now.year - ProfileOptions.minAge,
      now.month,
      now.day,
    );
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: _dob ?? DateTime(now.year - 27, now.month, now.day),
      firstDate: DateTime(now.year - ProfileOptions.maxAge, now.month, now.day),
      lastDate: latest,
      helpText: 'Date of birth',
    );
    if (picked == null) return;
    setState(() {
      _dob = picked;
      _dobText.text = DateFormat('d MMMM yyyy').format(picked);
    });
  }

  static String? _clean(String text) {
    final String t = text.trim();
    return t.isEmpty ? null : t;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    final Map<String, dynamic> body = <String, dynamic>{
      if (_clean(_firstName.text) != null) 'first_name': _firstName.text.trim(),
      if (_clean(_lastName.text) != null) 'last_name': _lastName.text.trim(),
      if (_gender != null) 'gender': _gender!.apiValue,
      if (_dob != null) 'date_of_birth': DateFormat('yyyy-MM-dd').format(_dob!),
      if (_maritalStatus != null) 'marital_status': _maritalStatus!.apiValue,
      if (_clean(_city.text) != null) 'city': _city.text.trim(),
      if (_state != null) 'state': _state,
      if (_clean(_bio.text) != null) 'bio': _bio.text.trim(),
    };

    final bool success =
        await ref.read(editBasicDetailsProvider.notifier).updateProfile(body);

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Basic details updated successfully')),
      );
      context.pop();
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to update basic details')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final bool busy = ref.watch(editBasicDetailsProvider).isLoading;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Basic Details'),
        actions: <Widget>[
          if (busy)
            const Padding(
              padding: EdgeInsets.only(right: 16),
              child: SizedBox.square(
                dimension: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          else
            TextButton(
              onPressed: _save,
              child: const Text('Save'),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(Spacing.lg),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              AccessibleTextField(
                label: 'First name *',
                controller: _firstName,
                textCapitalization: TextCapitalization.words,
                validator: (String? v) =>
                    (v ?? '').trim().isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: Spacing.md),
              AccessibleTextField(
                label: 'Last name',
                controller: _lastName,
                textCapitalization: TextCapitalization.words,
              ),
              const SizedBox(height: Spacing.md),
              ChipChoiceField<Gender>(
                label: 'Gender *',
                value: _gender,
                options: Gender.values,
                optionLabel: (Gender g) => g.displayName,
                onSelected: (Gender g) => setState(() => _gender = g),
              ),
              if (_gender == null)
                Padding(
                  padding: const EdgeInsets.only(top: 8, left: 12),
                  child: Text(
                    'Required',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                      fontSize: 12,
                    ),
                  ),
                ),
              const SizedBox(height: Spacing.md),
              AccessibleTextField(
                label: 'Date of birth *',
                controller: _dobText,
                readOnly: true,
                onTap: _pickDob,
                suffixIcon: const Icon(Icons.calendar_today_rounded),
                validator: (String? v) =>
                    (v ?? '').isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: Spacing.md),
              ChipChoiceField<MaritalStatus>(
                label: 'Marital status *',
                value: _maritalStatus,
                options: MaritalStatus.values,
                optionLabel: (MaritalStatus m) => m.displayName,
                onSelected: (MaritalStatus m) =>
                    setState(() => _maritalStatus = m),
              ),
              if (_maritalStatus == null)
                Padding(
                  padding: const EdgeInsets.only(top: 8, left: 12),
                  child: Text(
                    'Required',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                      fontSize: 12,
                    ),
                  ),
                ),
              const SizedBox(height: Spacing.md),
              AccessibleTextField(
                label: 'City',
                controller: _city,
                textCapitalization: TextCapitalization.words,
              ),
              const SizedBox(height: Spacing.md),
              AppDropdown<String?>(
                label: 'State',
                value: _state,
                items: <String?>[null, ...ProfileOptions.indianStates],
                itemLabel: (String? s) => s ?? 'Select state',
                onChanged: (String? s) => setState(() => _state = s),
              ),
              const SizedBox(height: Spacing.md),
              AccessibleTextField(
                label: 'About me',
                controller: _bio,
                maxLines: 4,
                textCapitalization: TextCapitalization.sentences,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
