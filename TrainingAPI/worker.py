"""Periodically store one overdue reminder per loan. No email or SMS is sent."""
import argparse
import logging
import os
import signal
from threading import Event

from app.databases.mongodb import MongoDB


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Scan once and exit')
    args = parser.parse_args()
    interval = int(os.getenv('WORKER_INTERVAL_SECONDS', '60'))
    if interval < 1:
        parser.error('WORKER_INTERVAL_SECONDS must be positive')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    stopped = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    database = MongoDB()
    try:
        database.ensure_notification_indexes()
        while not stopped.is_set():
            try:
                count = database.create_overdue_notifications()
                logging.info('Overdue scan finished: %s new notifications', count)
            except Exception:
                logging.error('Overdue scan failed; check MongoDB connection and loan data')
                if args.once:
                    raise
            if args.once or stopped.wait(interval):
                break
    finally:
        database.client.close()


if __name__ == '__main__':
    main()
