import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/constants/profile_options.dart';
import '../../../../core/errors/failures.dart';
import '../../../../core/utils/validators.dart';
import '../../../../models/enums/disability_type.dart';
import '../../../../models/enums/gender.dart';
import '../../../../models/enums/marital_status.dart';
import '../../../../models/enums/profile_managed_by.dart';
import '../../../../routing/route_names.dart';
import '../../../../shared/widgets/accessible_text_field.dart';
import '../../../../shared/widgets/app_dropdown.dart';
import '../../../../shared/widgets/chip_choice_field.dart';
import '../../../../shared/widgets/error_view.dart';
import '../../../../theme/design_tokens.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../providers/my_profile_provider.dart';
import '../providers/registration_draft_provider.dart';
import '../widgets/disability_details_form.dart';

/// Post-OTP profile creation, one topic per step. Submits to
/// `POST /profiles`, `PUT /profiles/me/sensitive` and
/// `PUT /profiles/me/preferences` at the end (see [ProfileSubmitNotifier]).
class ProfileWizardScreen extends ConsumerStatefulWidget {
  const ProfileWizardScreen({super.key});

  @override
  ConsumerState<ProfileWizardScreen> createState() =>
      _ProfileWizardScreenState();
}

class _ProfileWizardScreenState extends ConsumerState<ProfileWizardScreen> {
  static const List<(String, IconData)> _steps = <(String, IconData)>[
    ('Basic details', Icons.person_rounded),
    ('Disability', Icons.accessibility_new_rounded),
    ('Religion & language', Icons.translate_rounded),
    ('Education & career', Icons.school_rounded),
    ('Location & family', Icons.home_rounded),
    ('About & partner', Icons.favorite_rounded),
  ];

  final List<GlobalKey<FormState>> _formKeys =
      List<GlobalKey<FormState>>.generate(6, (_) => GlobalKey<FormState>());
  final ScrollController _scroll = ScrollController();
  int _step = 0;

  // Step 1 — basics
  late ProfileManagedBy _managedBy;
  final TextEditingController _firstName = TextEditingController();
  final TextEditingController _lastName = TextEditingController();
  final TextEditingController _dobText = TextEditingController();
  Gender? _gender;
  DateTime? _dob;
  MaritalStatus? _maritalStatus;

  // Step 2 — disability
  DisabilityDetails _disability = const DisabilityDetails();
  final TextEditingController _disabilityNote = TextEditingController();
  final TextEditingController _health = TextEditingController();

  // Step 3 — religion & language
  String? _religion;
  final TextEditingController _caste = TextEditingController();
  String? _motherTongue;
  int? _heightCm;

  // Step 4 — education & career
  String? _education;
  final TextEditingController _occupation = TextEditingController();
  String? _income;

  // Step 5 — location & family
  String? _state;
  final TextEditingController _city = TextEditingController();
  final TextEditingController _pincode = TextEditingController();
  String? _familyType;
  String? _familyStatus;
  final TextEditingController _whatsapp = TextEditingController();

  // Step 6 — about & partner
  final TextEditingController _bio = TextEditingController();
  Gender? _lookingFor;
  late RangeValues _partnerAge;
  Set<DisabilityType> _partnerDisabilities = <DisabilityType>{};
  String? _partnerMotherTongue;

  @override
  void initState() {
    super.initState();
    final RegistrationDraft draft = ref.read(registrationDraftProvider);
    _managedBy = draft.managedBy;
    final List<String> names = (draft.fullName ?? '').trim().split(
      RegExp(r'\s+'),
    );
    if (names.first.isNotEmpty) {
      _firstName.text = names.first;
      if (names.length > 1) _lastName.text = names.sublist(1).join(' ');
    }
    _lookingFor = draft.lookingFor;
    if (_lookingFor != null)
      _gender = _lookingFor == Gender.female ? Gender.male : Gender.female;
    _partnerAge = RangeValues(draft.ageMin.toDouble(), draft.ageMax.toDouble());
    _partnerMotherTongue = draft.motherTongue;
    _motherTongue = draft.motherTongue;
    if (draft.partnerDisability != null)
      _partnerDisabilities = <DisabilityType>{draft.partnerDisability!};

    final String? phone = ref.read(currentUserProvider)?.phone;
    if (phone != null && _managedBy.isSelf)
      _whatsapp.text = phone.replaceFirst('+91', '');
  }

  @override
  void dispose() {
    for (final TextEditingController c in <TextEditingController>[
      _firstName, _lastName, _dobText, _disabilityNote, _health, _caste, //
      _occupation, _city, _pincode, _whatsapp, _bio,
    ]) {
      c.dispose();
    }
    _scroll.dispose();
    super.dispose();
  }

