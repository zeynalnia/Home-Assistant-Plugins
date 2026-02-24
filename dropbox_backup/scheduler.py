"""Simple async scheduler for periodic backup runs."""

import asyncio
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class BackupScheduler:
    """Runs backup engine on a configurable interval."""

    def __init__(self, interval_hours: float, backup_callback):
        self.interval_hours = interval_hours
        self.backup_callback = backup_callback
        self._task: asyncio.Task | None = None
        self.last_run: datetime | None = None
        self.last_result: dict | None = None
        self.next_run: datetime | None = None

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

    async def _loop(self) -> None:
        """Main scheduler loop."""
        interval_seconds = self.interval_hours * 3600
        while True:
            self.next_run = datetime.now().replace(microsecond=0)
            self.next_run = datetime.fromtimestamp(
                self.next_run.timestamp() + interval_seconds
            )
            _logger.info("Next backup scheduled at %s", self.next_run)
            await asyncio.sleep(interval_seconds)
            try:
                _logger.info("Scheduled backup starting")
                self.last_result = await self.backup_callback()
                self.last_run = datetime.now()
                _logger.info("Scheduled backup completed: %s", self.last_result)
            except Exception as exc:
                _logger.error("Scheduled backup failed: %s", exc)
                self.last_result = {"error": str(exc)}
                self.last_run = datetime.now()
