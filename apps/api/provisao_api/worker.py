"""Worker entrypoint. Channel adapters are injected separately from domain persistence."""
import time
from .config import settings
from .db import SessionLocal
from .services.conversations import process_pending_outbox


def unavailable_gateway(_event) -> None:
    """Safe default until an active channel adapter is configured."""
    raise RuntimeError("no active channel gateway configured")

def main() -> None:
    while True:
        with SessionLocal() as session:
            process_pending_outbox(session, unavailable_gateway)
            session.commit()
        time.sleep(2)
if __name__ == "__main__": main()
