/// Gender enum for profiles and search filters.
///
/// [apiValue] mirrors `GenderEnum` in backend/app/models/enums.py.
enum Gender {
  male('Male', 'MALE'),
  female('Female', 'FEMALE'),
  other('Other', 'OTHER');

  final String displayName;
  final String apiValue;
  const Gender(this.displayName, this.apiValue);

  static Gender? fromApi(String? value) {
    for (final Gender g in values) {
      if (g.apiValue == value) return g;
    }
    return null;
  }
}
