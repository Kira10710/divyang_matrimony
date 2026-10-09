// Design tokens — the single source of truth for all visual constants.
//
// Every widget references these tokens instead of hardcoded values.
// This is what makes high-contrast theme swapping cheap (Section 9)
// and multi-platform branding feasible (Section 14).
//
// See Architecture Section 2.5 for full rationale.

/// --- Spacing (8pt grid) ---
class Spacing {
  Spacing._();
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 48;
}

/// --- Border Radius ---
class AppRadius {
  AppRadius._();
  static const double sm = 4;
  static const double md = 8;
  static const double lg = 12;
  static const double xl = 16;
  static const double card = 12;
  static const double button = 8;
  static const double dialog = 16;
}

/// --- Elevation ---
class AppElevation {
  AppElevation._();
  static const double none = 0;
  static const double card = 2;
  static const double dialog = 8;
  static const double appBar = 4;
}
