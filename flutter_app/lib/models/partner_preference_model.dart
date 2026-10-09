import 'enums/disability_type.dart';
import 'enums/gender.dart';
import 'enums/marital_status.dart';

class PartnerPreferenceModel {
  const PartnerPreferenceModel({
    required this.id,
    required this.profileId,
    this.ageMin,
    this.ageMax,
    this.heightCmMin,
    this.heightCmMax,
    this.preferredGender,
    this.preferredMaritalStatuses,
    this.preferredDisabilityTypes,
    this.preferredMotherTongue,
  });

  factory PartnerPreferenceModel.fromJson(Map<String, dynamic> json) {
    return PartnerPreferenceModel(
      id: json['id'] as String,
      profileId: json['profile_id'] as String,
      ageMin: json['age_min'] as int?,
      ageMax: json['age_max'] as int?,
      heightCmMin: json['preferred_height_min_cm'] as int?,
      heightCmMax: json['preferred_height_max_cm'] as int?,
      preferredGender: Gender.fromApi(json['preferred_gender'] as String?),
      preferredMaritalStatuses:
          (json['preferred_marital_statuses'] as List<dynamic>?)
              ?.map((e) => MaritalStatus.fromApi(e as String?))
              .whereType<MaritalStatus>()
              .toList(),
      preferredDisabilityTypes:
          (json['preferred_disability_types'] as List<dynamic>?)
              ?.map((e) => DisabilityType.fromApi(e as String?))
              .whereType<DisabilityType>()
              .toList(),
      preferredMotherTongue: json['preferred_mother_tongue'] as String?,
    );
  }

  final String id;
  final String profileId;
  final int? ageMin;
  final int? ageMax;
  final int? heightCmMin;
  final int? heightCmMax;
  final Gender? preferredGender;
  final List<MaritalStatus>? preferredMaritalStatuses;
  final List<DisabilityType>? preferredDisabilityTypes;
  final String? preferredMotherTongue;
}
