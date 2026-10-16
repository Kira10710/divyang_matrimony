"""Tests for scripts/ci_quality.py: the lint/format ratchets, the no-skips report check and the audit policy.

The ratchet tests run the REAL ruff against a throwaway project, so they prove that new violations
(import order, line length, duplicated lines) are caught and that harmless changes (line shifts, CRLF
checkouts, fixing legacy debt) behave as documented.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci_quality.py"
_spec = importlib.util.spec_from_file_location("ci_quality", SCRIPT)
ci = importlib.util.module_from_spec(_spec)
sys.modules["ci_quality"] = ci  # dataclasses resolve string annotations through sys.modules
_spec.loader.exec_module(ci)

PYPROJECT = '[tool.ruff]\nline-length = 100\n[tool.ruff.lint]\nselect = ["E", "I"]\n'
CLEAN = "import os\nimport sys\n\nprint(os.name, sys.platform)\n"
LONG = "x = " + "'" + "a" * 120 + "'\n"  # E501 at line-length 100


def project(tmp_path: Path, files: dict[str, str]) -> Path:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    for name, text in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="")
    return tmp_path


def write_baseline(root: Path) -> None:
    assert ci.main(["lint", "--update"], root=root) == 0
    assert ci.main(["format", "--update"], root=root) == 0


# ---------------------------------------------------------------------------
# Lint ratchet
# ---------------------------------------------------------------------------


class TestLintRatchet:
    def test_unchanged_code_passes(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": LONG, "ok.py": CLEAN})
        write_baseline(root)
        assert ci.main(["lint"], root=root) == 0

    def test_new_unsorted_imports_fail(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"ok.py": CLEAN})
        write_baseline(root)
        (root / "new_module.py").write_text("import sys\nimport os\n\nprint(os, sys)\n", encoding="utf-8")
        assert ci.main(["lint"], root=root) == 1

    def test_new_long_line_in_a_clean_file_fails(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"ok.py": CLEAN})
        write_baseline(root)
        (root / "ok.py").write_text(CLEAN + LONG.replace("a", "b"), encoding="utf-8")
        assert ci.main(["lint"], root=root) == 1

    def test_a_second_violation_in_a_file_that_already_has_one_still_fails(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": LONG})
        write_baseline(root)
        (root / "legacy.py").write_text(LONG + LONG.replace("a", "c"), encoding="utf-8")
        assert ci.main(["lint"], root=root) == 1

    def test_copying_an_existing_violating_line_fails(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": LONG})
        write_baseline(root)
        (root / "legacy.py").write_text(LONG + LONG, encoding="utf-8")  # identical text, one more occurrence
        assert ci.main(["lint"], root=root) == 1

    def test_editing_a_violating_line_counts_as_new_so_touched_code_gets_fixed(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": LONG})
        write_baseline(root)
        (root / "legacy.py").write_text(LONG.replace("a", "z", 1), encoding="utf-8")
        assert ci.main(["lint"], root=root) == 1

    def test_line_shifts_and_crlf_checkouts_do_not_count_as_new(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": LONG})
        write_baseline(root)
        shifted = "# a new comment\n\n" + LONG
        (root / "legacy.py").write_bytes(shifted.replace("\n", "\r\n").encode())
        assert ci.main(["lint"], root=root) == 0

    def test_fixing_legacy_debt_requires_updating_the_baseline_so_it_cannot_come_back(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": LONG})
        write_baseline(root)
        (root / "legacy.py").write_text("x = 1\n", encoding="utf-8")  # violation fixed
        assert ci.main(["lint"], root=root) == 1  # stale baseline entry is a failure by default
        assert ci.main(["lint", "--allow-stale"], root=root) == 0  # local convenience only
        assert ci.main(["lint", "--update"], root=root) == 0
        assert ci.main(["lint"], root=root) == 0
        baseline = json.loads((root / ci.LINT_BASELINE).read_text(encoding="utf-8"))
        assert baseline["violations"] == []
        (root / "legacy.py").write_text(LONG, encoding="utf-8")  # re-introducing it now fails
        assert ci.main(["lint"], root=root) == 1

    def test_missing_baseline_is_a_tooling_error_not_a_pass(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"ok.py": CLEAN})
        assert ci.main(["lint"], root=root) == 2

    def test_syntax_errors_are_reported_not_hidden(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"ok.py": CLEAN})
        write_baseline(root)
        (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
        assert ci.main(["lint"], root=root) == 1


# ---------------------------------------------------------------------------
# Format ratchet
# ---------------------------------------------------------------------------


class TestFormatRatchet:
    UNFORMATTED = "x   =  1\n"

    def test_legacy_unformatted_files_pass_but_new_ones_fail(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": self.UNFORMATTED, "ok.py": CLEAN})
        write_baseline(root)
        assert ci.main(["format"], root=root) == 0
        (root / "new.py").write_text(self.UNFORMATTED, encoding="utf-8")
        assert ci.main(["format"], root=root) == 1

    def test_a_formatted_file_that_regresses_fails(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"ok.py": CLEAN})
        write_baseline(root)
        (root / "ok.py").write_text(CLEAN + self.UNFORMATTED, encoding="utf-8")
        assert ci.main(["format"], root=root) == 1

    def test_formatting_a_legacy_file_requires_removing_it_from_the_baseline(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"legacy.py": self.UNFORMATTED})
        write_baseline(root)
        (root / "legacy.py").write_text("x = 1\n", encoding="utf-8")
        assert ci.main(["format"], root=root) == 1
        assert ci.main(["format", "--update"], root=root) == 0
        assert ci.main(["format"], root=root) == 0
        assert "legacy.py" not in ci.read_format_baseline(root / ci.FORMAT_BASELINE)

    def test_crlf_files_are_judged_by_their_content_not_their_line_endings(self, tmp_path: Path) -> None:
        root = project(tmp_path, {"ok.py": CLEAN})
        (root / "ok.py").write_bytes(CLEAN.replace("\n", "\r\n").encode())
        write_baseline(root)
        assert ci.read_format_baseline(root / ci.FORMAT_BASELINE) == set()
        assert ci.main(["format"], root=root) == 0

    def test_virtualenv_and_cache_directories_are_not_scanned(self, tmp_path: Path) -> None:
        root = project(
            tmp_path, {"ok.py": CLEAN, ".venv/lib/x.py": self.UNFORMATTED, "__pycache__/y.py": self.UNFORMATTED}
        )
        write_baseline(root)
        assert ci.read_format_baseline(root / ci.FORMAT_BASELINE) == set()


# ---------------------------------------------------------------------------
# Test report: no silent skips
# ---------------------------------------------------------------------------


def junit(tmp_path: Path, *, tests: int, skipped: int = 0, failures: int = 0, errors: int = 0) -> Path:
    cases = "".join(
        f'<testcase classname="t.A" name="skipme{i}"><skipped message="x"/></testcase>' for i in range(skipped)
    )
    xml = (
        f'<testsuites><testsuite name="pytest" tests="{tests}" skipped="{skipped}" failures="{failures}" '
        f'errors="{errors}">{cases}</testsuite></testsuites>'
    )
    path = tmp_path / "report.xml"
    path.write_text(xml, encoding="utf-8")
    return path


class TestJunitCheck:
    def test_clean_report_passes(self, tmp_path: Path) -> None:
        assert ci.main(["junit", str(junit(tmp_path, tests=449))]) == 0

    def test_any_skipped_test_fails_and_names_it(self, tmp_path: Path, capsys) -> None:
        assert ci.main(["junit", str(junit(tmp_path, tests=449, skipped=1))]) == 1
        assert "skipme0" in capsys.readouterr().out

    def test_empty_report_fails(self, tmp_path: Path) -> None:
        assert ci.main(["junit", str(junit(tmp_path, tests=0))]) == 1

    def test_failures_and_errors_fail(self, tmp_path: Path) -> None:
        assert ci.main(["junit", str(junit(tmp_path, tests=10, failures=1))]) == 1
        assert ci.main(["junit", str(junit(tmp_path, tests=10, errors=1))]) == 1

    def test_missing_or_corrupt_report_is_a_tooling_error(self, tmp_path: Path) -> None:
        assert ci.main(["junit", str(tmp_path / "nope.xml")]) == 2
        bad = tmp_path / "bad.xml"
        bad.write_text("<not-xml", encoding="utf-8")
        assert ci.main(["junit", str(bad)]) == 2


# ---------------------------------------------------------------------------
# Dependency audit: ignore-list policy and fail-closed execution
# ---------------------------------------------------------------------------

TODAY = dt.date(2026, 10, 17)
REASON = "only reachable through an optional parser this service never calls"
FREEZE_OK = (
    "\n".join(["fastapi==0.115.0", "SQLAlchemy==2.0.36", "pydantic==2.10.0", *[f"pkg{i}==1.{i}" for i in range(10)]])
    + "\n"
)


def entry(vuln_id: str = "GHSA-aaaa-bbbb-cccc", expires: str = "2026-12-01", reason: str = REASON) -> str:
    return f"{vuln_id} expires={expires} {reason}\n"


class TestIgnoreEntries:
    def test_a_complete_entry_becomes_an_ignore_flag(self) -> None:
        ids, problems = ci.parse_audit_ignores("# comment\n\n" + entry(), TODAY)
        assert (ids, problems) == (["GHSA-aaaa-bbbb-cccc"], [])
        cmd = ci.audit_command(ids, "reqs.txt")
        assert cmd[-2:] == ["--ignore-vuln", "GHSA-aaaa-bbbb-cccc"]

    @pytest.mark.parametrize(
        "line",
        [
            "GHSA-aaaa-bbbb-cccc",  # no expiry or reason
            "GHSA-aaaa-bbbb-cccc expires=2026-12-01",  # no reason
            f"GHSA-aaaa-bbbb-cccc 2026-12-01 {REASON}",  # missing `expires=`
            f"GHSA-aaaa-bbbb-cccc expires=soon {REASON}",  # bad date
            f"GHSA-aaaa-bbbb-cccc expires=2026-13-45 {REASON}",  # impossible date
            "GHSA-aaaa-bbbb-cccc expires=2026-12-01 fine",  # reason too short to be specific
            f"--exclude expires=2026-12-01 {REASON}",  # would be parsed as an option by pip-audit
            f"-x expires=2026-12-01 {REASON}",
            f"ab expires=2026-12-01 {REASON}",  # too short to be an advisory id
            f"GHSA!aaaa expires=2026-12-01 {REASON}",  # illegal character
        ],
    )
    def test_malformed_entries_are_rejected(self, line: str) -> None:
        ids, problems = ci.parse_audit_ignores(line, TODAY)
        assert ids == [] and len(problems) == 1

    def test_expired_entries_are_rejected_but_today_is_still_valid(self) -> None:
        assert ci.parse_audit_ignores(entry(expires="2026-10-16"), TODAY)[1]  # yesterday
        ids, problems = ci.parse_audit_ignores(entry(expires="2026-10-17"), TODAY)  # today
        assert (ids, problems) == (["GHSA-aaaa-bbbb-cccc"], [])

    def test_the_maximum_lifetime_is_exactly_120_days(self) -> None:
        longest = (TODAY + dt.timedelta(days=ci.MAX_IGNORE_DAYS)).isoformat()
        too_long = (TODAY + dt.timedelta(days=ci.MAX_IGNORE_DAYS + 1)).isoformat()
        assert ci.MAX_IGNORE_DAYS == 120
        assert ci.parse_audit_ignores(entry(expires=longest), TODAY)[1] == []
        ids, problems = ci.parse_audit_ignores(entry(expires=too_long), TODAY)
        assert ids == [] and "120 days" in problems[0]

    def test_duplicate_ids_are_rejected_so_one_id_cannot_hold_two_expiries(self) -> None:
        text = entry(expires="2026-11-01") + entry(expires="2026-12-01")
        ids, problems = ci.parse_audit_ignores(text, TODAY)
        assert ids == ["GHSA-aaaa-bbbb-cccc"] and len(problems) == 1

    def test_every_bad_line_is_reported_not_just_the_first(self) -> None:
        text = entry("GHSA-1111-2222-3333", "2020-01-01") + "garbage\n" + entry("GHSA-4444-5555-6666", "2026-12-01")
        ids, problems = ci.parse_audit_ignores(text, TODAY)
        assert ids == ["GHSA-4444-5555-6666"] and len(problems) == 2


class FakeRun:
    """Stand-in for subprocess.run that records calls and replays chosen outcomes."""

    def __init__(self, *, freeze_out=FREEZE_OK, freeze_rc=0, freeze_exc=None, audit_rc=0, audit_exc=None) -> None:
        self.freeze_out, self.freeze_rc, self.freeze_exc = freeze_out, freeze_rc, freeze_exc
        self.audit_rc, self.audit_exc = audit_rc, audit_exc
        self.calls: list[list[str]] = []
        self.requirements_seen: str | None = None

    def __call__(self, cmd, **_kwargs):
        self.calls.append(list(cmd))
        if "freeze" in cmd:
            if self.freeze_exc:
                raise self.freeze_exc
            return SimpleNamespace(returncode=self.freeze_rc, stdout=self.freeze_out, stderr="pip said no")
        if self.audit_exc:
            raise self.audit_exc
        self.requirements_seen = Path(cmd[cmd.index("-r") + 1]).read_text(encoding="utf-8")
        return SimpleNamespace(returncode=self.audit_rc)

    @property
    def audit_calls(self) -> list[list[str]]:
        return [c for c in self.calls if "pip_audit" in c]


@pytest.fixture
def run_audit(tmp_path, monkeypatch):
    """Run `ci_quality.py audit` against a temp root with a fake subprocess; returns (exit_code, fake)."""

    def _run(fake: FakeRun, ignore_text: str = "", argv=("audit",)) -> tuple[int, FakeRun]:
        (tmp_path / ci.AUDIT_IGNORES).write_text(ignore_text, encoding="utf-8")
        monkeypatch.setattr(ci.subprocess, "run", fake)
        return ci.main(list(argv), root=tmp_path), fake

    return _run


class TestAuditFailsClosed:
    def test_success_requires_pip_audit_to_exit_zero_and_uses_strict_pinned_mode(self, run_audit) -> None:
        code, fake = run_audit(FakeRun())
        assert code == 0
        (cmd,) = fake.audit_calls
        assert "--strict" in cmd and "--no-deps" in cmd and "-r" in cmd
        assert "--skip-editable" not in cmd  # would make --strict fail on the editable project
        assert fake.requirements_seen == FREEZE_OK
        freeze = next(c for c in fake.calls if "freeze" in c)
        assert "--exclude-editable" in freeze and "--all" in freeze

    @pytest.mark.parametrize("audit_rc", [1, 2, 3, 127, -9])
    def test_any_non_zero_pip_audit_exit_fails_the_job(self, run_audit, audit_rc) -> None:
        code, _ = run_audit(FakeRun(audit_rc=audit_rc))
        assert code == 1

    def test_pip_audit_that_cannot_be_started_is_a_tooling_error_not_a_pass(self, run_audit) -> None:
        code, _ = run_audit(FakeRun(audit_exc=FileNotFoundError("python")))
        assert code == 2

    def test_pip_freeze_failures_are_tooling_errors(self, run_audit) -> None:
        assert run_audit(FakeRun(freeze_rc=1))[0] == 2
        assert run_audit(FakeRun(freeze_exc=OSError("nope")))[0] == 2

    @pytest.mark.parametrize(
        "freeze_out",
        [
            "",  # nothing installed
            "fastapi==0.115.0\n",  # far too few packages
            "\n".join([f"pkg{i}==1.{i}" for i in range(20)]) + "\n",  # plenty, but the core packages are missing
        ],
    )
    def test_an_empty_or_implausible_package_list_fails_instead_of_auditing_nothing(
        self, run_audit, freeze_out
    ) -> None:
        code, fake = run_audit(FakeRun(freeze_out=freeze_out))
        assert code == 1 and fake.audit_calls == []

    def test_packages_that_are_not_exact_pins_fail_before_auditing(self, run_audit) -> None:
        unpinned = FREEZE_OK + "mystery @ file:///tmp/mystery\n"
        code, fake = run_audit(FakeRun(freeze_out=unpinned))
        assert code == 1 and fake.audit_calls == []

    def test_invalid_ignore_entries_stop_the_audit_before_any_command_runs(self, run_audit) -> None:
        for bad in ("nonsense\n", entry(expires="2020-01-01"), entry(reason="short")):
            code, fake = run_audit(FakeRun(), ignore_text=bad)
            assert code == 1 and fake.calls == []

    def test_a_valid_ignore_is_passed_to_pip_audit(self, run_audit) -> None:
        future = (dt.datetime.now(dt.UTC).date() + dt.timedelta(days=30)).isoformat()
        code, fake = run_audit(FakeRun(), ignore_text=entry(expires=future))
        assert code == 0
        (cmd,) = fake.audit_calls
        assert cmd[cmd.index("--ignore-vuln") + 1] == "GHSA-aaaa-bbbb-cccc"

    def test_dry_run_validates_the_ignore_file_but_runs_nothing(self, run_audit, capsys) -> None:
        code, fake = run_audit(FakeRun(), argv=("audit", "--dry-run"))
        assert code == 0 and fake.calls == []
        assert "--strict" in capsys.readouterr().out
        code, fake = run_audit(FakeRun(), ignore_text="nonsense\n", argv=("audit", "--dry-run"))
        assert code == 1

    def test_the_real_environment_listing_is_accepted_by_the_pin_parser(self) -> None:
        """Executes the real `pip freeze --all --exclude-editable` of the test environment."""
        text, problems = ci.frozen_requirements(SCRIPT.parents[1])
        assert problems == [], problems
        assert "==" in text
