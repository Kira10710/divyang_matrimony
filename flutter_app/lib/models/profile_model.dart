import 'enums/disability_type.dart';
import 'enums/gender.dart';
import 'enums/marital_status.dart';
import 'photo_model.dart';
import 'partner_preference_model.dart';
import 'sensitive_data_model.dart';

/// The signed-in user's own profile, parsed from `GET /profiles/me`
/// (`ProfileWithSensitiveOut` in backend/app/schemas/profile.py).
///
/// Only the fields the app currently displays are parsed; extend as screens
/// need more.
class ProfileModel {
  const ProfileModel({
    required this.id,
    required this.firstName,
    required this.completenessScore,
    required this.verificationStatus,
    this.lastName,
    this.gender,
    this.dateOfBirth,
    this.maritalStatus,
    this.heightCm,
    this.education,
    this.occupation,
    this.annualIncome,
    this.motherTongue,
    this.age,
    this.city,
    this.state,
    this.pincode,
    this.bio,
    this.disabilityType,
    this.photos = const [],
    this.sensitiveData,
    this.partnerPreferences,
  });

  factory ProfileModel.fromOwnProfileJson(Map<String, dynamic> json) {
    final Map<String, dynamic> p = json['profile'] as Map<String, dynamic>;
    return ProfileModel(
      id: p['id'] as String,
      firstName: p['first_name'] as String,
      lastName: p['last_name'] as String?,
      gender: Gender.fromApi(p['gender'] as String?),
      dateOfBirth: p['date_of_birth'] != null
          ? DateTime.tryParse(p['date_of_birth'] as String)
          : null,
      maritalStatus: MaritalStatus.fromApi(p['marital_status'] as String?),
      heightCm: p['height_cm'] as int?,
      education: p['education'] as String?,
      occupation: p['occupation'] as String?,
      annualIncome: p['annual_income'] as String?,
      motherTongue: p['mother_tongue'] as String?,
      age: p['age'] as int?,
      city: p['city'] as String?,
      state: p['state'] as String?,
      pincode: p['pincode'] as String?,
      bio: p['bio'] as String?,
      disabilityType: DisabilityType.fromApi(p['disability_type'] as String?),
      completenessScore: p['completeness_score'] as int? ?? 0,
      verificationStatus: p['verification_status'] as String? ?? 'PENDING',
      photos:
          (p['photos'] as List<dynamic>?)
              ?.map((e) => PhotoModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      sensitiveData: json['sensitive_data'] != null
          ? SensitiveDataModel.fromJson(
              json['sensitive_data'] as Map<String, dynamic>,
            )
          : null,
      partnerPreferences: json['partner_preferences'] != null
          ? PartnerPreferenceModel.fromJson(
              json['partner_preferences'] as Map<String, dynamic>,
            )
          : null,
    );
  }

  final String id;
  final String firstName;
  final String? lastName;
  final Gender? gender;
  final DateTime? dateOfBirth;
  final MaritalStatus? maritalStatus;
  final int? heightCm;
  final String? education;
  final String? occupation;
  final String? annualIncome;
  final String? motherTongue;
  final int? age;
  final String? city;
  final String? state;
  final String? pincode;
  final String? bio;
  final DisabilityType? disabilityType;
  final int completenessScore;
  final String verificationStatus;
  final List<PhotoModel> photos;
  final SensitiveDataModel? sensitiveData;
  final PartnerPreferenceModel? partnerPreferences;
}
