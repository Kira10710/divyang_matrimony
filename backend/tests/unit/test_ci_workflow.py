"""Structural guarantees of .github/workflows/ci.yml.

These assert the pipeline's safety properties, so a later edit cannot quietly reintroduce the failure
modes found in review: lint blocking the PostgreSQL tests, mandatory security checks that may fail
silently, secrets reachable from fork PRs, or a SQLite fallback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")  # pyyaml is a dev dependency; CI installs it

REPO = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO / ".github" / "workflows" / "ci.yml"
ADVISORY_JOBS = {"backend-typecheck"}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML (YAML 1.1) parses the bare key `on` as boolean True.
    return workflow.get("on") or workflow.get(True) or {}


def _step_index(job: dict, needle: str) -> int:
    for index, step in enumerate(job["steps"]):
        if needle in step.get("run", ""):
            return index
    raise AssertionError(f"no step running {needle!r}")


def test_the_workflow_is_valid_and_has_the_expected_jobs(workflow) -> None:
    assert {
        "backend-lint-gate",
        "backend-typecheck",
        "backend-test",
        "backend-dependency-audit",
        "backend-build",
    } <= set(workflow["jobs"])


class TestPostgresJobIsIndependentAndTruthful:
    def test_it_does_not_wait_for_lint_or_anything_else(self, workflow) -> None:
        assert "needs" not in workflow["jobs"]["backend-test"]

    def test_postgres_is_mandatory_and_cannot_fall_back_to_sqlite(self, workflow) -> None:
        job = workflow["jobs"]["backend-test"]
        env = job["env"]
        assert env["REQUIRE_POSTGRES_TESTS"] == "1"
        assert env["TEST_DATABASE_URL"].startswith("postgresql+asyncpg://")
        assert env["TEST_DATABASE_URL"].rsplit("/", 1)[1].startswith("test_")
        assert job["services"]["postgres"]["image"].startswith("postgres:16")
        assert "pg_isready" in job["services"]["postgres"]["options"]

    def test_migrations_run_before_the_suite_and_skips_are_rejected_afterwards(self, workflow) -> None:
        job = workflow["jobs"]["backend-test"]
        install = _step_index(job, "pip install")
        migrate = _step_index(job, "scripts/migrate.py")
        suite = _step_index(job, "pytest --cov")
        no_skips = _step_index(job, "ci_quality.py junit")
        assert install < migrate < suite < no_skips
        assert "--junitxml" in job["steps"][suite]["run"]

    def test_no_step_in_the_test_job_may_fail_silently(self, workflow) -> None:
        job = workflow["jobs"]["backend-test"]
        assert not job.get("continue-on-error")
        assert not any(step.get("continue-on-error") for step in job["steps"])

    def test_test_reports_are_kept_briefly_and_only_from_the_report_files(self, workflow) -> None:
        upload = [s for s in workflow["jobs"]["backend-test"]["steps"] if "upload-artifact" in s.get("uses", "")]
        assert len(upload) == 1
        assert upload[0]["with"]["retention-days"] <= 14
        assert ".env" not in str(upload[0]["with"]["path"])


class TestGatesAreMandatoryExceptTypes:
    def test_only_the_mypy_job_may_continue_on_error(self, workflow) -> None:
        tolerant = {
            name
            for name, job in workflow["jobs"].items()
            if job.get("continue-on-error") or any(step.get("continue-on-error") for step in job["steps"])
        }
        assert tolerant == ADVISORY_JOBS

    def test_dependency_audit_is_a_standalone_mandatory_job(self, workflow) -> None:
        job = workflow["jobs"]["backend-dependency-audit"]
        assert "needs" not in job and not job.get("continue-on-error")
        assert any("ci_quality.py audit" in step.get("run", "") for step in job["steps"])

    def test_lint_gate_runs_both_ratchets(self, workflow) -> None:
        job = workflow["jobs"]["backend-lint-gate"]
        assert _step_index(job, "ci_quality.py lint") >= 0
        assert _step_index(job, "ci_quality.py format") >= 0
        assert not any("ruff check ." in step.get("run", "") for step in job["steps"])  # no bare, always-red check

    def test_the_docker_build_waits_for_every_mandatory_backend_gate(self, workflow) -> None:
        assert set(workflow["jobs"]["backend-build"]["needs"]) == {
            "backend-lint-gate",
            "backend-test",
            "backend-dependency-audit",
        }


class TestUntrustedCodeAndSecrets:
    def test_token_is_read_only_by_default(self, workflow) -> None:
        assert workflow["permissions"] == {"contents": "read"}
        assert not any("permissions" in job for job in workflow["jobs"].values())  # no job widens it

    def test_forks_cannot_reach_secrets(self, workflow) -> None:
        triggers = _triggers(workflow)
        assert set(triggers) == {"push", "pull_request"}  # no pull_request_target / workflow_run
        assert "secrets." not in WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_checkouts_do_not_persist_the_token(self, workflow) -> None:
        for name, job in workflow["jobs"].items():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/checkout"):
                    assert step["with"]["persist-credentials"] is False, name

    def test_every_job_has_a_timeout_and_duplicate_pr_runs_are_cancelled(self, workflow) -> None:
        assert all("timeout-minutes" in job for job in workflow["jobs"].values())
        assert "cancel-in-progress" in workflow["concurrency"]

    def test_publishing_jobs_only_run_on_main_and_never_push_images(self, workflow) -> None:
        build = workflow["jobs"]["backend-build"]
        assert build["if"] == "github.ref == 'refs/heads/main'"
        assert not any("docker push" in step.get("run", "") for step in build["steps"])
