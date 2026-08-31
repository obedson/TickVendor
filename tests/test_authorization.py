"""Authorization and tenant-boundary dependency tests."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401
from src.authorization import require_community_role, require_platform_roles
from src.database import Base
from src.models import (
    Community,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformRole,
    User,
)


def test_platform_role_dependency_denies_and_allows():
    participant = SimpleNamespace(role=PlatformRole.PARTICIPANT)
    admin = SimpleNamespace(role=PlatformRole.SUPER_ADMIN)
    dependency = require_platform_roles(PlatformRole.SUPER_ADMIN)

    with pytest.raises(HTTPException) as denied:
        dependency(participant)
    assert denied.value.status_code == 403
    assert dependency(admin) is admin


def test_community_role_enforces_membership_boundary(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rbac.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin = User(email="admin@example.com", password_hash="hash")
        outsider = User(email="outsider@example.com", password_hash="hash")
        db.add_all([admin, outsider])
        db.flush()
        org = Organization(owner_id=admin.id, name="Org", slug="org-rbac")
        db.add(org)
        db.flush()
        community = Community(organization_id=org.id, name="C", slug="community-rbac")
        db.add(community)
        db.flush()
        db.add(Membership(
            community_id=community.id, user_id=admin.id,
            role=MembershipRole.ADMIN, status=MembershipStatus.ACTIVE,
        ))
        db.commit()

        assert require_community_role(
            db, community.id, admin, MembershipRole.ADMIN
        ).role == MembershipRole.ADMIN
        with pytest.raises(HTTPException) as denied:
            require_community_role(db, community.id, outsider, MembershipRole.ADMIN)
        assert denied.value.status_code == 403
        with pytest.raises(HTTPException) as missing:
            require_community_role(db, uuid4(), admin, MembershipRole.ADMIN)
        assert missing.value.status_code == 404
    engine.dispose()
