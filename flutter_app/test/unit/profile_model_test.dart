import 'package:flutter_test/flutter_test.dart';
import 'package:divyang_matrimony/models/profile_model.dart';
import 'package:divyang_matrimony/models/enums/gender.dart';
import 'package:divyang_matrimony/models/enums/disability_type.dart';
import 'package:divyang_matrimony/models/enums/marital_status.dart';

void main() {
  group('ProfileModel Parsing', () {
    test('should parse empty aggregation correctly', () {
      final json = {
        "profile": {
          "id": "profile-123",
          "user_id": "user-123",
          "platform_id": "platform-1",
          "first_name": "Test",
          "gender": "MALE",
          "completeness_score": 30,
          "verification_status": "PENDING",
          "photos": <dynamic>[],
        },
        "sensitive_data": null,
        "partner_preferences": null,
      };

      final profile = ProfileModel.fromOwnProfileJson(json);
      expect(profile.id, "profile-123");
      expect(profile.firstName, "Test");
      expect(profile.gender, Gender.male);
      expect(profile.completenessScore, 30);
      expect(profile.verificationStatus, "PENDING");
      expect(profile.photos.length, 0);
      expect(profile.sensitiveData, isNull);
      expect(profile.partnerPreferences, isNull);
    });

    test('should parse full aggregation correctly', () {
      final json = {
        "profile": {
          "id": "profile-123",
          "first_name": "Test",
          "last_name": "User",
          "gender": "FEMALE",
          "disability_type": "VISUAL",
          "completeness_score": 100,
          "verification_status": "APPROVED",
          "photos": [
            {
              "id": "photo-1",
              "profile_id": "profile-123",
              "display_order": 0,
              "is_primary": true,
              "moderation_status": "APPROVED",
              "created_at": "2023-01-01T00:00:00Z",
              "signed_urls": {"medium_url": "https://example.com/medium.jpg"},
            },
          ],
        },
        "sensitive_data": {
          "disability_percentage": 40,
          "disability_since": "BIRTH",
          "contact_phone": "1234567890",
        },
        "partner_preferences": {
          "id": "pref-123",
          "profile_id": "profile-123",
          "age_min": 25,
          "preferred_gender": "MALE",
          "preferred_marital_statuses": ["NEVER_MARRIED", "DIVORCED"],
          "preferred_disability_types": ["VISUAL"],
        },
      };

      final profile = ProfileModel.fromOwnProfileJson(json);

      expect(profile.lastName, "User");
      expect(profile.gender, Gender.female);
      expect(profile.disabilityType, DisabilityType.visual);

      expect(profile.photos.length, 1);
      expect(profile.photos.first.id, "photo-1");
      expect(profile.photos.first.isPrimary, true);
      expect(profile.photos.first.mediumUrl, "https://example.com/medium.jpg");

      expect(profile.sensitiveData, isNotNull);
      expect(profile.sensitiveData!.disabilityPercentage, 40);
      expect(profile.sensitiveData!.contactPhone, "1234567890");

      expect(profile.partnerPreferences, isNotNull);
      expect(profile.partnerPreferences!.ageMin, 25);
      expect(profile.partnerPreferences!.preferredGender, Gender.male);
      expect(profile.partnerPreferences!.preferredMaritalStatuses?.length, 2);
      expect(
        profile.partnerPreferences!.preferredMaritalStatuses?.first,
        MaritalStatus.neverMarried,
      );
      expect(
        profile.partnerPreferences!.preferredDisabilityTypes?.first,
        DisabilityType.visual,
      );
    });
  });
}
