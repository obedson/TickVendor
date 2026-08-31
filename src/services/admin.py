"""Administrative point adjustment service with mandatory audit trail."""

from sqlalchemy.orm import Session

from src.authorization import require_community_role
from src.models import MembershipRole, User
from src.services.impact import award_points
from src.services.notification import audit


def adjust_points(db: Session, community_id, target_user_id, amount: int, reason: str, admin: User):
    require_community_role(db, community_id, admin, MembershipRole.ADMIN)
    transaction = award_points(
        db, user_id=target_user_id, community_id=community_id,
        source_type="manual_adjustment", source_id=admin.id,
        idempotency_key=f"manual:{community_id}:{target_user_id}:{admin.id}:{reason}:{amount}",
        reason=reason, points_override=amount,
    )
    audit(db, actor_id=admin.id, community_id=community_id, action="impact.adjusted",
          target_type="user", target_id=target_user_id,
          metadata={"amount": amount, "reason": reason, "transaction_id": str(transaction.id)})
    return transaction
