"""
CI quality gates (Architecture §12.1). Standard library only, so it runs before anything else is installed.

The repository carries a large number of pre-existing Ruff violations and unformatted files. Instead of
turning the whole lint step off (or letting it block the PostgreSQL test job), CI uses RATCHETS:

  lint     Every current violation is recorded in `ruff-baseline.json`, keyed by (file, rule, content of
           the offending line) with a count. CI fails when a violation appears that is not in the
           baseline: a new file, a new rule hit, a new copy of the same line, or an edited line that still
           violates. It also fails when the baseline lists violations that no longer exist, so the
           baseline only ever shrinks and a fixed violation cannot be silently re-introduced later.
  format   `ruff-format-baseline.txt` lists files that were not formatted when the ratchet was introduced.
           Every other Python file must be `ruff format` clean. Files leave the list when they are formatted.
  junit    The PostgreSQL job fails if the test report shows zero tests or ANY skipped test. A skip is how a
           SQLite fallback or a missing database would otherwise hide.
  audit    Runs `pip-audit --strict` over the pinned third-party packages of the current environment, so a
           dependency that cannot be audited FAILS the job instead of being skipped. Exceptions need an entry
           in `pip-audit-ignore.txt` (valid ID, reason, expiry within 120 days).

Usage (from backend/):
    python scripts/ci_quality.py lint            # gate
    python scripts/ci_quality.py lint --update   # rewrite the baseline (shrinks it; review the diff)
    python scripts/ci_quality.py format [--update]
    python scripts/ci_quality.py junit test-results.xml
    python scripts/ci_quality.py audit [--dry-run]

Exit codes: 0 = pass, 1 = gate failure, 2 = tooling or usage error.
Line endings are normalised before comparing, so Windows (CRLF) and Linux (LF) checkouts agree.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
LINT_BASELINE = "ruff-baseline.json"
FORMAT_BASELINE = "ruff-format-baseline.txt"
AUDIT_IGNORES = "pip-audit-ignore.txt"
_SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", "build", "dist", "site-packages"}


class ToolError(RuntimeError):
    """The gate could not run (missing tool, unreadable file); distinct from a gate failure."""


# ---------------------------------------------------------------------------
# Ruff helpers
# ---------------------------------------------------------------------------


def _ruff(args: list[str], root: Path, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [sys.executable, "-m", "ruff", *args], cwd=root, input=stdin, capture_output=True, check=False
        )
    except OSError as exc:
        raise ToolError(f"cannot run ruff: {exc}") from exc


def _require_ruff(root: Path) -> None:
    probe = _ruff(["--version"], root)
    if probe.returncode != 0:
        raise ToolError("ruff is not installed (pip install -e '.[dev]')")


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _rel(path: Path | str, root: Path) -> str:
    p = Path(path)
    with contextlib.suppress(ValueError):
        p = p.resolve().relative_to(root.resolve())
    return p.as_posix()


def python_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".") and not d.endswith(".egg-info")
        )
        found.extend(Path(dirpath) / f for f in sorted(filenames) if f.endswith(".py"))
    return found


# ---------------------------------------------------------------------------
# Lint ratchet
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    file: str
    code: str
    line: int
    message: str
    text: str

    @property
    def fingerprint(self) -> tuple[str, str, str]:
        return (self.file, self.code, hashlib.sha1(self.text.strip().encode(), usedforsecurity=False).hexdigest()[:12])


def collect_violations(root: Path) -> list[Violation]:
    _require_ruff(root)
    result = _ruff(["check", ".", "--output-format=json", "--exit-zero", "--no-cache"], root)
    if result.returncode not in (0, 1):
        raise ToolError(f"ruff check failed to run: {result.stderr.decode(errors='replace')[:300]}")
    try:
        items = json.loads(result.stdout or b"[]")
    except json.JSONDecodeError as exc:
        raise ToolError(f"unreadable ruff output: {exc}") from exc
    lines_cache: dict[str, list[str]] = {}
    violations: list[Violation] = []
    for item in items:
        rel = _rel(item["filename"], root)
        if rel not in lines_cache:
            lines_cache[rel] = _norm((root / rel).read_text(encoding="utf-8", errors="replace")).split("\n")
        row = int(item.get("location", {}).get("row") or 1)
        lines = lines_cache[rel]
        text = lines[row - 1] if 0 < row <= len(lines) else ""
        violations.append(Violation(rel, item.get("code") or "SYNTAX", row, item.get("message", ""), text))
    return sorted(violations, key=lambda v: (v.file, v.line, v.code))


def build_lint_baseline(violations: list[Violation]) -> dict:
    counts: Counter[tuple[str, str, str]] = Counter(v.fingerprint for v in violations)
    example: dict[tuple[str, str, str], str] = {}
    for v in violations:
        example.setdefault(v.fingerprint, v.text.strip()[:90])
    return {
        "_policy": (
            "Reviewed record of PRE-EXISTING Ruff violations. CI fails on any violation not listed here and on "
            "entries that no longer occur. Regenerate with `python scripts/ci_quality.py lint --update`; the "
            "diff must only ever remove entries. Never add entries to make a new violation pass."
        ),
        "total": len(violations),
        "violations": [
            {"file": f, "code": c, "line_hash": h, "count": n, "example": example[(f, c, h)]}
            for (f, c, h), n in sorted(counts.items())
        ],
    }


def compare_lint(
    violations: list[Violation], baseline: dict, *, allow_stale: bool = False
) -> tuple[list[str], list[str]]:
    """Return (failures, notes)."""
    allowed: Counter[tuple[str, str, str]] = Counter(
        {(e["file"], e["code"], e["line_hash"]): int(e["count"]) for e in baseline.get("violations", [])}
    )
    seen: Counter[tuple[str, str, str]] = Counter()
    failures: list[str] = []
    for v in violations:
        seen[v.fingerprint] += 1
        if seen[v.fingerprint] > allowed[v.fingerprint]:
            failures.append(f"NEW lint violation: {v.file}:{v.line} {v.code} {v.message}")
    stale = sum((allowed - seen).values())
    notes = [f"{sum(allowed.values())} legacy violations recorded, {len(violations)} found now"]
    if stale:
        message = (
            f"{stale} baseline entries no longer occur; run `python scripts/ci_quality.py lint --update` and commit it"
        )
        (notes if allow_stale else failures).append(message)
    return failures, notes


# ---------------------------------------------------------------------------
# Format ratchet
# ---------------------------------------------------------------------------


def _is_unformatted(root: Path, path: Path) -> bool:
    source = _norm(path.read_text(encoding="utf-8", errors="replace")).encode()
    result = _ruff(["format", "--check", "--stdin-filename", _rel(path, root), "-"], root, stdin=source)
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    raise ToolError(f"ruff format failed for {_rel(path, root)}: {result.stderr.decode(errors='replace')[:200]}")


def unformatted_files(root: Path) -> list[str]:
    _require_ruff(root)
    files = python_files(root)
    with ThreadPoolExecutor(max_workers=8) as pool:
        flags = list(pool.map(lambda p: _is_unformatted(root, p), files))
    return sorted(_rel(p, root) for p, bad in zip(files, flags, strict=True) if bad)


def read_format_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}


def write_format_baseline(path: Path, files: list[str]) -> None:
    header = (
        "# Python files that were NOT `ruff format` clean when the formatting ratchet was introduced.\n"
        "# Every other .py file must be formatted. Remove a file from this list when you format it\n"
        "# (`python scripts/ci_quality.py format --update`). Never add a file to hide new unformatted code.\n"
    )
    path.write_text(header + "".join(f"{f}\n" for f in files), encoding="utf-8", newline="\n")


def compare_format(
    unformatted: list[str], baseline: set[str], *, allow_stale: bool = False
) -> tuple[list[str], list[str]]:
    failures = [f"NOT FORMATTED (run `ruff format {f}`): {f}" for f in unformatted if f not in baseline]
    stale = sorted(baseline - set(unformatted))
    notes = [f"{len(baseline)} legacy unformatted files recorded, {len(unformatted)} found now"]
    if stale:
        message = f"{len(stale)} baseline files are now formatted or gone (e.g. {stale[0]}); run `... format --update`"
        (notes if allow_stale else failures).append(message)
    return failures, notes


# ---------------------------------------------------------------------------
# Test report: no silent skips
# ---------------------------------------------------------------------------


def check_junit(path: Path) -> list[str]:
    try:
        root = ET.parse(path).getroot()  # noqa: S314 - our own pytest output
    except (OSError, ET.ParseError) as exc:
        raise ToolError(f"cannot read test report {path}: {exc}") from exc
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "skipped", "failures", "errors")}
    problems: list[str] = []
    if totals["tests"] == 0:
        problems.append("the report contains no tests")
    if totals["skipped"]:
        skipped = [
            f"{c.get('classname')}::{c.get('name')}" for c in root.iter("testcase") if c.find("skipped") is not None
        ]
        problems.append(f"{totals['skipped']} test(s) were skipped; the PostgreSQL job allows none: {skipped[:5]}")
    if totals["failures"] or totals["errors"]:
        problems.append(f"{totals['failures']} failure(s), {totals['errors']} error(s) in the report")
    return problems


# ---------------------------------------------------------------------------
# Dependency audit with an explicit ignore policy
# ---------------------------------------------------------------------------


MAX_IGNORE_DAYS = 120
MIN_REASON_CHARS = 20
MIN_PACKAGES = 10  # an audit of fewer packages than this means the environment listing is wrong, not clean
_REQUIRED_PACKAGES = ("fastapi==", "sqlalchemy==", "pydantic==")
# Advisory identifiers (GHSA-..., PYSEC-..., CVE-...). Must not start with "-": the value is passed to
# `--ignore-vuln`, and a leading dash could be parsed as another option.
_VULN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
_PINNED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*$")


def parse_audit_ignores(text: str, today: dt.date) -> tuple[list[str], list[str]]:
    """Lines: `VULN-ID  expires=YYYY-MM-DD  reason text`. Returns (ids, problems); any problem fails the audit."""
    ids: list[str] = []
    problems: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[1].startswith("expires="):
            problems.append(f"line {number}: expected `ID expires=YYYY-MM-DD reason`")
            continue
        vuln_id, reason = parts[0], parts[2].strip()
        if not _VULN_ID.match(vuln_id):
            problems.append(f"line {number}: {vuln_id!r} is not a valid advisory id (e.g. GHSA-xxxx-xxxx-xxxx)")
            continue
        if vuln_id in ids:
            problems.append(f"line {number}: {vuln_id} is listed twice; keep one entry with one expiry")
            continue
        try:
            expires = dt.date.fromisoformat(parts[1].removeprefix("expires="))
        except ValueError:
            problems.append(f"line {number}: bad expiry date {parts[1]!r}")
            continue
        if len(reason) < MIN_REASON_CHARS:
            problems.append(f"line {number}: give a specific reason (at least {MIN_REASON_CHARS} characters)")
            continue
        if expires < today:
            problems.append(f"line {number}: ignore for {vuln_id} expired on {expires}; fix or renew with a new reason")
            continue
        if (expires - today).days > MAX_IGNORE_DAYS:
            problems.append(f"line {number}: ignore for {vuln_id} runs more than {MAX_IGNORE_DAYS} days; shorten it")
            continue
        ids.append(vuln_id)
    return ids, problems


def audit_command(ignore_ids: list[str], requirements: Path | str) -> list[str]:
    """The pip-audit invocation.

    `--strict`: any dependency that cannot be collected or audited is fatal (without it pip-audit only warns
    and exits 0). `--no-deps -r <file>`: audit exactly the pinned packages we list, no re-resolution.
    `--skip-editable` is deliberately NOT used: it reports the editable project as a skipped dependency,
    which `--strict` turns into an error; the project itself is simply left out of the list instead.
    """
    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "--strict",
        "--no-deps",
        "-r",
        str(requirements),
        "--progress-spinner",
        "off",
        "--desc",
        "on",
    ]
    for vuln_id in ignore_ids:
        cmd += ["--ignore-vuln", vuln_id]
    return cmd


def frozen_requirements(root: Path) -> tuple[str, list[str]]:
    """Pinned third-party packages of the running environment (the editable project excluded)."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [sys.executable, "-m", "pip", "freeze", "--all", "--exclude-editable"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise ToolError(f"cannot run pip freeze: {exc}") from exc
    if result.returncode != 0:
        raise ToolError(f"pip freeze failed: {result.stderr.strip()[:200]}")
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    problems = [f"not an exact pin, cannot be audited: {ln!r}" for ln in lines if not _PINNED.match(ln)]
    if len(lines) < MIN_PACKAGES or not all(any(ln.lower().startswith(r) for ln in lines) for r in _REQUIRED_PACKAGES):
        problems.append(f"only {len(lines)} packages listed, or core packages are missing; the audit would be vacuous")
    return "\n".join(lines) + "\n", problems


