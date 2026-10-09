"""
Standalone migration runner.

Runs Alembic migrations as a separate deploy step, NOT on container boot.
This avoids race conditions when multiple API containers start concurrently.

See Architecture Section 12.1.

Usage:
    python scripts/migrate.py           # Apply all pending migrations
    python scripts/migrate.py --revision head  # Explicit target
"""
import subprocess
import sys


def main():
    """Run Alembic upgrade to head."""
    revision = "head"
    if len(sys.argv) > 2 and sys.argv[1] == "--revision":
        revision = sys.argv[2]

    print(f"Running Alembic migration to: {revision}")
    result = subprocess.run(
        ["alembic", "upgrade", revision],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.returncode != 0:
        print(f"Migration failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print("Migration completed successfully.")


if __name__ == "__main__":
    main()
