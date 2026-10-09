/// Who manages this profile — set during registration.
///
/// See Architecture Section 2.2:
/// - Affects pronoun copy in forms ("Tell us about yourself" vs "about them")
/// - Determines whose phone number is primary contact
/// - Displayed as a trust badge on profile cards
///
/// [apiValue] mirrors `ProfileManagedByEnum` in backend/app/models/enums.py.
enum ProfileManagedBy {
  self_managed('Myself', 'SELF'),
  parent('My son / daughter', 'PARENT'),
  sibling('My brother / sister', 'SIBLING'),
  guardian('Someone in my care', 'GUARDIAN');

  final String displayName;
  final String apiValue;
  const ProfileManagedBy(this.displayName, this.apiValue);

  bool get isSelf => this == ProfileManagedBy.self_managed;
}
