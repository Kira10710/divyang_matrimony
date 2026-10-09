"""
Test-data builders for the `profiles` and related tables.

Same dict-factory pattern as user_factory.py — builds plain dicts of
constructor kwargs, not ORM instances. Persistence goes through repositories.
"""
from __future__ import annotations

from datetime import date

import factory

from app.models.enums import (
    GenderEnum,
    MaritalStatusEnum,
    ProfileManagedByEnum,
)


class ProfileFactory(factory.Factory):
    """A minimal valid profile for Divyang Matrimony (disability required)."""

    class Meta:
        model = dict

    platform_id = "divyang_matrimony"
    managed_by = ProfileManagedByEnum.SELF
    first_name = factory.Faker("first_name", locale="en_IN")
    last_name = factory.Faker("last_name", locale="en_IN")
    gender = GenderEnum.MALE
    date_of_birth = date(1995, 6, 15)
    marital_status = MaritalStatusEnum.NEVER_MARRIED
    disability_type = "PHYSICAL"
    country = "India"


class SensitiveDataFactory(factory.Factory):
    """Sensitive profile data (plaintext — not yet encrypted)."""

    class Meta:
        model = dict

    religion = "Hindu"
    caste = "General"
    family_type = "Nuclear"
    family_status = "Middle"
    disability_percentage = 60
    disability_since = "Birth"
    mobility_aid = "Wheelchair"
    contact_phone = "+919876543210"
    whatsapp_number = "+919876543210"


class PartnerPreferenceFactory(factory.Factory):
    """Partner preferences with sensible defaults."""

    class Meta:
        model = dict

    preferred_gender = GenderEnum.FEMALE
    age_min = 21
    age_max = 30
    preferred_religion = "Hindu"
    religion_is_strict = False
