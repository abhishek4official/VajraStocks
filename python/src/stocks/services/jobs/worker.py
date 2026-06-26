"""Threaded job worker — drains the queue off the request thread (V2.0 spec M1).

A single background thread loops on ``JobRunner.run_next()``, using a fresh DB session per
iteration so it never holds a connection open while idle. Start it in the app lifespan;
stop it on shutdown.
"""

from __future__ import annotations

import threading

from loguru import logger

from stocks.services.jobs.runner import JobRunner


class JobWorker:
    def __init__(self, db_manager, poll_interval: float = 2.0):
        self.db_manager = db_manager
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="job-worker", daemon=True)
        self._thread.start()
        logger.info("Job worker started.")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("Job worker stopped.")

    def _loop(self) -> None:
        while not self._stop.is_set():
            ran = None
            session = self.db_manager.get_session()
            try:
                ran = JobRunner(session).run_next()
            except Exception as exc:  # noqa: BLE001 — never let the worker thread die
                logger.warning(f"Job worker iteration error: {exc}")
            finally:
                session.close()
            if ran is None:
                self._stop.wait(self.poll_interval)  # idle — wait, interruptible by stop()
