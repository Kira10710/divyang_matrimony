"""
Test-data builders for the `users` table.

These build plain `dict`s of constructor kwargs, not ORM instances — the
app's persistence layer is fully async, and factory_boy's built-in
SQLAlchemy integration (`SQLAlchemyModelFactory`) assumes a synchronous
`Session`. Actual persistence goes through `UserRepository.create()` (see
the `make_user`/`make_admin` fixtures in `tests/conftest.py`), so tests
exercise the same create path production code does.
"""
from __future__ import annotations

import itertools

import factory

# 10-digit numbers starting with 6 stay within the app's Indian-mobile
# validator (`^(\+91)?[6-9]\d{9}$`, backend/app/schemas/auth.py) and are
# monotonically unique for the life of the test process.
_phone_sequence = itertools.count(6_000_000_000)


def _next_phone() -> str:
    return f"+91{next(_phone_sequence)}"


class UserFactory(factory.Factory):
    """A regular, phone-verified end user (Architecture §4.1: OTP-only,
    no password)."""

    class Meta:
        model = dict

    phone = factory.LazyFunction(_next_phone)
    platform_id = "divyang_matrimony"
    is_phone_verified = True
    is_active = True
    is_banned = False


class AdminUserFactory(factory.Factory):
    """An admin account — email + password, no phone (Architecture §7.8:
    admins are issued credentials, never self-registering OTP users)."""

    class Meta:
        model = dict

    email = factory.Sequence(lambda n: f"admin{n}@divyangmatrimony.com")
    platform_id = "divyang_matrimony"
    is_phone_verified = False
    is_email_verified = True
    is_active = True
    is_banned = False
