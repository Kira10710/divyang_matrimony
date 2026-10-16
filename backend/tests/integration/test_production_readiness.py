"""Production-readiness checks: startup validation, proxy/IP handling, anti-enumeration,
refresh-token atomicity, log redaction, health output, image pipeline limits and
container hygiene."""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import structlog
from PIL import Image
from starlette.requests import Request

from app.core import dependencies
from app.core.config import Settings, settings
from app.core.exceptions import BadRequestError
from app.core.logging_config import _redact_sensitive_fields
from app.repositories.session_repository import SessionRepository
from app.services import photo_service as photo_module
from app.services.photo_service import PhotoService

BACKEND = Path(__file__).resolve().parents[2]
PHONE_A = "9876543210"
PHONE_B = "9123456780"


# ---------------------------------------------------------------------------
# Workstream 1: startup validation
# ---------------------------------------------------------------------------


@pytest.fixture
def firebase_file(tmp_path: Path) -> str:
    path = tmp_path / "firebase.json"
    path.write_text("{}")
    return str(path)


def _settings(firebase_file: str, **overrides) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+asyncpg://app:Zk3pQ9vL2xRt@db.internal:5432/divyang",
        "REDIS_URL": "rediss://default:Hq8sLw2mZc@cache.internal:6380/0",
        "JWT_SECRET_KEY": "Xk3-9Qw8Lp2Zr7Vb1Nm6Td4Gs0Hj5Fy8Cu3Ae9Rk2Mb7",
        "FIELD_ENCRYPTION_KEY": "9f3a6c1e8b2d47f05a6c9e1d3b7f2a84c0e5d1b9a7f3c6e2d8b4a1f09c5e7d3b",
        "FIREBASE_CREDENTIALS_PATH": firebase_file,
        "FIREBASE_STORAGE_BUCKET": "divyang-prod.appspot.com",
        "RAZORPAY_KEY_ID": "rzp_live_x",
        "RAZORPAY_KEY_SECRET": "k",
        "RAZORPAY_WEBHOOK_SECRET": "w",
        "CORS_ORIGINS": ["https://app.example-matrimony.in"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class TestStartupValidation:
    def test_a_well_configured_production_instance_starts(self, firebase_file) -> None:
        assert _settings(firebase_file).ENVIRONMENT == "production"

    def test_development_is_not_blocked_by_production_rules(self, firebase_file) -> None:
        loose = _settings(
            firebase_file, ENVIRONMENT="development", JWT_SECRET_KEY="short", FIELD_ENCRYPTION_KEY="0" * 64
        )
        assert loose.ENVIRONMENT == "development"

    @pytest.mark.parametrize(
        ("override", "fragment"),
        [
            ({"JWT_SECRET_KEY": "short"}, "JWT_SECRET_KEY"),
            ({"JWT_SECRET_KEY": "please-change-me-" + "x9Z" * 10}, "placeholder"),
            ({"JWT_ALGORITHM": "none"}, "JWT_ALGORITHM"),
            ({"FIELD_ENCRYPTION_KEY": "0" * 64}, "FIELD_ENCRYPTION_KEY"),
            ({"FIELD_ENCRYPTION_KEY": "abc"}, "FIELD_ENCRYPTION_KEY"),
            ({"CORS_ORIGINS": ["*"]}, "CORS_ORIGINS"),
            ({"CORS_ORIGINS": ["http://app.example.com"]}, "CORS_ORIGINS"),
            ({"DATABASE_URL": "postgresql+asyncpg://divyang:devpassword@db/x"}, "development/test credential"),
            ({"DATABASE_URL": "sqlite:///x.db"}, "DATABASE_URL"),
            ({"FIREBASE_CREDENTIALS_PATH": "/nonexistent/firebase.json"}, "FIREBASE_CREDENTIALS_PATH"),
            ({"FIREBASE_STORAGE_BUCKET": " "}, "FIREBASE_STORAGE_BUCKET"),
        ],
    )
    def test_unsafe_production_settings_are_refused(self, firebase_file, override, fragment) -> None:
        with pytest.raises(ValueError, match=fragment):
            _settings(firebase_file, **override)

    def test_cors_and_redis_must_be_explicit_in_production(self, firebase_file) -> None:
        base = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://app:Zk3pQ9vL2xRt@db.internal/divyang",
            "JWT_SECRET_KEY": "Xk3-9Qw8Lp2Zr7Vb1Nm6Td4Gs0Hj5Fy8Cu3Ae9Rk2Mb7",
            "FIELD_ENCRYPTION_KEY": "9f3a6c1e8b2d47f05a6c9e1d3b7f2a84c0e5d1b9a7f3c6e2d8b4a1f09c5e7d3b",
            "FIREBASE_CREDENTIALS_PATH": firebase_file,
            "FIREBASE_STORAGE_BUCKET": "b",
            "RAZORPAY_KEY_ID": "k",
            "RAZORPAY_KEY_SECRET": "k",
            "RAZORPAY_WEBHOOK_SECRET": "k",
        }
        with pytest.raises(ValueError, match="CORS_ORIGINS must be set explicitly"):
            Settings(_env_file=None, **base)

    def test_error_text_never_contains_the_secret_values(self, firebase_file) -> None:
        secret = "tiny-secret-value"
        with pytest.raises(ValueError) as caught:
            _settings(firebase_file, JWT_SECRET_KEY=secret)
        assert secret not in str(caught.value)

    @pytest.mark.parametrize("hops", [-1, 6])
    def test_proxy_hops_are_bounded(self, firebase_file, hops) -> None:
        with pytest.raises(ValueError, match="TRUSTED_PROXY_HOPS"):
            _settings(firebase_file, ENVIRONMENT="development", TRUSTED_PROXY_HOPS=hops)


