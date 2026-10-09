import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/profile_options.dart';
import '../../../../models/enums/disability_type.dart';
import '../../../../models/enums/gender.dart';
import '../../../../models/partner_preference_model.dart';
import '../../../../shared/widgets/app_dropdown.dart';
import '../../../../shared/widgets/chip_choice_field.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/my_profile_provider.dart';

class EditPartnerPreferencesScreen extends ConsumerStatefulWidget {
  const EditPartnerPreferencesScreen({super.key});

  @override
  ConsumerState<EditPartnerPreferencesScreen> createState() =>
      _EditPartnerPreferencesScreenState();
}

class _EditPartnerPreferencesScreenState
    extends ConsumerState<EditPartnerPreferencesScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  Gender? _lookingFor;
  late RangeValues _partnerAge;
  Set<DisabilityType> _partnerDisabilities = <DisabilityType>{};
  String? _partnerMotherTongue;

  @override
  void initState() {
    super.initState();
    final PartnerPreferenceModel? prefs =
        ref.read(myProfileProvider).valueOrNull?.partnerPreferences;

    _lookingFor = prefs?.preferredGender;
    _partnerAge = RangeValues(
      (prefs?.ageMin ?? ProfileOptions.minAge).toDouble(),
      (prefs?.ageMax ?? 50).toDouble(),
    );
    _partnerMotherTongue = prefs?.preferredMotherTongue;
    if (prefs?.preferredDisabilityTypes != null) {
      _partnerDisabilities = prefs!.preferredDisabilityTypes!.toSet();
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    final Map<String, dynamic> body = <String, dynamic>{
      'preferred_gender': _lookingFor?.apiValue,
      'age_min': _partnerAge.start.round(),
      'age_max': _partnerAge.end.round(),
      'preferred_disability_types': _partnerDisabilities.isEmpty
          ? null
          : <String>[
              for (final DisabilityType t in _partnerDisabilities) t.apiValue,
            ],
      'preferred_mother_tongue': _partnerMotherTongue,
    };

    final bool success = await ref
        .read(editPartnerPreferencesProvider.notifier)
        .updatePreferences(body);

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Preferences updated successfully')),
      );
      context.pop();
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to update preferences')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final TextTheme text = Theme.of(context).textTheme;
    final bool busy = ref.watch(editPartnerPreferencesProvider).isLoading;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Partner Preferences'),
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
              ChipChoiceField<Gender>(
                label: 'Looking for',
                value: _lookingFor,
                options: Gender.values,
                optionLabel: (Gender g) => switch (g) {
                  Gender.female => 'Bride',
                  Gender.male => 'Groom',
                  Gender.other => 'Anyone',
                },
                onSelected: (Gender g) => setState(() => _lookingFor = g),
              ),
              const SizedBox(height: Spacing.lg),
              Text(
                'Age: ${_partnerAge.start.round()} to ${_partnerAge.end.round()} years',
                style: text.titleMedium,
              ),
              RangeSlider(
                values: _partnerAge,
                min: ProfileOptions.minAge.toDouble(),
                max: 70,
                divisions: 70 - ProfileOptions.minAge,
                labels: RangeLabels(
                  '${_partnerAge.start.round()}',
                  '${_partnerAge.end.round()}',
                ),
                semanticFormatterCallback: (double v) => '${v.round()} years',
                onChanged: (RangeValues v) => setState(() => _partnerAge = v),
              ),
              const SizedBox(height: Spacing.lg),
              ChipMultiChoiceField<DisabilityType>(
                label: "Partner's disability",
                helperText: 'Leave all unselected to stay open to everyone.',
                value: _partnerDisabilities,
                options: DisabilityType.values,
                optionLabel: (DisabilityType t) => t.displayName,
                onChanged: (Set<DisabilityType> s) =>
                    setState(() => _partnerDisabilities = s),
              ),
              const SizedBox(height: Spacing.lg),
              AppDropdown<String?>(
                label: "Partner's mother tongue",
                value: _partnerMotherTongue,
                items: <String?>[null, ...ProfileOptions.motherTongues],
                itemLabel: (String? s) => s ?? 'Any language',
                onChanged: (String? s) =>
                    setState(() => _partnerMotherTongue = s),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
