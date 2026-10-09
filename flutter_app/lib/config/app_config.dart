/// Platform-specific feature flags.
///
/// Loaded based on [EnvConfig.platformId] — controls which features
/// are enabled for Divyang Matrimony vs future platforms (e.g., Senior Citizen Matrimony).
/// See Architecture Section 14.
class AppConfig {
  AppConfig._();

  // TODO: Load from platform_config when multi-platform is active.
  // For now, hardcoded for divyang_matrimony.

  static const bool disabilityFieldsEnabled = true;
  static const bool seniorCitizenCardEnabled = false;
  static const int defaultAgeMin = 18;
  static const int defaultAgeMax = 45;
}
