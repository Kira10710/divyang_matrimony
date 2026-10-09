/// Marital status — mirrors `MaritalStatusEnum` in backend/app/models/enums.py.
enum MaritalStatus {
  neverMarried('Never married', 'NEVER_MARRIED'),
  divorced('Divorced', 'DIVORCED'),
  widowed('Widowed', 'WIDOWED'),
  separated('Separated', 'SEPARATED');

  final String displayName;
  final String apiValue;
  const MaritalStatus(this.displayName, this.apiValue);

  static MaritalStatus? fromApi(String? apiValue) {
    if (apiValue == null) return null;
    return MaritalStatus.values
        .where((e) => e.apiValue == apiValue)
        .firstOrNull;
  }
}
