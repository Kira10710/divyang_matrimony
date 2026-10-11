import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../demo/sample_profiles.dart';
import '../../../../models/enums/disability_type.dart';
import '../../../../models/enums/gender.dart';
import '../../../../models/enums/marital_status.dart';
import '../../../../models/profile_model.dart';

class SearchFilters {
  const SearchFilters({
    this.gender = Gender.female,
    this.age = const RangeValues(21, 40),
    this.disability,
    this.maritalStatus,
    this.motherTongue,
  });

  final Gender gender;
  final RangeValues age;
  final DisabilityType? disability;
  final MaritalStatus? maritalStatus;
  final String? motherTongue;

  bool matches(ProfileModel p) {
    final int? a = p.age;
    return p.gender == gender &&
        (a == null || (a >= age.start && a <= age.end)) &&
        (disability == null || p.disabilityType == disability) &&
        (maritalStatus == null || p.maritalStatus == maritalStatus) &&
        (motherTongue == null || p.motherTongue == motherTongue);
  }
}

final StateProvider<SearchFilters> searchFiltersProvider =
    StateProvider<SearchFilters>((Ref ref) => const SearchFilters());

final Provider<List<ProfileModel>> searchResultsProvider =
    Provider<List<ProfileModel>>((Ref ref) {
      final SearchFilters f = ref.watch(searchFiltersProvider);
      return sampleProfiles.where(f.matches).toList();
    });

/// Mother tongues present in the sample data, for the filter dropdown.
final List<String> sampleMotherTongues =
    sampleProfiles
        .map((p) => p.motherTongue)
        .whereType<String>()
        .toSet()
        .toList()
      ..sort();
