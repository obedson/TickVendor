"""One-time operator bootstrap for the first platform Super Administrator.

This command deliberately requires an already registered and email-verified user.
It is not an HTTP endpoint and cannot be used to promote arbitrary users remotely.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.models  # noqa: F401
from src.models import PlatformRole, User
from src.services.notification import audit


def provision_first_super_admin(db: Session, email: str) -> User:
    """Promote one existing verified user, refusing all non-bootstrap states."""
    existing_count = db.scalar(
        select(func.count()).select_from(User).where(User.role == PlatformRole.SUPER_ADMIN)
    )
    if existing_count:
        raise RuntimeError("A Super Administrator already exists; first-admin bootstrap is closed")

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise RuntimeError("User not found; register and verify the operator account first")
    if not user.is_active:
        raise RuntimeError("The operator account is inactive")
    if user.email_verified_at is None:
        raise RuntimeError("The operator account must be email-verified before bootstrap")

    previous_role = user.role.value
    user.role = PlatformRole.SUPER_ADMIN
    audit(
        db,
        actor_id=None,
        action="platform.super_admin_bootstrapped",
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "from_role": previous_role, "to_role": user.role.value},
        commit=False,
    )
    db.commit()
    return user


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision the first TickVendor Super Administrator")
    parser.add_argument("--email", required=True, help="Existing email-verified operator account")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm this one-time privileged database operation",
    )
    args = parser.parse_args()
    if not args.confirm:
        parser.error("refusing to run without --confirm")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("DATABASE_URL must point at the intended staging or production database")

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            user = provision_first_super_admin(db, args.email.strip().lower())
            print(f"Provisioned first Super Administrator: {user.email}")
    except RuntimeError as exc:
        print(f"Bootstrap refused: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
