"""Read commands from stdin (for hassio.addon_stdin service)."""

import asyncio
import logging
import sys
from datetime import datetime

_logger = logging.getLogger(__name__)


async def start_stdin_reader(do_backup, scheduler) -> asyncio.Task:
    """Start a background task that reads stdin lines and dispatches commands."""
    loop = asyncio.get_running_loop()

    async def _reader_loop() -> None:
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            command = line.strip()
            if not command:
                continue
            if command == "trigger":
                _logger.info("Received 'trigger' command via stdin")
                try:
                    result = await do_backup()
                    scheduler.last_result = result
                    scheduler.last_run = datetime.now()
                    _logger.info("Stdin-triggered backup completed: %s", result)
                except Exception as exc:
                    scheduler.last_result = {"error": str(exc)}
                    scheduler.last_run = datetime.now()
                    _logger.error("Stdin-triggered backup failed: %s", exc)
            else:
                _logger.warning("Unknown stdin command: %s", command)

    task = asyncio.create_task(_reader_loop())
    _logger.info("Stdin reader started")
    return task