  bool get _isSelf => _managedBy.isSelf;

  /// "you" / "Priya" — used in headings so a parent filling this in reads
  /// questions about their child, not about themselves.
  String get _subject => _isSelf
      ? 'you'
      : (_firstName.text.trim().isEmpty ? 'them' : _firstName.text.trim());

  String get _possessive => _isSelf
      ? 'your'
      : (_firstName.text.trim().isEmpty
            ? 'their'
            : "${_firstName.text.trim()}'s");

  void _scrollToTop() {
    if (_scroll.hasClients) _scroll.jumpTo(0);
  }

  void _next() {
    if (!(_formKeys[_step].currentState?.validate() ?? false)) {
      SemanticsService.sendAnnouncement(
        View.of(context),
        'Some answers need attention',
        Directionality.of(context),
      );
      return;
    }
    if (_step == _steps.length - 1) {
      _submit();
      return;
    }
    setState(() => _step++);
    _scrollToTop();
  }

  void _back() {
    if (_step == 0) return;
    setState(() => _step--);
    _scrollToTop();
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

  Map<String, dynamic> _withoutNulls(Map<String, dynamic> m) =>
      <String, dynamic>{
        for (final MapEntry<String, dynamic> e in m.entries)
          if (e.value != null) e.key: e.value,
      };

  Future<void> _submit() async {
    final ProfileSubmission submission = ProfileSubmission(
      profile: _withoutNulls(<String, dynamic>{
        'managed_by': _managedBy.apiValue,
        'first_name': _firstName.text.trim(),
        'last_name': _lastName.text.trim(),
        'gender': _gender!.apiValue,
        'date_of_birth': DateFormat('yyyy-MM-dd').format(_dob!),
        'marital_status': _maritalStatus!.apiValue,
        'disability_type': _disability.type!.apiValue,
        'height_cm': _heightCm,
        'education': _education,
        'occupation': _clean(_occupation.text),
        'annual_income': _income,
        'mother_tongue': _motherTongue,
        'city': _clean(_city.text),
        'state': _state,
        'pincode': _clean(_pincode.text),
        'bio': _clean(_bio.text),
      }),
      sensitive: _withoutNulls(<String, dynamic>{
        'disability_since': _disability.since,
        'disability_percentage': _disability.hasCertificate
            ? _disability.percentage
            : null,
        'mobility_aid': _disability.mobilityAids.isEmpty
            ? null
            : _disability.mobilityAids.join(', '),
        'disability_details': _clean(_disabilityNote.text),
        'health_conditions': _clean(_health.text),
        'religion': _religion,
        'caste': _clean(_caste.text),
        'family_type': _familyType,
        'family_status': _familyStatus,
        'whatsapp_number': _whatsapp.text.trim().isEmpty
            ? null
            : Validators.phoneToE164(_whatsapp.text),
      }),
      preferences: _withoutNulls(<String, dynamic>{
        'preferred_gender': _lookingFor?.apiValue,
        'age_min': _partnerAge.start.round(),
        'age_max': _partnerAge.end.round(),
        'preferred_disability_types': _partnerDisabilities.isEmpty
            ? null
            : <String>[
                for (final DisabilityType t in _partnerDisabilities) t.apiValue,
              ],
        'preferred_mother_tongue': _partnerMotherTongue,
      }),
    );

    final bool ok = await ref
        .read(profileSubmitProvider.notifier)
        .submit(submission);
    if (ok && mounted) context.go(RouteNames.home);
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<void> submitState = ref.watch(profileSubmitProvider);
    final bool submitting = submitState.isLoading;
    final Object? error = submitState.error;
    final TextTheme text = Theme.of(context).textTheme;
    final ColorScheme colors = Theme.of(context).colorScheme;
    final bool last = _step == _steps.length - 1;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Create profile'),
        leading: _step == 0
            ? null
            : IconButton(
                icon: const Icon(Icons.arrow_back),
                tooltip: 'Previous step',
                onPressed: _back,
              ),
        automaticallyImplyLeading: false,
        actions: <Widget>[
          TextButton(
            onPressed: () => ref.read(authProvider.notifier).logout(),
            child: const Text('Log out'),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            _StepHeader(steps: _steps, current: _step),
            Expanded(
              child: SingleChildScrollView(
                controller: _scroll,
                padding: const EdgeInsets.all(Spacing.lg),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 680),
                    child: Form(
                      key: _formKeys[_step],
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Semantics(
                            header: true,
                            child: Text(
                              _stepTitle(),
                              style: text.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          const SizedBox(height: Spacing.xs),
                          Text(
                            _stepSubtitle(),
                            style: text.bodyLarge?.copyWith(
                              color: colors.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(height: Spacing.lg),
                          ..._stepBody(),
                          if (error != null && last) ...<Widget>[
                            const SizedBox(height: Spacing.lg),
                            InlineErrorBanner(
                              message: error is Failure
                                  ? error.message
                                  : 'Could not save the profile. Please try again.',
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
            _BottomBar(
              isFirst: _step == 0,
              isLast: last,
              busy: submitting,
              onBack: _back,
              onNext: submitting ? null : _next,
            ),
          ],
        ),
      ),
    );
  }

  String _stepTitle() => switch (_step) {
    0 => _isSelf ? 'Tell us about yourself' : 'Tell us about $_subject',
    1 => 'About $_possessive disability',
    2 => 'Religion & language',
    3 => 'Education & career',
    4 => 'Where ${_isSelf ? 'you live' : '$_subject lives'} & family',
    _ => 'Almost done!',
  };

  String _stepSubtitle() => switch (_step) {
    0 => 'These basics appear on the profile.',
    1 =>
      'This helps us find someone who understands. You decide who sees the details.',
    2 => 'Religion and caste are shown only to premium members.',
    3 => 'Income is never shown to anyone else.',
    4 =>
      'The exact PIN code stays private. Family details are shown to premium members.',
    _ =>
      'Describe ${_isSelf ? 'yourself' : _subject} and who ${_isSelf ? 'you are' : 'they are'} hoping to meet.',
  };

  List<Widget> _stepBody() => switch (_step) {
    0 => _basicsStep(),
    1 => <Widget>[
      DisabilityDetailsForm(
        value: _disability,
        isSelf: _isSelf,
        detailsController: _disabilityNote,
        healthController: _health,
        onChanged: (DisabilityDetails d) => setState(() => _disability = d),
      ),
    ],
    2 => _backgroundStep(),
    3 => _careerStep(),
    4 => _locationStep(),
    _ => _aboutStep(),
  };

  static const SizedBox _gap = SizedBox(height: Spacing.md + 4);

  List<Widget> _basicsStep() => <Widget>[
    AppDropdown<ProfileManagedBy>(
      label: 'This profile is for',
      value: _managedBy,
      items: ProfileManagedBy.values,
      itemLabel: (ProfileManagedBy m) => m.displayName,
      onChanged: (ProfileManagedBy? m) =>
          setState(() => _managedBy = m ?? _managedBy),
    ),
    _gap,
    LayoutBuilder(
      builder: (BuildContext context, BoxConstraints c) {
        final Widget first = AccessibleTextField(
          label: 'First name *',
          controller: _firstName,
          textCapitalization: TextCapitalization.words,
          textInputAction: TextInputAction.next,
          onChanged: (_) => setState(() {}),
          validator: (String? v) =>
              Validators.required(v, message: 'Enter the first name'),
        );
        final Widget lastName = AccessibleTextField(
          label: 'Last name *',
          controller: _lastName,
          textCapitalization: TextCapitalization.words,
          textInputAction: TextInputAction.next,
          helperText: 'Shown only to registered members',
          validator: (String? v) =>
              Validators.required(v, message: 'Enter the last name'),
        );
        if (c.maxWidth < 480)
          return Column(children: <Widget>[first, _gap, lastName]);
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(child: first),
            const SizedBox(width: Spacing.md),
            Expanded(child: lastName),
          ],
        );
      },
    ),
    _gap,
    ChipChoiceField<Gender>(
      label: 'Gender *',
      value: _gender,
      options: Gender.values,
      optionLabel: (Gender g) => g.displayName,
      validator: (Gender? g) => g == null ? 'Please choose one' : null,
      onSelected: (Gender g) => setState(() => _gender = g),
    ),
    _gap,
    AccessibleTextField(
      label: 'Date of birth *',
      controller: _dobText,
      readOnly: true,
      onTap: _pickDob,
      suffixIcon: const Icon(Icons.calendar_month_rounded),
      helperText:
          'Only the age is shown to others. Must be ${ProfileOptions.minAge} or older.',
      validator: (_) => _dob == null ? 'Choose the date of birth' : null,
    ),
    _gap,
    ChipChoiceField<MaritalStatus>(
      label: 'Marital status *',
      value: _maritalStatus,
      options: MaritalStatus.values,
      optionLabel: (MaritalStatus m) => m.displayName,
      validator: (MaritalStatus? m) => m == null ? 'Please choose one' : null,
      onSelected: (MaritalStatus m) => setState(() => _maritalStatus = m),
    ),
  ];

  List<Widget> _backgroundStep() => <Widget>[
    AppDropdown<String>(
      label: 'Religion',
      value: _religion,
      items: ProfileOptions.religions,
      itemLabel: (String s) => s,
      onChanged: (String? s) => setState(() => _religion = s),
    ),
    _gap,
    AccessibleTextField(
      label: 'Caste / community (optional)',
      controller: _caste,
      textCapitalization: TextCapitalization.words,
    ),
    _gap,
    AppDropdown<String>(
      label: 'Mother tongue *',
      value: _motherTongue,
      items: ProfileOptions.motherTongues,
      itemLabel: (String s) => s,
      validator: (String? s) => s == null ? 'Choose a mother tongue' : null,
      onChanged: (String? s) => setState(() => _motherTongue = s),
    ),
    _gap,
    AppDropdown<int>(
      label: 'Height',
      value: _heightCm,
      items: ProfileOptions.heightsCm,
      itemLabel: ProfileOptions.formatHeight,
      onChanged: (int? h) => setState(() => _heightCm = h),
    ),
  ];

  List<Widget> _careerStep() => <Widget>[
    AppDropdown<String>(
      label: 'Highest education *',
      value: _education,
      items: ProfileOptions.education,
      itemLabel: (String s) => s,
      validator: (String? s) =>
          s == null ? 'Choose the highest education' : null,
      onChanged: (String? s) => setState(() => _education = s),
    ),
    _gap,
    AccessibleTextField(
      label: 'Occupation',
      hintText: 'e.g. Software developer, Teacher, Running a family business',
      controller: _occupation,
      textCapitalization: TextCapitalization.sentences,
    ),
    _gap,
    AppDropdown<String>(
      label: 'Annual income',
      value: _income,
      items: ProfileOptions.annualIncome,
      itemLabel: (String s) => s,
      onChanged: (String? s) => setState(() => _income = s),
    ),
  ];

  List<Widget> _locationStep() => <Widget>[
    AppDropdown<String>(
      label: 'State *',
      value: _state,
      items: ProfileOptions.indianStates,
      itemLabel: (String s) => s,
      validator: (String? s) => s == null ? 'Choose a state' : null,
      onChanged: (String? s) => setState(() => _state = s),
    ),
    _gap,
    AccessibleTextField(
      label: 'City *',
      controller: _city,
      textCapitalization: TextCapitalization.words,
      textInputAction: TextInputAction.next,
      validator: (String? v) =>
          Validators.required(v, message: 'Enter the city'),
    ),
    _gap,
    AccessibleTextField(
      label: 'PIN code (optional)',
      controller: _pincode,
      keyboardType: TextInputType.number,
      inputFormatters: <TextInputFormatter>[
        FilteringTextInputFormatter.digitsOnly,
        LengthLimitingTextInputFormatter(6),
      ],
      validator: (String? v) =>
          (v ?? '').isEmpty || v!.length == 6 ? null : 'PIN code has 6 digits',
    ),
    _gap,
    ChipChoiceField<String>(
      label: 'Family type',
      value: _familyType,
      options: ProfileOptions.familyTypes,
      optionLabel: (String s) => s,
      onSelected: (String s) => setState(() => _familyType = s),
    ),
    _gap,
    ChipChoiceField<String>(
      label: 'Family status',
      value: _familyStatus,
      options: ProfileOptions.familyStatus,
      optionLabel: (String s) => s,
      onSelected: (String s) => setState(() => _familyStatus = s),
    ),
    _gap,
    AccessibleTextField(
      label: 'WhatsApp number for matches (optional)',
      helperText:
          'Encrypted, and shared only after both sides accept an interest.',
      controller: _whatsapp,
      keyboardType: TextInputType.phone,
      prefixText: '+91 ',
      inputFormatters: <TextInputFormatter>[
        FilteringTextInputFormatter.digitsOnly,
        LengthLimitingTextInputFormatter(10),
      ],
      validator: (String? v) => (v ?? '').isEmpty ? null : Validators.phone(v),
    ),
  ];

  List<Widget> _aboutStep() {
    final TextTheme text = Theme.of(context).textTheme;
    return <Widget>[
      AccessibleTextField(
        label: 'About ${_isSelf ? 'me' : _subject}',
        hintText: _isSelf
            ? 'What do you enjoy? What matters to you in a partner?'
            : 'What do they enjoy? What kind of partner are you looking for them?',
        controller: _bio,
        maxLength: AppConstants.maxBioLength,
        maxLines: 5,
        keyboardType: TextInputType.multiline,
        textCapitalization: TextCapitalization.sentences,
      ),
      const SizedBox(height: Spacing.lg),
      const Divider(),
      Semantics(
        header: true,
        child: Text('Partner preferences', style: text.titleLarge),
      ),
      const SizedBox(height: Spacing.md),
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
      _gap,
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
      _gap,
      ChipMultiChoiceField<DisabilityType>(
        label: "Partner's disability",
        helperText: 'Leave all unselected to stay open to everyone.',
        value: _partnerDisabilities,
        options: DisabilityType.values,
        optionLabel: (DisabilityType t) => t.displayName,
        onChanged: (Set<DisabilityType> s) =>
            setState(() => _partnerDisabilities = s),
      ),
      _gap,
      AppDropdown<String?>(
        label: "Partner's mother tongue",
        value: _partnerMotherTongue,
        items: <String?>[null, ...ProfileOptions.motherTongues],
        itemLabel: (String? s) => s ?? 'Any language',
        onChanged: (String? s) => setState(() => _partnerMotherTongue = s),
      ),
    ];
  }
}

class _StepHeader extends StatelessWidget {
  const _StepHeader({required this.steps, required this.current});

  final List<(String, IconData)> steps;
  final int current;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final TextTheme text = Theme.of(context).textTheme;
    final bool wide = MediaQuery.sizeOf(context).width >= 900;

    return Semantics(
      label: 'Step ${current + 1} of ${steps.length}: ${steps[current].$1}',
      liveRegion: true,
      excludeSemantics: true,
      child: Container(
        color: colors.surfaceContainerLow,
        padding: const EdgeInsets.fromLTRB(
          Spacing.lg,
          Spacing.md,
          Spacing.lg,
          Spacing.md,
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                if (wide)
                  Row(
                    children: <Widget>[
                      for (int i = 0; i < steps.length; i++) ...<Widget>[
                        _StepDot(
                          index: i,
                          current: current,
                          icon: steps[i].$2,
                          label: steps[i].$1,
                        ),
                        if (i < steps.length - 1)
                          Expanded(
                            child: Container(
                              height: 2,
                              margin: const EdgeInsets.symmetric(
                                horizontal: Spacing.xs,
                              ),
                              color: i < current
                                  ? colors.primary
                                  : colors.outlineVariant,
                            ),
                          ),
                      ],
                    ],
                  )
                else ...<Widget>[
                  Text(
                    'Step ${current + 1} of ${steps.length} · ${steps[current].$1}',
                    style: text.labelLarge?.copyWith(color: colors.primary),
                  ),
                  const SizedBox(height: Spacing.sm),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: (current + 1) / steps.length,
                      minHeight: 8,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StepDot extends StatelessWidget {
  const _StepDot({
    required this.index,
    required this.current,
    required this.icon,
    required this.label,
  });

  final int index;
  final int current;
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final bool done = index < current;
    final bool active = index == current;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        CircleAvatar(
          radius: 16,
          backgroundColor: active || done
              ? colors.primary
              : colors.surfaceContainerHighest,
          child: Icon(
            done ? Icons.check_rounded : icon,
            size: 18,
            color: active || done ? colors.onPrimary : colors.onSurfaceVariant,
          ),
        ),
        if (active) ...<Widget>[
          const SizedBox(width: Spacing.xs + 2),
          Text(
            label,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
              color: colors.primary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ],
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar({
    required this.isFirst,
    required this.isLast,
    required this.busy,
    required this.onBack,
    required this.onNext,
  });

  final bool isFirst;
  final bool isLast;
  final bool busy;
  final VoidCallback onBack;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 8,
      color: Theme.of(context).colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: Spacing.lg,
          vertical: Spacing.sm + 4,
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 680),
            child: Row(
              children: <Widget>[
                if (!isFirst) ...<Widget>[
                  Expanded(
                    child: OutlinedButton(
                      onPressed: busy ? null : onBack,
                      child: const Text('Back'),
                    ),
                  ),
                  const SizedBox(width: Spacing.md),
                ],
                Expanded(
                  flex: 2,
                  child: FilledButton(
                    onPressed: onNext,
                    child: busy
                        ? const SizedBox.square(
                            dimension: 22,
                            child: CircularProgressIndicator(strokeWidth: 2.5),
                          )
                        : Text(isLast ? 'Create profile' : 'Continue'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
