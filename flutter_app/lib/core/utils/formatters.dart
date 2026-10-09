// Formatting utilities (date, currency, phone number display).

/// Formats an E.164 Indian phone number (`+919876543210`) for display as
/// `+91 98765 43210`. Falls back to the raw input for any shape it doesn't
/// recognize rather than guessing.
String formatPhoneForDisplay(String phone) {
  final String cleaned = phone.replaceAll(RegExp(r'\s+'), '');
  final RegExpMatch? match = RegExp(
    r'^(\+\d{1,3})(\d{5})(\d{5})$',
  ).firstMatch(cleaned);
  if (match == null) return phone;
  return '${match[1]} ${match[2]} ${match[3]}';
}
