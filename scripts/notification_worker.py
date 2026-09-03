"""Run the scheduled notification worker against the configured database."""
import time

from src.database import SessionLocal
from src.services.notification_worker import process_scheduled_notifications


class ConfiguredSender:
    def send(self, user_id, notification_type, title, message, payload):
        # Scheduled work currently targets in-app delivery. Channel adapters are
        # invoked by immediate notification dispatch according to preferences/rules.
        from src.services.notification import notify
        with SessionLocal() as db:
            notify(db, user_id, notification_type, title, message, payload)


def run_once() -> int:
    with SessionLocal() as db:
        return process_scheduled_notifications(db, ConfiguredSender())


def main() -> None:
    while True:
        run_once()
        time.sleep(60)


if __name__ == "__main__":
    main()
