"""
Provision an admin account (Architecture §7.8). Run by an operator, never by the API.

Usage (from backend/):
    python scripts/create_admin.py --email ops@example.com --role ADMIN --platform divyang_matrimony
    python scripts/create_admin.py --email ceo@example.com --role SUPER_ADMIN \
        --platform divyang_matrimony --allow-super-admin     # also needs ALLOW_SUPER_ADMIN_PROVISIONING=yes

Safety:
  - --platform is mandatory; there is no default and no "global" shortcut.
  - SUPER_ADMIN needs BOTH --allow-super-admin and ALLOW_SUPER_ADMIN_PROVISIONING=yes.
  - The password is read with getpass (or stdin with --password-stdin), never from
    a command-line argument, so it stays out of shell history and process lists.
  - The target database (host/name only, no credentials) is shown and the operator
    must type its name to continue, so a wrong DATABASE_URL is caught before any write.
  - Nothing secret is printed or logged.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy.engine import make_url


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision an admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=["ADMIN", "SUPPORT", "SUPER_ADMIN"])
    parser.add_argument("--platform", required=True, help="Platform key; must exist and be active.")
    parser.add_argument("--allow-super-admin", action="store_true")
    parser.add_argument("--password-stdin", action="store_true", help="Read the password from stdin.")
    return parser.parse_args(argv)


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Admin password: ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match.")
    return first


def _check_super_admin_authorization(role: str, allow_flag: bool) -> bool:
    """SUPER_ADMIN needs the flag AND the environment opt-in."""
    if role != "SUPER_ADMIN":
        return False
    if not allow_flag or os.environ.get("ALLOW_SUPER_ADMIN_PROVISIONING", "").lower() != "yes":
        raise SystemExit("SUPER_ADMIN provisioning needs --allow-super-admin and ALLOW_SUPER_ADMIN_PROVISIONING=yes.")
    return True


def _confirm_target_database(database_url: str) -> None:
    target = make_url(database_url)
    print(f"Target database: host={target.host} port={target.port} name={target.database}")
    typed = input("Type the database name to continue: ").strip()
    if typed != (target.database or ""):
        raise SystemExit("Database name did not match; aborting.")


async def _run(args: argparse.Namespace, password: str, allow_super_admin: bool) -> None:
    # Imported late so --help works without a full environment.
    from app.core.database import AsyncSessionLocal
    from app.services.admin_service import provision_admin

    async with AsyncSessionLocal() as session:
        admin = await provision_admin(
            session,
            email=args.email,
            password=password,
            role=args.role,
            platform_id=args.platform,
            allow_super_admin=allow_super_admin,
        )
        await session.commit()
    print(f"Created {args.role} account {admin.id} on platform {args.platform}.")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    allow_super_admin = _check_super_admin_authorization(args.role, args.allow_super_admin)

    from app.core.config import settings

    _confirm_target_database(settings.DATABASE_URL)
    password = _read_password(args.password_stdin)
    asyncio.run(_run(args, password, allow_super_admin))


if __name__ == "__main__":
    main()
