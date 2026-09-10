"""Focused tests for first Super Administrator bootstrap."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from scripts.provision_first_super_admin import provision_first_super_admin
from src.database import Base
from src.models import AuditLog, PlatformRole, Profile, User


def make_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    Base.metadata.create_all(engine)
    return engine


def test_bootstrap_promotes_verified_existing_user_and_audits(tmp_path):
    engine = make_db(tmp_path)
    with Session(engine) as db:
        user = User(
            email="operator@example.com",
            password_hash="hash",
            profile=Profile(username="operator", display_name="Operator"),
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()

        provisioned = provision_first_super_admin(db, user.email)

        assert provisioned.role is PlatformRole.SUPER_ADMIN
        entry = db.scalar(
            select(AuditLog).where(AuditLog.action == "platform.super_admin_bootstrapped")
        )
        assert entry is not None
        assert entry.actor_id is None
        assert entry.target_id == user.id
        assert entry.metadata_json["from_role"] == "participant"

    engine.dispose()


def test_bootstrap_refuses_unverified_user_and_second_bootstrap(tmp_path):
    engine = make_db(tmp_path)
    with Session(engine) as db:
        user = User(
            email="operator@example.com",
            password_hash="hash",
            profile=Profile(username="operator", display_name="Operator"),
        )
        db.add(user)
        db.commit()
        with pytest.raises(RuntimeError, match="email-verified"):
            provision_first_super_admin(db, user.email)

        user.email_verified_at = datetime.now(UTC)
        db.commit()
        provision_first_super_admin(db, user.email)
        with pytest.raises(RuntimeError, match="already exists"):
            provision_first_super_admin(db, user.email)

    engine.dispose()