# ---------------------------------------------------------------------------
# Workstream 2: client IP and abuse cases
# ---------------------------------------------------------------------------


def _request(forwarded: str | None, peer: str = "10.0.0.5") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 5555)})


class TestClientIp:
    def test_forwarded_header_is_ignored_by_default(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
        assert dependencies.resolve_client_ip(_request("1.2.3.4")) == "10.0.0.5"

    def test_one_trusted_hop_uses_the_last_entry_not_a_client_supplied_one(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
        spoofed = _request("6.6.6.6, 203.0.113.9")  # client prepended 6.6.6.6; proxy appended the real peer
        assert dependencies.resolve_client_ip(spoofed) == "203.0.113.9"

    def test_two_trusted_hops_skip_the_inner_proxy(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
        request = _request("6.6.6.6, 203.0.113.9, 172.16.0.2")
        assert dependencies.resolve_client_ip(request) == "203.0.113.9"

    @pytest.mark.parametrize("header", [None, "", "203.0.113.9", "not-an-ip, still-not"])
    def test_missing_short_or_invalid_headers_fall_back_to_the_peer(self, monkeypatch, header) -> None:
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
        assert dependencies.resolve_client_ip(_request(header)) == "10.0.0.5"

    def test_request_context_uses_the_resolved_ip(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
        context = dependencies.get_request_context(_request("198.51.100.7"))
        assert context["ip_address"] == "198.51.100.7"


class TestAntiEnumeration:
    def _codes_after_failures(self, client, phone: str, attempts: int) -> list[tuple[int, str | None]]:
        results = []
        for _ in range(attempts):
            response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"})
            errors = response.json().get("errors") or [{}]
            results.append((response.status_code, errors[0].get("code")))
        return results

    def test_lockout_behaviour_is_identical_for_known_and_unknown_numbers(self, app_client, make_user) -> None:
        asyncio.run(make_user(phone="+91" + PHONE_A))
        known = self._codes_after_failures(app_client, PHONE_A, 8)
        unknown = self._codes_after_failures(app_client, PHONE_B, 8)
        assert known == unknown
        assert any(code == "ACCOUNT_LOCKED" for _, code in known)  # the lockout does trigger

    def test_banned_and_unknown_numbers_get_the_same_send_otp_response(self, app_client, make_user) -> None:
        asyncio.run(make_user(phone="+91" + PHONE_A, is_banned=True))
        banned = app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE_A})
        unknown = app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE_B})
        assert (banned.status_code, banned.json()) == (unknown.status_code, unknown.json())


