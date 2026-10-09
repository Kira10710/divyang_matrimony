import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../models/enums/disability_type.dart';
import '../../../../models/enums/gender.dart';
import '../../../../models/enums/profile_managed_by.dart';

/// What a visitor typed on the landing page (quick-search bar + "Create
/// profile" card), carried through OTP into the profile wizard so nothing
/// has to be asked twice. In-memory only — a web reload simply starts the
/// wizard empty.
class RegistrationDraft {
  const RegistrationDraft({
    this.managedBy = ProfileManagedBy.self_managed,
    this.fullName,
    this.lookingFor,
    this.ageMin = 21,
    this.ageMax = 35,
    this.motherTongue,
    this.partnerDisability,
  });

  final ProfileManagedBy managedBy;
  final String? fullName;

  /// Gender of the partner being searched for.
  final Gender? lookingFor;
  final int ageMin;
  final int ageMax;
  final String? motherTongue;

  /// Null means "open to any disability type".
  final DisabilityType? partnerDisability;

  RegistrationDraft copyWith({
    ProfileManagedBy? managedBy,
    String? fullName,
    Gender? lookingFor,
    int? ageMin,
    int? ageMax,
    String? motherTongue,
    DisabilityType? partnerDisability,
    bool clearPartnerDisability = false,
  }) {
    return RegistrationDraft(
      managedBy: managedBy ?? this.managedBy,
      fullName: fullName ?? this.fullName,
      lookingFor: lookingFor ?? this.lookingFor,
      ageMin: ageMin ?? this.ageMin,
      ageMax: ageMax ?? this.ageMax,
      motherTongue: motherTongue ?? this.motherTongue,
      partnerDisability: clearPartnerDisability
          ? null
          : partnerDisability ?? this.partnerDisability,
    );
  }
}

class RegistrationDraftNotifier extends Notifier<RegistrationDraft> {
  @override
  RegistrationDraft build() => const RegistrationDraft();

  void update(RegistrationDraft Function(RegistrationDraft) change) =>
      state = change(state);
}

final NotifierProvider<RegistrationDraftNotifier, RegistrationDraft>
registrationDraftProvider =
    NotifierProvider<RegistrationDraftNotifier, RegistrationDraft>(
      RegistrationDraftNotifier.new,
    );
