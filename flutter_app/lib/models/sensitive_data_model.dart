class SensitiveDataModel {
  const SensitiveDataModel({
    this.disabilityPercentage,
    this.disabilitySince,
    this.disabilityDetails,
    this.healthConditions,
    this.anyGeneticDisorder,
    this.mobilityAid,
    this.aboutFamily,
    this.contactPhone,
    this.contactEmail,
    this.whatsappNumber,
  });

  factory SensitiveDataModel.fromJson(Map<String, dynamic> json) {
    return SensitiveDataModel(
      disabilityPercentage: json['disability_percentage'] as int?,
      disabilitySince: json['disability_since'] as String?,
      disabilityDetails: json['disability_details'] as String?,
      healthConditions: json['health_conditions'] as String?,
      anyGeneticDisorder: json['any_genetic_disorder'] as bool?,
      mobilityAid: json['mobility_aid'] as String?,
      aboutFamily: json['about_family'] as String?,
      contactPhone: json['contact_phone'] as String?,
      contactEmail: json['contact_email'] as String?,
      whatsappNumber: json['whatsapp_number'] as String?,
    );
  }

  final int? disabilityPercentage;
  final String? disabilitySince;
  final String? disabilityDetails;
  final String? healthConditions;
  final bool? anyGeneticDisorder;
  final String? mobilityAid;
  final String? aboutFamily;
  final String? contactPhone;
  final String? contactEmail;
  final String? whatsappNumber;
}