class TestRefreshAtomicity:
    def test_overlapping_transactions_only_one_refresh_wins_on_postgresql(
        self, db_engine, db_session_factory, make_user, new_jti
    ) -> None:
        """Two transactions that both loaded the session as active and overlap in time.

        PostgreSQL makes the second UPDATE wait for the first row lock, then re-check
        `is_revoked = FALSE`; SQLite cannot overlap transactions this way, so this runs only on PostgreSQL.
        """
        if db_engine.dialect.name != "postgresql":
            pytest.skip("overlapping-transaction semantics need PostgreSQL")
        user = asyncio.run(make_user())

        async def _run() -> list[bool]:
            async with db_session_factory() as setup:
                await SessionRepository(setup).create_session(
                    user_id=user.id,
                    refresh_token_jti=new_jti,
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                    device_info=None,
                    ip_address=None,
                    platform_id=user.platform_id,
                )
                await setup.commit()
            barrier = asyncio.Barrier(2)

            async def _racer() -> bool:
                async with db_session_factory() as db:
                    row = await SessionRepository(db).get_session_by_jti(new_jti)
                    assert row is not None and row.is_revoked is False
                    await barrier.wait()  # both racers now hold the row as "active"
                    won = await SessionRepository(db).revoke_if_active(row)
                    await asyncio.sleep(0.3)  # keep the transaction open so the other one must wait on the lock
                    await db.commit()
                    return won

            return list(await asyncio.gather(_racer(), _racer()))

        assert sorted(asyncio.run(_run())) == [False, True]

    def test_only_one_of_two_concurrent_revocations_wins(self, db_session_factory, make_user, new_jti) -> None:
        user = asyncio.run(make_user())

        async def _run() -> tuple[bool, bool]:
            async with db_session_factory() as setup:
                repo = SessionRepository(setup)
                created = await repo.create_session(
                    user_id=user.id,
                    refresh_token_jti=new_jti,
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                    device_info=None,
                    ip_address=None,
                    platform_id=user.platform_id,
                )
                await setup.commit()
            async with db_session_factory() as first, db_session_factory() as second:
                row_one = await SessionRepository(first).get_session_by_jti(new_jti)
                row_two = await SessionRepository(second).get_session_by_jti(new_jti)
                assert row_one.id == row_two.id == created.id
                won_first = await SessionRepository(first).revoke_if_active(row_one)
                await first.commit()
                won_second = await SessionRepository(second).revoke_if_active(row_two)
                await second.commit()
                return won_first, won_second

        assert asyncio.run(_run()) == (True, False)


