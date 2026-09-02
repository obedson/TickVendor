"""Payment status API coverage."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.models import (
    Membership,
    MembershipRole,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Profile,
    User,
)
from src.security import create_access_token, hash_password
from tests.test_database import create_event_context


def test_owner_can_read_payment_status_and_other_user_cannot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'payment-status.db'}", connect_args={"check_same_thread": False}); Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        owner, community, event = create_event_context(db); other = User(email="payment-other@example.com", password_hash=hash_password("password-password")); db.add(other); db.flush(); db.add(Profile(user_id=other.id, username="payment-other", display_name="Other")); db.add(Membership(community_id=community.id, user_id=owner.id, role=MembershipRole.MEMBER)); order = Order(reference="STATUS-ORDER", idempotency_key="status-order-key", user_id=owner.id, event_id=event.id, status=OrderStatus.PENDING, total_amount=10, currency="NGN"); db.add(order); db.flush(); db.add(Payment(order_id=order.id, provider="test", provider_reference="status-ref", idempotency_key="status-key", status=PaymentStatus.PENDING, amount=10, currency="NGN")); db.commit(); payment_id = db.query(Payment).one().id; owner_id, other_id = owner.id, other.id
    app = create_app()
    def override():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = override; client = TestClient(app)
    assert client.get(f"/api/v1/payments/{payment_id}", headers={"Authorization": f"Bearer {create_access_token(owner_id, 'participant')}"}).status_code == 200
    assert client.get(f"/api/v1/payments/{payment_id}", headers={"Authorization": f"Bearer {create_access_token(other_id, 'participant')}"}).status_code == 404
    engine.dispose()
