"""Backup engine: download from Supervisor, upload to Dropbox."""

import io
import logging
import os
from datetime import datetime

import aiohttp
import dropbox
from dropbox.files import WriteMode

from state import load_uploaded, save_uploaded

_logger = logging.getLogger(__name__)

SUPERVISOR_URL = "http://supervisor"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB chunks for Dropbox upload


async def list_ha_backups() -> list[dict]:
    """List all backups from the Supervisor API."""
    headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{SUPERVISOR_URL}/backups", headers=headers
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["data"]["backups"]


async def download_backup(slug: str) -> bytes:
    """Download a backup by slug from the Supervisor API.
    Returns the full backup content as bytes.
    """
    headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{SUPERVISOR_URL}/backups/{slug}/download", headers=headers
        ) as resp:
            resp.raise_for_status()
            return await resp.read()


def upload_to_dropbox(
    dbx: dropbox.Dropbox, data: bytes, dropbox_path: str
) -> None:
    """Upload data to Dropbox using chunked upload for large files."""
    size = len(data)
    _logger.info("Uploading %d bytes to %s", size, dropbox_path)

    if size <= CHUNK_SIZE:
        dbx.files_upload(data, dropbox_path, mode=WriteMode.overwrite)
    else:
        stream = io.BytesIO(data)
        session_start = dbx.files_upload_session_start(stream.read(CHUNK_SIZE))
        cursor = dropbox.files.UploadSessionCursor(
            session_id=session_start.session_id, offset=CHUNK_SIZE
        )
        commit = dropbox.files.CommitInfo(
            path=dropbox_path, mode=WriteMode.overwrite
        )
        while stream.tell() < size:
            remaining = size - stream.tell()
            if remaining <= CHUNK_SIZE:
                dbx.files_upload_session_finish(
                    stream.read(CHUNK_SIZE), cursor, commit
                )
            else:
                dbx.files_upload_session_append_v2(
                    stream.read(CHUNK_SIZE), cursor
                )
                cursor.offset = stream.tell()

    _logger.info("Upload complete: %s", dropbox_path)


async def run_backup(
    dbx: dropbox.Dropbox,
    backup_path: str,
    max_backups: int,
) -> dict:
    """Run a full backup cycle. Returns summary dict."""
    results = {"uploaded": [], "skipped": [], "errors": []}
    uploaded = load_uploaded()

    backups = await list_ha_backups()
    _logger.info("Found %d backups in Home Assistant", len(backups))

    for backup in backups:
        slug = backup["slug"]
        name = backup.get("name", slug)
        date = backup.get("date", "unknown")

        if slug in uploaded:
            results["skipped"].append(name)
            continue

        try:
            _logger.info("Downloading backup: %s (%s)", name, slug)
            data = await download_backup(slug)

            safe_name = name.replace("/", "_").replace(" ", "_")
            safe_date = date.replace(":", "-")
            dropbox_file_path = f"{backup_path}/{safe_name}_{safe_date}.tar"

            upload_to_dropbox(dbx, data, dropbox_file_path)

            uploaded[slug] = {
                "name": name,
                "date": date,
                "dropbox_path": dropbox_file_path,
                "uploaded_at": datetime.now().isoformat(),
            }
            save_uploaded(uploaded)
            results["uploaded"].append(name)

        except Exception as exc:
            _logger.error("Failed to backup %s: %s", name, exc)
            results["errors"].append(f"{name}: {exc}")

    # Retention: delete oldest if over limit
    if max_backups > 0:
        await _enforce_retention(dbx, backup_path, max_backups)

    return results


async def _enforce_retention(
    dbx: dropbox.Dropbox, backup_path: str, max_backups: int
) -> None:
    """Delete oldest backups from Dropbox if count exceeds max_backups."""
    try:
        result = dbx.files_list_folder(backup_path)
        entries = sorted(
            result.entries,
            key=lambda e: e.server_modified
            if hasattr(e, "server_modified")
            else datetime.min,
        )
        uploaded = load_uploaded()
        while len(entries) > max_backups:
            oldest = entries.pop(0)
            _logger.info("Retention: deleting %s", oldest.path_display)
            dbx.files_delete_v2(oldest.path_display)
            # Remove from tracking state
            slugs_to_remove = [
                slug for slug, info in uploaded.items()
                if info.get("dropbox_path") == oldest.path_display
            ]
            for slug in slugs_to_remove:
                del uploaded[slug]
        save_uploaded(uploaded)
    except dropbox.exceptions.ApiError as exc:
        _logger.error("Retention check failed: %s", exc)
