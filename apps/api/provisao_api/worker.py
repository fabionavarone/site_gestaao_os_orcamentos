"""Bounded Telegram inbox, outbox, polling and storage maintenance workers."""
import json
import logging
import os
import signal
import socket
import time
from .config import settings
from .db import SessionLocal
from .services.conversations import process_pending_outbox
from .services.delivery import TelegramOutboxDelivery
from .services.inbox_worker import process_event_batch
from .services.polling import poll_active_bots
from .services.storage import LocalStorage

stop=False


def request_stop(*_args):
    global stop; stop=True


def log(operation: str, result: str, **context):
    logging.getLogger("provisao.worker").info(json.dumps({"service":"telegram-worker","operation":operation,"result":result,**context},default=str))


def run_once(kind: str) -> int:
    cfg=settings(); count=0
    with SessionLocal() as session:
        if kind in {"all","inbox"}: count += process_event_batch(session,cfg); session.commit()
        if kind in {"all","outbox"}: count += process_pending_outbox(session,TelegramOutboxDelivery(session,cfg),worker_id=f"{socket.gethostname()}:{os.getpid()}",lock_seconds=cfg.outbox_lock_seconds,max_attempts=cfg.outbox_max_attempts)
        if kind in {"all","polling"} and cfg.app_env in {"development","staging"}: count += poll_active_bots(session,cfg); session.commit()
        if kind in {"all","cleanup"}: count += LocalStorage(cfg.storage_root).cleanup_temp()
    return count


def main() -> None:
    logging.basicConfig(level=logging.INFO,format="%(message)s")
    signal.signal(signal.SIGTERM,request_stop); signal.signal(signal.SIGINT,request_stop)
    kind=os.getenv("WORKER_KIND","all")
    if kind not in {"all","inbox","outbox","polling","cleanup"}: raise SystemExit("invalid WORKER_KIND")
    while not stop:
        try: log(kind,"ok",processed=run_once(kind))
        except Exception as exc: log(kind,"error",error=str(exc)[:500])
        for _ in range(20):
            if stop: break
            time.sleep(.1)


if __name__ == "__main__": main()
