"""Simple async scheduler for periodic backup runs."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from state import load_last_run, save_last_run

_logger = logging.getLogger(__name__)


class BackupScheduler:
    """Runs backup engine on a configurable interval."""

    def __init__(self, interval_hours: float, backup_callback):
        self.interval_hours = interval_hours
        self.backup_callback = backup_callback
        self._task: asyncio.Task | None = None
        self.next_run: datetime | None = None
        self._restore_last_run()

    def start(self) -> None:
        """Start the scheduler loop."""
        if self.interval_hours <= 0:
            _logger.info("Scheduler disabled (interval_hours=%s)", self.interval_hours)
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        _logger.info("Scheduler started with interval %s hours", self.interval_hours)

    def stop(self) -> None:
        """Stop the scheduler loop."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
            _logger.info("Scheduler stopped")

    def _restore_last_run(self) -> None:
        """Restore last_run and last_result from persisted state."""
        state = load_last_run()
        last_run_str = state.get("last_run")
        if last_run_str:
            try:
                dt = datetime.fromisoformat(last_run_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                self.last_run = dt
            except (ValueError, TypeError):
                self.last_run = None
        else:
            self.last_run = None
        self.last_result = state.get("last_result")

    def record_run(self, result: dict | None) -> None:
        """Record a backup run (scheduled or manual) and persist."""
        self.last_run = datetime.now(timezone.utc)
        self.last_result = result
        save_last_run(self.last_run.isoformat(), self.last_result)

    async def _loop(self) -> None:
        """Main scheduler loop."""
        interval_seconds = self.interval_hours * 3600
        while True:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            self.next_run = now + timedelta(seconds=interval_seconds)
            _logger.info("Next backup scheduled at %s", self.next_run)
            await asyncio.sleep(interval_seconds)
            try:
                _logger.info("Scheduled backup starting")
                result = await self.backup_callback()
                self.record_run(result)
                _logger.info("Scheduled backup completed: %s", result)
            except Exception as exc:
                _logger.error("Scheduled backup failed: %s", exc)
                self.record_run({"error": str(exc)})
