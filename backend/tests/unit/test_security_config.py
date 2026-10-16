from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.otp_service import ConsoleOtpService, RedisOtpService


class TestSecurityConfig:
    """Regression tests for critical production configuration security."""

    def test_missing_environment_fails_safely(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing ENVIRONMENT should raise a validation error instead of defaulting."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with pytest.raises(ValidationError) as exc:
            Settings(_env_file=None)
        assert "ENVIRONMENT" in str(exc.value)
        assert "Field required" in str(exc.value)

    def test_invalid_environment_fails_safely(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid ENVIRONMENT should be rejected by Literal validation."""
        monkeypatch.setenv("ENVIRONMENT", "testing")
        with pytest.raises(ValidationError) as exc:
            Settings(_env_file=None)
        assert "ENVIRONMENT" in str(exc.value)

    @pytest.mark.asyncio
    async def test_production_rejects_console_otp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Production environment should never select ConsoleOtpService."""
        import app.core.dependencies as deps

        monkeypatch.setattr(deps.settings, "ENVIRONMENT", "production")
        mock_redis = MagicMock()
        service = await deps.get_otp_service(mock_redis)

        assert isinstance(service, RedisOtpService)
        assert not isinstance(service, ConsoleOtpService)

    def test_console_otp_raises_error_outside_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ConsoleOtpService should fail to instantiate in production/staging."""
        import app.services.otp_service as otp_svc

        monkeypatch.setattr(otp_svc.settings, "ENVIRONMENT", "production")
        with pytest.raises(RuntimeError, match="CRITICAL SECURITY ERROR"):
            ConsoleOtpService()
