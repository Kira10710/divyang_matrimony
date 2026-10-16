"""
Unit tests for app.core.db_guard.

These tests validate the safety guard's structural URL parsing logic without
connecting to any real database.  They are intentionally isolated from all
other app imports and run cleanly with or without TEST_DATABASE_URL set.

Coverage goals
--------------
assert_safe_test_db_url
  - empty / whitespace-only URL → fail closed
  - malformed URL → fail closed
  - forbidden ENVIRONMENT values → fail closed
  - database name must satisfy strict convention
    (test_, _test, or exactly "test") — not a substring match
  - host must be in the explicit allowlist — no .local bypass
  - valid combinations → pass

assert_safe_clean_db_url
  - confirmed=False → fail
  - env != "development" → fail
  - ENVIRONMENT env-var is forbidden → fail
  - non-local host → fail
  - non-test-named database → fail
  - valid (local host + test-named db + confirmed + dev env) → pass
"""

from __future__ import annotations

import pytest

from app.core.db_guard import DatabaseSafetyError, assert_safe_clean_db_url, assert_safe_test_db_url

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TEST_URL = "postgresql+asyncpg://test:test@localhost:5432/test_divyang"
_VALID_CLEAN_URL = "postgresql+asyncpg://test:test@127.0.0.1:5432/test_local"


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove ENVIRONMENT from the process environment so tests start clean."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)


# ===========================================================================
# assert_safe_test_db_url
# ===========================================================================


class TestAssertSafeTestDbUrl:
    # -----------------------------------------------------------------------
    # Fail-closed on missing / malformed input
    # -----------------------------------------------------------------------

    def test_empty_string_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        with pytest.raises(DatabaseSafetyError, match="empty or missing"):
            assert_safe_test_db_url("")

    def test_whitespace_only_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        with pytest.raises(DatabaseSafetyError, match="empty or missing"):
            assert_safe_test_db_url("   ")

    def test_malformed_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        with pytest.raises(DatabaseSafetyError, match="malformed"):
            assert_safe_test_db_url("not_a_url_at_all:::///")

    # -----------------------------------------------------------------------
    # Forbidden ENVIRONMENT values
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("env_val", ["production", "prod", "staging", "PRODUCTION", "STAGING"])
    def test_forbidden_environment_raises(self, monkeypatch: pytest.MonkeyPatch, env_val: str) -> None:
        monkeypatch.setenv("ENVIRONMENT", env_val)
        with pytest.raises(DatabaseSafetyError, match="ENVIRONMENT"):
            assert_safe_test_db_url(_VALID_TEST_URL)

    def test_development_environment_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "development")
        # Should not raise
        assert_safe_test_db_url(_VALID_TEST_URL)

    def test_unset_environment_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        # ENVIRONMENT defaults to "" — not forbidden
        assert_safe_test_db_url(_VALID_TEST_URL)

    # -----------------------------------------------------------------------
    # Database naming convention
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("db_name", ["test_divyang", "divyang_test", "test"])
    def test_valid_test_db_names_pass(self, monkeypatch: pytest.MonkeyPatch, db_name: str) -> None:
        _clean_env(monkeypatch)
        url = f"postgresql+asyncpg://test:test@localhost:5432/{db_name}"
        assert_safe_test_db_url(url)  # must not raise

    @pytest.mark.parametrize(
        "db_name",
        [
            "divyang",  # no "test" at all
            "contest",  # contains "test" as substring but doesn't start/end with it
            "attestation",  # same — substring false positive
            "protein",  # same
            "mytest123",  # "test" in middle, not as prefix/suffix
            "testing",  # starts with "test" but not "test_"
            "testdb",  # starts with "test" but not "test_"
            "production_db",
            "live_db",
        ],
    )
    def test_invalid_db_names_raise(self, monkeypatch: pytest.MonkeyPatch, db_name: str) -> None:
        _clean_env(monkeypatch)
        url = f"postgresql+asyncpg://test:test@localhost:5432/{db_name}"
        with pytest.raises(DatabaseSafetyError, match="naming convention"):
            assert_safe_test_db_url(url)

    def test_no_database_name_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        # URL with no database component
        with pytest.raises(DatabaseSafetyError):
            assert_safe_test_db_url("postgresql+asyncpg://test:test@localhost:5432/")

    # -----------------------------------------------------------------------
    # Host allowlist
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "host",
        ["localhost", "127.0.0.1", "::1", "test-db", "postgres-test", "postgres"],
    )
    def test_allowed_hosts_pass(self, monkeypatch: pytest.MonkeyPatch, host: str) -> None:
        _clean_env(monkeypatch)
        # Use bracket notation for IPv6
        host_part = f"[{host}]" if ":" in host else host
        url = f"postgresql+asyncpg://test:test@{host_part}:5432/test_divyang"
        assert_safe_test_db_url(url)  # must not raise

    @pytest.mark.parametrize(
        "host",
        [
            "db.example.com",
            "internal.company.local",  # .local was the old bypass — must now reject
            "10.0.0.1",
            "192.168.1.100",
            "remote-postgres",
            "staging-db",
            "prod-db",
        ],
    )
    def test_disallowed_hosts_raise(self, monkeypatch: pytest.MonkeyPatch, host: str) -> None:
        _clean_env(monkeypatch)
        url = f"postgresql+asyncpg://test:test@{host}:5432/test_divyang"
        with pytest.raises(DatabaseSafetyError, match="allowlist"):
            assert_safe_test_db_url(url)

    # -----------------------------------------------------------------------
    # Password must NOT affect host/db parsing
    # -----------------------------------------------------------------------

    def test_password_containing_prod_does_not_trigger_host_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A password like 'prod_secret' must not cause a false positive."""
        _clean_env(monkeypatch)
        url = "postgresql+asyncpg://user:prod_secret_password@localhost:5432/test_divyang"
        assert_safe_test_db_url(url)  # must not raise

    def test_password_containing_localhost_does_not_bypass_host_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A password containing 'localhost' on a remote host must still fail."""
        _clean_env(monkeypatch)
        url = "postgresql+asyncpg://user:localhost_pw@remote.db.example.com:5432/test_divyang"
        with pytest.raises(DatabaseSafetyError, match="allowlist"):
            assert_safe_test_db_url(url)


