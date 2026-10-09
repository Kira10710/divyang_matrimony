/// Pick-list values for profile registration and partner preferences.
///
/// The backend stores these as free strings (see backend/app/schemas/profile.py),
/// so the list lives client-side; values are sent exactly as shown.
class ProfileOptions {
  ProfileOptions._();

  static const List<String> disabilitySince = <String>[
    'Since birth',
    'Since childhood',
    'Acquired later in life',
  ];

  static const List<String> mobilityAids = <String>[
    'None',
    'Wheelchair',
    'Crutches / walker',
    'Prosthetic limb',
    'Calipers / orthosis',
    'White cane',
    'Hearing aid / cochlear implant',
    'Sign language',
    'Other',
  ];

  static const List<String> religions = <String>[
    'Hindu',
    'Muslim',
    'Christian',
    'Sikh',
    'Buddhist',
    'Jain',
    'Parsi',
    'Jewish',
    'No religion',
    'Other',
  ];

  static const List<String> motherTongues = <String>[
    'Hindi',
    'Marathi',
    'Gujarati',
    'Bengali',
    'Tamil',
    'Telugu',
    'Kannada',
    'Malayalam',
    'Punjabi',
    'Odia',
    'Assamese',
    'Urdu',
    'Konkani',
    'Sindhi',
    'Marwari',
    'English',
    'Other',
  ];

  static const List<String> education = <String>[
    'Below 10th',
    '10th',
    '12th',
    'Diploma',
    "Bachelor's degree",
    "Master's degree",
    'Doctorate',
    'Professional (CA / CS / MBBS / LLB)',
    'Other',
  ];

  static const List<String> annualIncome = <String>[
    'Not working / prefer not to say',
    'Up to ₹2 lakh',
    '₹2 – 5 lakh',
    '₹5 – 10 lakh',
    '₹10 – 20 lakh',
    '₹20 – 50 lakh',
    '₹50 lakh+',
  ];

  static const List<String> familyTypes = <String>['Nuclear', 'Joint'];

  static const List<String> familyStatus = <String>[
    'Middle class',
    'Upper middle class',
    'Affluent',
  ];

  static const List<String> indianStates = <String>[
    'Andhra Pradesh',
    'Arunachal Pradesh',
    'Assam',
    'Bihar',
    'Chhattisgarh',
    'Delhi',
    'Goa',
    'Gujarat',
    'Haryana',
    'Himachal Pradesh',
    'Jammu & Kashmir',
    'Jharkhand',
    'Karnataka',
    'Kerala',
    'Ladakh',
    'Madhya Pradesh',
    'Maharashtra',
    'Manipur',
    'Meghalaya',
    'Mizoram',
    'Nagaland',
    'Odisha',
    'Puducherry',
    'Punjab',
    'Rajasthan',
    'Sikkim',
    'Tamil Nadu',
    'Telangana',
    'Tripura',
    'Uttar Pradesh',
    'Uttarakhand',
    'West Bengal',
    'Other',
  ];

  /// 4'0" (122 cm) to 7'0" (213 cm) in one-inch steps.
  static List<int> get heightsCm => <int>[
    for (int inches = 48; inches <= 84; inches++) (inches * 2.54).round(),
  ];

  static String formatHeight(int cm) {
    final int totalInches = (cm / 2.54).round();
    return "${totalInches ~/ 12}' ${totalInches % 12}\" · $cm cm";
  }

  static const int minAge = 18;
  static const int maxAge = 80;
}