# ---------------------------------------------------------------------------
# Admin provisioning script guards (scripts/create_admin.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def create_admin_script():
    import importlib.util

    spec = importlib.util.spec_from_file_location("create_admin_script", BACKEND / "scripts" / "create_admin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCreateAdminScript:
    def test_platform_and_valid_role_are_mandatory_arguments(self, create_admin_script) -> None:
        with pytest.raises(SystemExit):
            create_admin_script._parse_args(["--email", "a@b.com", "--role", "ADMIN"])  # no --platform
        with pytest.raises(SystemExit):
            create_admin_script._parse_args(["--email", "a@b.com", "--role", "OWNER", "--platform", "p"])

    def test_super_admin_needs_both_the_flag_and_the_environment_opt_in(self, create_admin_script, monkeypatch) -> None:
        monkeypatch.delenv("ALLOW_SUPER_ADMIN_PROVISIONING", raising=False)
        with pytest.raises(SystemExit):
            create_admin_script._check_super_admin_authorization("SUPER_ADMIN", True)  # env missing
        monkeypatch.setenv("ALLOW_SUPER_ADMIN_PROVISIONING", "yes")
        with pytest.raises(SystemExit):
            create_admin_script._check_super_admin_authorization("SUPER_ADMIN", False)  # flag missing
        assert create_admin_script._check_super_admin_authorization("SUPER_ADMIN", True) is True
        assert create_admin_script._check_super_admin_authorization("ADMIN", False) is False

    def test_wrong_database_name_aborts_before_any_write(self, create_admin_script, monkeypatch, capsys) -> None:
        url = "postgresql+asyncpg://user:pw-SENTINEL@db.example:5432/divyang"
        monkeypatch.setattr("builtins.input", lambda _prompt="": "something_else")
        with pytest.raises(SystemExit):
            create_admin_script._confirm_target_database(url)
        monkeypatch.setattr("builtins.input", lambda _prompt="": "divyang")
        create_admin_script._confirm_target_database(url)  # matching name proceeds
        assert "pw-SENTINEL" not in capsys.readouterr().out  # credentials are never printed

    def test_super_admin_refusal_happens_before_the_database_is_touched(self, create_admin_script, monkeypatch) -> None:
        monkeypatch.delenv("ALLOW_SUPER_ADMIN_PROVISIONING", raising=False)

        def _boom(*_a, **_k):
            raise AssertionError("database work started")

        monkeypatch.setattr(create_admin_script.asyncio, "run", _boom)
        monkeypatch.setattr("builtins.input", _boom)
        with pytest.raises(SystemExit):
            create_admin_script.main(
                ["--email", "a@b.com", "--role", "SUPER_ADMIN", "--platform", "p", "--allow-super-admin"]
            )


# ---------------------------------------------------------------------------
# Workstream 1: logs, errors, health
# ---------------------------------------------------------------------------


class TestLogRedaction:
    def test_sensitive_keys_are_redacted_including_compound_names(self) -> None:
        event = {
            "event": "x",
            "phone": "+919876543210",
            "email": "a@b.com",
            "Authorization": "Bearer abc",
            "jwt_secret_key": "s",
            "refresh_token_jti": "jti",
            "password_hash": "h",
            "user_id": "keep-me",
        }
        out = _redact_sensitive_fields(None, "info", dict(event))
        for key in ("phone", "email", "Authorization", "jwt_secret_key", "refresh_token_jti", "password_hash"):
            assert out[key] == "[REDACTED]", key
        assert out["user_id"] == "keep-me"


class TestErrorAndHealthOutput:
    def _call_unhandled(self, app_client, message: str):
        handler = app_client.app.exception_handlers[Exception]
        request = _request(None)
        request.scope["path"] = "/api/v1/profiles/me"
        return asyncio.run(handler(request, RuntimeError(message)))

    def test_unhandled_errors_are_generic_and_the_message_is_not_logged_in_production(
        self, app_client, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        pii = "Key (phone)=(+919876543210) already exists"
        with structlog.testing.capture_logs() as logs:
            response = self._call_unhandled(app_client, pii)
        assert response.status_code == 500
        assert pii not in response.body.decode()
        assert pii not in repr(logs)
        assert logs[0]["exc_type"] == "RuntimeError"

    def test_health_endpoints_expose_no_configuration(self, app_client) -> None:
        for path in ("/health", "/api/v1/health"):
            response = app_client.get(path)
            assert response.status_code == 200
            text = response.text.lower()
            for forbidden in ("database", "redis", "secret", "key", "password", "version", "environment"):
                assert forbidden not in text, (path, forbidden)

    @pytest.mark.parametrize("environment", ["production", "staging"])
    def test_api_docs_and_schema_are_not_public_outside_development(self, monkeypatch, environment) -> None:
        from fastapi.testclient import TestClient

        from app.main import create_app

        monkeypatch.setattr(settings, "ENVIRONMENT", environment)
        client = TestClient(create_app())
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404, path

    def test_api_docs_are_available_in_development(self, monkeypatch) -> None:
        from fastapi.testclient import TestClient

        from app.main import create_app

        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        assert TestClient(create_app()).get("/openapi.json").status_code == 200


# ---------------------------------------------------------------------------
# Workstream 3: image pipeline
# ---------------------------------------------------------------------------


class FakeBlob:
    def __init__(self, bucket: FakeBucket, name: str) -> None:
        self.bucket, self.name = bucket, name

    @property
    def data(self) -> bytes | None:
        return self.bucket.objects.get(self.name)

    @property
    def size(self) -> int | None:
        return None if self.data is None else len(self.data)

    def exists(self) -> bool:
        return self.name in self.bucket.objects

    def reload(self) -> None:
        return None

    def download_as_bytes(self, **_kw) -> bytes:
        return self.bucket.objects[self.name]

    def upload_from_string(self, data: bytes, content_type: str | None = None) -> None:
        self.bucket.objects[self.name] = data
        self.bucket.content_types[self.name] = content_type
        if self.bucket.fail_upload_for and self.bucket.fail_upload_for in self.name:
            raise RuntimeError("upload failed")

    def delete(self) -> None:
        self.bucket.objects.pop(self.name, None)

    def generate_signed_url(self, **_kw) -> str:
        return f"https://signed.example/{self.name}"


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str | None] = {}
        self.fail_upload_for: str | None = None

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self, name)


