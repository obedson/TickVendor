"""Run the scheduled notification worker against the configured database."""
import os
import time

from src.database import SessionLocal
from src.services.notification_worker import process_scheduled_notifications


class ConfiguredSender:
    def send(self, user_id, notification_type, title, message, payload):
        # Scheduled work currently targets in-app delivery. Channel adapters are
        # invoked by immediate notification dispatch according to preferences/rules.
        from src.services.notification import notify
        with SessionLocal() as db:
            community_id = payload.get("community_id") if isinstance(payload, dict) else None
            notify(db, user_id, notification_type, title, message, payload,
                   community_id=community_id)


def run_once() -> int:
    with SessionLocal() as db:
        return process_scheduled_notifications(
            db, ConfiguredSender(), batch_size=int(os.getenv("NOTIFICATION_WORKER_BATCH_SIZE", "100"))
        )


def main() -> None:
    while True:
        run_once()
        time.sleep(60)


if __name__ == "__main__":
    main()
