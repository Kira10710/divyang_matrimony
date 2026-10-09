/// Disability type enum — used in profiles, preferences, and search filters.
///
/// [apiValue] mirrors `DisabilityTypeEnum` in backend/app/models/enums.py.
/// See Architecture Section 4.2 for the full list.
enum DisabilityType {
  physical(
    'Physical / Locomotor',
    'PHYSICAL',
    'Mobility, limb difference, cerebral palsy, dwarfism…',
  ),
  visual('Visual', 'VISUAL', 'Blindness or low vision'),
  hearing(
    'Hearing / Speech',
    'HEARING',
    'Deaf, hard of hearing, speech & language',
  ),
  intellectual(
    'Intellectual / Developmental',
    'INTELLECTUAL',
    'Intellectual disability, autism, learning disability',
  ),
  multiple('Multiple', 'MULTIPLE', 'More than one of the above');

  final String displayName;
  final String apiValue;
  final String description;
  const DisabilityType(this.displayName, this.apiValue, this.description);

  static DisabilityType? fromApi(String? value) {
    for (final DisabilityType t in values) {
      if (t.apiValue == value) return t;
    }
    return null;
  }
}
