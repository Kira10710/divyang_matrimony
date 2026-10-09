import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../models/enums/disability_type.dart';
import '../../../../models/profile_model.dart';
import '../../../../theme/design_tokens.dart';
import '../providers/my_profile_provider.dart';
import '../widgets/disability_details_form.dart';

class EditDisabilityDetailsScreen extends ConsumerStatefulWidget {
  const EditDisabilityDetailsScreen({super.key});

  @override
  ConsumerState<EditDisabilityDetailsScreen> createState() =>
      _EditDisabilityDetailsScreenState();
}

class _EditDisabilityDetailsScreenState
    extends ConsumerState<EditDisabilityDetailsScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _disabilityNote = TextEditingController();
  final TextEditingController _health = TextEditingController();

  DisabilityDetails _disability = const DisabilityDetails();

  @override
  void initState() {
    super.initState();
    final ProfileModel? profile = ref.read(myProfileProvider).valueOrNull;

    if (profile != null) {
      final sensitive = profile.sensitiveData;

      _disabilityNote.text = sensitive?.disabilityDetails ?? '';
      _health.text = sensitive?.healthConditions ?? '';

      _disability = DisabilityDetails(
        type: profile.disabilityType,
        since: sensitive?.disabilitySince,
        hasCertificate: (sensitive?.disabilityPercentage ?? 0) > 0,
        percentage: sensitive?.disabilityPercentage ?? 40,
        mobilityAids: (sensitive?.mobilityAid ?? '')
            .split(',')
            .map((e) => e.trim())
            .where((e) => e.isNotEmpty)
            .toSet(),
      );
    }
  }

  @override
  void dispose() {
    _disabilityNote.dispose();
    _health.dispose();
    super.dispose();
  }

  static String? _clean(String text) {
    final String t = text.trim();
    return t.isEmpty ? null : t;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    final Map<String, dynamic> profileBody = <String, dynamic>{
      if (_disability.type != null) 'disability_type': _disability.type!.apiValue,
    };

    final Map<String, dynamic> sensitiveBody = <String, dynamic>{
      if (_disability.since != null) 'disability_since': _disability.since,
      if (_disability.hasCertificate)
        'disability_percentage': _disability.percentage,
      if (!_disability.hasCertificate) 'disability_percentage': null,
      'mobility_aid': _disability.mobilityAids.isEmpty
          ? null
          : _disability.mobilityAids.join(', '),
      'disability_details': _clean(_disabilityNote.text),
      'health_conditions': _clean(_health.text),
    };

    final bool success = await ref
        .read(editDisabilityDetailsProvider.notifier)
        .updateDisabilityAndHealth(
          profileBody: profileBody,
          sensitiveBody: sensitiveBody,
        );

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Disability details updated successfully')),
      );
      context.pop();
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to update disability details')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final bool busy = ref.watch(editDisabilityDetailsProvider).isLoading;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Disability & Health'),
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
          child: DisabilityDetailsForm(
            value: _disability,
            onChanged: (DisabilityDetails d) => setState(() => _disability = d),
            detailsController: _disabilityNote,
            healthController: _health,
            isSelf: true,
          ),
        ),
      ),
    );
  }
}