def _jpeg_with_gps(size=(32, 16)) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "Maker"
    exif[0x0112] = 6
    exif.get_ifd(0x8825)[2] = (1.0, 2.0, 3.0)
    out = io.BytesIO()
    Image.new("RGB", size, (1, 2, 3)).save(out, "JPEG", exif=exif)
    return out.getvalue()


def _service(bucket: FakeBucket, repo=None) -> PhotoService:
    return PhotoService(
        photo_repo=repo or MagicMock(),
        bucket_factory=lambda: bucket,
        gcs_credentials_factory=lambda: MagicMock(),
    )


PROFILE = "11111111-1111-1111-1111-111111111111"


def _upload_all(bucket: FakeBucket, payloads: dict[str, bytes]) -> tuple[str, str, str]:
    paths = tuple(f"profiles/{PROFILE}/u_{name}.jpg" for name in ("original", "medium", "thumbnail"))
    for path, name in zip(paths, ("original", "medium", "thumbnail"), strict=True):
        bucket.objects[path] = payloads[name]
    return paths


class TestImagePipeline:
    def _verify(self, service: PhotoService, paths):
        import uuid

        return service._verify_and_clean_variants(uuid.UUID(PROFILE), paths, "key")

    def test_all_three_variants_are_cleaned_and_moved_to_server_owned_paths(self) -> None:
        bucket = FakeBucket()
        payload = _jpeg_with_gps()
        paths = _upload_all(bucket, {"original": payload, "medium": payload, "thumbnail": payload})

        finals = self._verify(_service(bucket), paths)

        assert set(bucket.objects) == set(finals)  # uploads are gone, only clean copies remain
        for final in finals:
            assert final.startswith(f"profiles/{PROFILE}/clean/")
            image = Image.open(io.BytesIO(bucket.objects[final]))
            assert len(image.getexif()) == 0
            assert image.size == (16, 32)  # orientation applied to pixels
        assert set(bucket.content_types.values()) == {"image/jpeg"}

    def test_failure_on_the_last_variant_leaves_nothing_behind(self) -> None:
        bucket = FakeBucket()
        good = _jpeg_with_gps()
        paths = _upload_all(bucket, {"original": good, "medium": good, "thumbnail": b"\xff\xd8\xff\xe0 broken"})

        with pytest.raises(BadRequestError):
            self._verify(_service(bucket), paths)

        assert bucket.objects == {}

    def test_storage_write_failure_cleans_up_created_and_uploaded_objects(self) -> None:
        bucket = FakeBucket()
        good = _jpeg_with_gps()
        paths = _upload_all(bucket, {"original": good, "medium": good, "thumbnail": good})
        bucket.fail_upload_for = "_thumbnail"

        with pytest.raises(BadRequestError, match="Could not verify"):
            self._verify(_service(bucket), paths)

        assert bucket.objects == {}

    @pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
    def test_unsupported_formats_are_rejected(self, fmt: str) -> None:
        out = io.BytesIO()
        Image.new("RGB", (4, 4)).save(out, fmt)
        bucket = FakeBucket()
        paths = _upload_all(bucket, {"original": out.getvalue(), "medium": out.getvalue(), "thumbnail": out.getvalue()})
        with pytest.raises(BadRequestError):
            self._verify(_service(bucket), paths)
        assert bucket.objects == {}

    @pytest.mark.parametrize(("size", "message"), [((5000, 5000), "too many pixels"), ((20000, 20000), "not a valid")])
    def test_a_small_file_declaring_a_huge_canvas_is_rejected_without_decoding(self, size, message) -> None:
        out = io.BytesIO()
        Image.new("1", size).save(out, "PNG")  # a few KB on disk, tens or hundreds of MP when decoded
        assert len(out.getvalue()) < 1_000_000
        with pytest.raises(BadRequestError, match=message):
            PhotoService._strip_metadata(out.getvalue(), "p")

    def test_truncated_jpeg_is_rejected(self) -> None:
        with pytest.raises(BadRequestError):
            PhotoService._strip_metadata(_jpeg_with_gps()[:60], "p")

    def test_server_owned_clean_objects_cannot_be_registered_as_uploads(self) -> None:
        """Registering an existing published object as an "upload" must not delete it."""
        bucket = FakeBucket()
        good = _jpeg_with_gps()
        published = f"profiles/{PROFILE}/clean/oldkey_original.jpg"
        bucket.objects[published] = good
        uploads = _upload_all(bucket, {"original": good, "medium": good, "thumbnail": good})
        with pytest.raises(BadRequestError, match="Invalid storage path"):
            self._verify(_service(bucket), (published, uploads[1], uploads[2]))
        assert published in bucket.objects  # the live photo's file is untouched

    def test_files_outside_the_profile_folder_are_never_touched(self) -> None:
        bucket = FakeBucket()
        other = "profiles/22222222-2222-2222-2222-222222222222/victim.jpg"
        bucket.objects[other] = _jpeg_with_gps()
        paths = (other, other, other)
        with pytest.raises(BadRequestError, match="Invalid storage path"):
            self._verify(_service(bucket), paths)
        assert other in bucket.objects  # the other profile's object was not deleted

    def test_processing_concurrency_is_bounded_by_configuration(self, monkeypatch) -> None:
        monkeypatch.setattr(photo_module, "_image_executor", None)
        monkeypatch.setattr(settings, "PHOTO_PROCESSING_CONCURRENCY", 1)
        executor = photo_module._get_image_executor()
        assert executor._max_workers == 1
        executor.shutdown(wait=False)
        monkeypatch.setattr(photo_module, "_image_executor", None)