# ===========================================================================
# assert_safe_clean_db_url
# ===========================================================================


class TestAssertSafeCleanDbUrl:
    # -----------------------------------------------------------------------
    # Confirmation gates
    # -----------------------------------------------------------------------

    def test_unconfirmed_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        with pytest.raises(DatabaseSafetyError, match="confirmation"):
            assert_safe_clean_db_url(_VALID_CLEAN_URL, confirmed=False, env="development")

    def test_confirmed_development_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        # Must not raise
        assert_safe_clean_db_url(_VALID_CLEAN_URL, confirmed=True, env="development")

    # -----------------------------------------------------------------------
    # Environment enforcement
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "env_val",
        ["production", "prod", "staging", "ci", "test", "development_extra"],
    )
    def test_non_development_env_raises(self, monkeypatch: pytest.MonkeyPatch, env_val: str) -> None:
        _clean_env(monkeypatch)
        with pytest.raises(DatabaseSafetyError):
            assert_safe_clean_db_url(_VALID_CLEAN_URL, confirmed=True, env=env_val)

    @pytest.mark.parametrize("env_val", ["production", "prod", "staging"])
    def test_forbidden_environment_var_raises(self, monkeypatch: pytest.MonkeyPatch, env_val: str) -> None:
        """ENVIRONMENT env-var check fires even when caller passes env='development'."""
        monkeypatch.setenv("ENVIRONMENT", env_val)
        with pytest.raises(DatabaseSafetyError):
            assert_safe_clean_db_url(_VALID_CLEAN_URL, confirmed=True, env="development")

    # -----------------------------------------------------------------------
    # Host: stricter set than test guard (no CI aliases)
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
    def test_local_hosts_pass(self, monkeypatch: pytest.MonkeyPatch, host: str) -> None:
        _clean_env(monkeypatch)
        host_part = f"[{host}]" if ":" in host else host
        url = f"postgresql+asyncpg://test:test@{host_part}:5432/test_local"
        assert_safe_clean_db_url(url, confirmed=True, env="development")

    @pytest.mark.parametrize(
        "host",
        [
            "postgres",  # allowed for tests but NOT for clean_db
            "test-db",  # same
            "postgres-test",  # same
            "10.0.0.1",
            "remote.example.com",
        ],
    )
    def test_non_local_hosts_raise(self, monkeypatch: pytest.MonkeyPatch, host: str) -> None:
        _clean_env(monkeypatch)
        url = f"postgresql+asyncpg://test:test@{host}:5432/test_local"
        with pytest.raises(DatabaseSafetyError):
            assert_safe_clean_db_url(url, confirmed=True, env="development")

    # -----------------------------------------------------------------------
    # Database naming: same convention as test guard
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("db_name", ["contest", "attestation", "divyang", "live_db"])
    def test_non_test_db_names_raise(self, monkeypatch: pytest.MonkeyPatch, db_name: str) -> None:
        _clean_env(monkeypatch)
        url = f"postgresql+asyncpg://test:test@localhost:5432/{db_name}"
        with pytest.raises(DatabaseSafetyError):
            assert_safe_clean_db_url(url, confirmed=True, env="development")

    # -----------------------------------------------------------------------
    # Empty / malformed
    # -----------------------------------------------------------------------

    def test_empty_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        with pytest.raises(DatabaseSafetyError, match="empty or missing"):
            assert_safe_clean_db_url("", confirmed=True, env="development")
