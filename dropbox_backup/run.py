"""Main entry point for the Dropbox Backup addon."""

import asyncio
import logging
import sys

from aiohttp import web

from options import load_options
from dropbox_auth import DropboxAuth
from backup_engine import run_backup
from scheduler import BackupScheduler
from web.server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
_logger = logging.getLogger(__name__)


def main() -> None:
    """Start the addon."""
    options = load_options()
    app_key = options.get("dropbox_app_key", "")
    app_secret = options.get("dropbox_app_secret", "")
    interval_hours = options.get("backup_interval_hours", 24)
    max_backups = options.get("max_backups_in_dropbox", 10)
    backup_path = options.get("dropbox_backup_path", "/HomeAssistant/Backups")

    if not app_key or not app_secret:
        _logger.error("Dropbox app_key and app_secret must be configured in addon options")

    auth = DropboxAuth(app_key, app_secret)

    async def do_backup() -> dict:
        dbx = auth.get_client()
        if dbx is None:
            _logger.warning("Skipping backup: not authorized with Dropbox")
            return {"error": "Not authorized"}
        return await run_backup(dbx, backup_path, max_backups)

    scheduler = BackupScheduler(interval_hours, do_backup)
    app = create_app(auth, scheduler, do_backup)

    async def on_startup(_app: web.Application) -> None:
        scheduler.start()

    async def on_cleanup(_app: web.Application) -> None:
        scheduler.stop()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    _logger.info("Starting Dropbox Backup addon on port 8099")
    web.run_app(app, host="0.0.0.0", port=8099)


if __name__ == "__main__":
    main()