# ---------------------------------------------------------------------------
# Workstream 6/7: container and CI hygiene
# ---------------------------------------------------------------------------


class TestDeploymentFiles:
    def test_dockerignore_keeps_secrets_out_of_the_image(self) -> None:
        lines = (BACKEND / ".dockerignore").read_text().splitlines()
        # Docker matches bare patterns against the context root only (verified empirically with
        # `docker build`), so secrets must be excluded with "**/" to cover nested folders too.
        for pattern in ("**/.env", "**/.env.*", "**/*.json", "**/*.pem", "**/__pycache__", "**/.venv"):
            assert pattern in lines, pattern
        assert "*.json" not in lines and ".env" not in lines  # root-only forms give false comfort

    def test_dockerfile_runs_as_non_root_with_an_honest_healthcheck(self) -> None:
        text = (BACKEND / "Dockerfile").read_text()
        assert "USER appuser" in text
        assert "status_code == 200" in text
        assert "--no-proxy-headers" in text

    def test_ci_requires_postgres_for_the_integration_suite(self) -> None:
        workflow = (BACKEND.parent / ".github" / "workflows" / "ci.yml").read_text()
        assert "TEST_DATABASE_URL" in workflow
        assert 'REQUIRE_POSTGRES_TESTS: "1"' in workflow

    def test_compose_does_not_publish_postgres_on_all_interfaces(self) -> None:
        compose = (BACKEND / "docker-compose.yml").read_text()
        assert '"127.0.0.1:5432:5432"' in compose