def run_audit(root: Path, ignore_ids: list[str], *, dry_run: bool = False) -> int:
    """0 only if pip-audit itself exits 0. Every other outcome fails (1) or is a tooling error (2)."""
    if dry_run:
        print("[audit] would run:", " ".join(audit_command(ignore_ids, "<pinned requirements>")))
        return 0
    text, problems = frozen_requirements(root)
    if problems:
        return _report("audit", problems, [])
    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "audit-requirements.txt"
        requirements.write_text(text, encoding="utf-8", newline="\n")
        cmd = audit_command(ignore_ids, requirements)
        print("[audit] auditing", len(text.splitlines()), "pinned packages with:", " ".join(cmd[:5]), "...")
        try:
            completed = subprocess.run(cmd, cwd=root, check=False)  # noqa: S603 - fixed argument list, no shell
        except OSError as exc:
            raise ToolError(f"cannot run pip-audit: {exc}") from exc
    return 0 if completed.returncode == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _summary(title: str, failures: list[str], notes: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(
            f"### {title}\n" + "".join(f"- {n}\n" for n in notes) + "".join(f"- FAIL: {f}\n" for f in failures[:50])
        )


def _report(title: str, failures: list[str], notes: list[str]) -> int:
    for note in notes:
        print(f"[{title}] {note}")
    for failure in failures:
        print(f"[{title}] FAIL: {failure}")
    _summary(title, failures, notes)
    return 1 if failures else 0


def main(argv: list[str] | None = None, root: Path = BACKEND) -> int:
    parser = argparse.ArgumentParser(description="CI quality gates")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("lint", "format"):
        p = sub.add_parser(name)
        p.add_argument("--update", action="store_true", help="rewrite the baseline")
        p.add_argument(
            "--allow-stale", action="store_true", help="do not fail on baseline entries that no longer occur"
        )
    sub.add_parser("junit").add_argument("report")
    audit = sub.add_parser("audit")
    audit.add_argument("--dry-run", action="store_true", help="validate the ignore list and print the command only")
    args = parser.parse_args(argv)

    try:
        if args.command == "lint":
            violations = collect_violations(root)
            target = root / LINT_BASELINE
            if args.update:
                target.write_text(
                    json.dumps(build_lint_baseline(violations), indent=1) + "\n", encoding="utf-8", newline="\n"
                )
                print(f"[lint] baseline written: {len(violations)} violations")
                return 0
            if not target.exists():
                raise ToolError(f"{LINT_BASELINE} is missing; create it with `lint --update` and review it")
            failures, notes = compare_lint(
                violations, json.loads(target.read_text(encoding="utf-8")), allow_stale=args.allow_stale
            )
            return _report("lint", failures, notes)
        if args.command == "format":
            files = unformatted_files(root)
            target = root / FORMAT_BASELINE
            if args.update:
                write_format_baseline(target, files)
                print(f"[format] baseline written: {len(files)} files")
                return 0
            failures, notes = compare_format(files, read_format_baseline(target), allow_stale=args.allow_stale)
            return _report("format", failures, notes)
        if args.command == "junit":
            return _report("tests", check_junit(Path(args.report)), [f"checked {args.report}"])
        if args.command == "audit":
            ignore_file = root / AUDIT_IGNORES
            text = ignore_file.read_text(encoding="utf-8") if ignore_file.exists() else ""
            ids, problems = parse_audit_ignores(text, dt.datetime.now(dt.UTC).date())
            if problems:
                return _report("audit", problems, [])
            return run_audit(root, ids, dry_run=args.dry_run)
    except ToolError as exc:
        print(f"[{args.command}] tooling error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
