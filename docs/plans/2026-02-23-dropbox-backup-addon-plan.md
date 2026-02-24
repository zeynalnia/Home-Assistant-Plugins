# Dropbox Backup Addon Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Home Assistant addon that uploads HA backups to Dropbox with OAuth2, scheduling, and retention.

**Architecture:** Single Python async process using aiohttp. Serves a web UI via HA ingress for OAuth and manual triggers. Downloads backups from the Supervisor API, uploads to Dropbox via chunked upload. Stores tokens and tracking state in `/data/`.

**Tech Stack:** Python 3.11, aiohttp, dropbox SDK, Alpine Linux Docker image

---

### Task 1: Addon scaffold — config.yaml and Dockerfile

**Files:**
- Create: `dropbox_backup/config.yaml`
- Create: `dropbox_backup/Dockerfile`
- Create: `dropbox_backup/requirements.txt`

**Step 1: Create `dropbox_backup/config.yaml`**

```yaml
name: "Dropbox Backup"
version: "0.1.0"
slug: "dropbox_backup"
description: "Back up Home Assistant snapshots to Dropbox"
url: "https://github.com/your-repo/dropbox-backup-addon"
arch:
  - amd64
  - aarch64
  - armv7
  - armhf
  - i386
hassio_api: true
hassio_role: "backup"
ingress: true
ingress_port: 8099
options:
  dropbox_app_key: ""
  dropbox_app_secret: ""
  backup_interval_hours: 24
  max_backups_in_dropbox: 10
  dropbox_backup_path: "/HomeAssistant/Backups"
schema:
  dropbox_app_key: str
  dropbox_app_secret: str
  backup_interval_hours: int
  max_backups_in_dropbox: int
  dropbox_backup_path: str
```

**Step 2: Create `dropbox_backup/requirements.txt`**

```
aiohttp==3.9.3
dropbox==12.0.2
jinja2==3.1.3
```

**Step 3: Create `dropbox_backup/Dockerfile`**

```dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . /app

CMD ["python3", "/app/run.py"]
```

**Step 4: Commit**

```bash
git add dropbox_backup/config.yaml dropbox_backup/Dockerfile dropbox_backup/requirements.txt
git commit -m "feat: addon scaffold with config.yaml, Dockerfile, requirements"
```

---

### Task 2: Persistent state helpers — tokens.json and uploaded.json

**Files:**
- Create: `dropbox_backup/state.py`

**Step 1: Implement state module**

This module manages reading/writing `/data/tokens.json` and `/data/uploaded.json`.

```python
"""Persistent state management for tokens and upload tracking."""

import json
import logging
from pathlib import Path

DATA_DIR = Path("/data")
TOKENS_FILE = DATA_DIR / "tokens.json"
UPLOADED_FILE = DATA_DIR / "uploaded.json"

_logger = logging.getLogger(__name__)


def load_tokens() -> dict | None:
    """Load OAuth tokens from disk. Returns None if not found."""
    if not TOKENS_FILE.exists():
        return None
    try:
        return json.loads(TOKENS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _logger.error("Failed to load tokens: %s", exc)
        return None


def save_tokens(tokens: dict) -> None:
    """Save OAuth tokens to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))


def clear_tokens() -> None:
    """Remove stored tokens."""
    if TOKENS_FILE.exists():
        TOKENS_FILE.unlink()


def load_uploaded() -> dict:
    """Load uploaded backup tracking. Returns {slug: {name, date, path}}."""
    if not UPLOADED_FILE.exists():
        return {}
    try:
        return json.loads(UPLOADED_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _logger.error("Failed to load uploaded state: %s", exc)
        return {}


def save_uploaded(uploaded: dict) -> None:
    """Save uploaded backup tracking to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADED_FILE.write_text(json.dumps(uploaded, indent=2))
```

**Step 2: Commit**

```bash
git add dropbox_backup/state.py
git commit -m "feat: persistent state helpers for tokens and upload tracking"
```

---

### Task 3: Addon options loader

**Files:**
- Create: `dropbox_backup/options.py`

**Step 1: Implement options loader**

HA addons receive options via `/data/options.json`.

```python
"""Load addon options from Home Assistant."""

import json
import logging
from pathlib import Path

OPTIONS_FILE = Path("/data/options.json")

_logger = logging.getLogger(__name__)


def load_options() -> dict:
    """Load addon options. Returns dict with all configured values."""
    if not OPTIONS_FILE.exists():
        _logger.warning("Options file not found at %s", OPTIONS_FILE)
        return {}
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _logger.error("Failed to load options: %s", exc)
        return {}
```

**Step 2: Commit**

```bash
git add dropbox_backup/options.py
git commit -m "feat: addon options loader from /data/options.json"
```

---

### Task 4: Dropbox OAuth2 module

**Files:**
- Create: `dropbox_backup/dropbox_auth.py`

**Step 1: Implement OAuth2 helper**

Uses the Dropbox SDK's `DropboxOAuth2FlowNoRedirect` for PKCE flow, and token refresh.

```python
"""Dropbox OAuth2 authentication helpers."""

import logging

import dropbox

from state import load_tokens, save_tokens, clear_tokens

_logger = logging.getLogger(__name__)


class DropboxAuth:
    """Manages Dropbox OAuth2 flow and token lifecycle."""

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self._flow: dropbox.DropboxOAuth2Flow | None = None

    def start_auth(self, redirect_uri: str) -> str:
        """Start OAuth2 flow. Returns the authorization URL."""
        self._flow = dropbox.DropboxOAuth2Flow(
            consumer_key=self.app_key,
            consumer_secret=self.app_secret,
            redirect_uri=redirect_uri,
            session={},
            csrf_token_session_key="dropbox-auth-csrf-token",
            token_access_type="offline",
        )
        return self._flow.start()

    def finish_auth(self, query_params: dict) -> dict:
        """Complete OAuth2 flow with the callback query params.
        Returns token dict and saves to disk.
        """
        if self._flow is None:
            raise RuntimeError("OAuth flow not started")
        result = self._flow.finish(query_params)
        tokens = {
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "expires_at": result.expires_at.isoformat() if result.expires_at else None,
        }
        save_tokens(tokens)
        _logger.info("Dropbox authorization completed successfully")
        return tokens

    def get_client(self) -> dropbox.Dropbox | None:
        """Get an authenticated Dropbox client, or None if not authorized."""
        tokens = load_tokens()
        if not tokens or not tokens.get("refresh_token"):
            return None
        try:
            dbx = dropbox.Dropbox(
                oauth2_refresh_token=tokens["refresh_token"],
                app_key=self.app_key,
                app_secret=self.app_secret,
            )
            # Force token refresh to verify it works
            dbx.check_and_refresh_access_token()
            return dbx
        except dropbox.exceptions.AuthError as exc:
            _logger.error("Dropbox auth failed: %s", exc)
            clear_tokens()
            return None

    @staticmethod
    def is_authorized() -> bool:
        """Check if we have stored tokens."""
        tokens = load_tokens()
        return tokens is not None and bool(tokens.get("refresh_token"))
```

**Step 2: Commit**

```bash
git add dropbox_backup/dropbox_auth.py
git commit -m "feat: Dropbox OAuth2 module with PKCE flow and token refresh"
```

---

### Task 5: Backup engine — Supervisor API + Dropbox upload

**Files:**
- Create: `dropbox_backup/backup_engine.py`

**Step 1: Implement backup engine**

Downloads backups from Supervisor, uploads to Dropbox with chunked upload, manages retention.

```python
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
        while len(entries) > max_backups:
            oldest = entries.pop(0)
            _logger.info("Retention: deleting %s", oldest.path_display)
            dbx.files_delete_v2(oldest.path_display)
    except dropbox.exceptions.ApiError as exc:
        _logger.error("Retention check failed: %s", exc)
```

**Step 2: Commit**

```bash
git add dropbox_backup/backup_engine.py
git commit -m "feat: backup engine with Supervisor download, Dropbox chunked upload, retention"
```

---

### Task 6: Scheduler

**Files:**
- Create: `dropbox_backup/scheduler.py`

**Step 1: Implement async scheduler**

```python
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
```

**Step 2: Commit**

```bash
git add dropbox_backup/scheduler.py
git commit -m "feat: async backup scheduler with configurable interval"
```

---

### Task 7: Web UI — aiohttp routes and HTML template

**Files:**
- Create: `dropbox_backup/web/server.py`
- Create: `dropbox_backup/web/templates/index.html`

**Step 1: Create `dropbox_backup/web/templates/index.html`**

Minimal Jinja2 template with status, buttons, and backup list.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dropbox Backup</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #333; background: #fafafa; }
        h1 { color: #0061fe; }
        .status { padding: 12px 16px; border-radius: 8px; margin: 16px 0; }
        .status.ok { background: #e6f4ea; color: #1e7e34; }
        .status.warn { background: #fff3cd; color: #856404; }
        .btn { display: inline-block; padding: 10px 20px; border: none; border-radius: 6px; color: #fff; cursor: pointer; text-decoration: none; font-size: 14px; margin: 4px; }
        .btn-primary { background: #0061fe; }
        .btn-primary:hover { background: #0050d4; }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #218838; }
        table { width: 100%; border-collapse: collapse; margin-top: 16px; }
        th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #ddd; }
        th { background: #f0f0f0; }
        .info { color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <h1>Dropbox Backup</h1>

    {% if authorized %}
    <div class="status ok">Authorized with Dropbox</div>
    {% else %}
    <div class="status warn">Not authorized — connect your Dropbox account to start backing up.</div>
    <a href="{{ ingress_path }}/auth" class="btn btn-primary">Authorize with Dropbox</a>
    {% endif %}

    {% if authorized %}
    <form action="{{ ingress_path }}/trigger" method="post" style="display:inline;">
        <button type="submit" class="btn btn-success">Backup Now</button>
    </form>
    {% endif %}

    {% if last_run %}
    <p class="info">Last backup: {{ last_run }}</p>
    {% endif %}
    {% if next_run %}
    <p class="info">Next scheduled backup: {{ next_run }}</p>
    {% endif %}
    {% if last_result %}
    <p class="info">Last result: Uploaded {{ last_result.uploaded | length }}, Skipped {{ last_result.skipped | length }}{% if last_result.errors %}, Errors: {{ last_result.errors | length }}{% endif %}</p>
    {% endif %}

    {% if uploaded %}
    <h2>Uploaded Backups</h2>
    <table>
        <thead><tr><th>Name</th><th>Date</th><th>Dropbox Path</th></tr></thead>
        <tbody>
        {% for slug, info in uploaded.items() %}
            <tr>
                <td>{{ info.name }}</td>
                <td>{{ info.date }}</td>
                <td>{{ info.dropbox_path }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    {% endif %}
</body>
</html>
```

**Step 2: Create `dropbox_backup/web/server.py`**

aiohttp routes for index, auth, callback, trigger.

```python
"""Web server for the Dropbox Backup addon (HA ingress)."""

import logging
import os
from pathlib import Path

from aiohttp import web
import jinja2

from state import load_uploaded

_logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(dropbox_auth, scheduler, run_backup_fn) -> web.Application:
    """Create and configure the aiohttp web application."""
    app = web.Application()
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    app["jinja_env"] = env
    app["dropbox_auth"] = dropbox_auth
    app["scheduler"] = scheduler
    app["run_backup_fn"] = run_backup_fn

    app.router.add_get("/", handle_index)
    app.router.add_get("/auth", handle_auth)
    app.router.add_get("/callback", handle_callback)
    app.router.add_post("/trigger", handle_trigger)

    return app


def _ingress_path() -> str:
    """Get the ingress path prefix from env."""
    return os.environ.get("INGRESS_PATH", "")


async def handle_index(request: web.Request) -> web.Response:
    """Render the status page."""
    env = request.app["jinja_env"]
    scheduler = request.app["scheduler"]
    auth = request.app["dropbox_auth"]

    template = env.get_template("index.html")
    html = template.render(
        authorized=auth.is_authorized(),
        ingress_path=_ingress_path(),
        last_run=scheduler.last_run,
        next_run=scheduler.next_run,
        last_result=scheduler.last_result,
        uploaded=load_uploaded(),
    )
    return web.Response(text=html, content_type="text/html")


async def handle_auth(request: web.Request) -> web.Response:
    """Start the Dropbox OAuth2 flow."""
    auth = request.app["dropbox_auth"]
    ingress = _ingress_path()
    # Build the redirect URI for the callback
    redirect_uri = f"{request.scheme}://{request.host}{ingress}/callback"
    auth_url = auth.start_auth(redirect_uri)
    raise web.HTTPFound(auth_url)


async def handle_callback(request: web.Request) -> web.Response:
    """Handle the Dropbox OAuth2 callback."""
    auth = request.app["dropbox_auth"]
    try:
        auth.finish_auth(dict(request.query))
        raise web.HTTPFound(_ingress_path() + "/")
    except Exception as exc:
        _logger.error("OAuth callback failed: %s", exc)
        return web.Response(
            text=f"Authorization failed: {exc}", status=500
        )


async def handle_trigger(request: web.Request) -> web.Response:
    """Manually trigger a backup."""
    scheduler = request.app["scheduler"]
    run_backup_fn = request.app["run_backup_fn"]
    try:
        result = await run_backup_fn()
        scheduler.last_run = __import__("datetime").datetime.now()
        scheduler.last_result = result
        raise web.HTTPFound(_ingress_path() + "/")
    except web.HTTPFound:
        raise
    except Exception as exc:
        _logger.error("Manual backup failed: %s", exc)
        return web.Response(text=f"Backup failed: {exc}", status=500)
```

**Step 3: Commit**

```bash
git add dropbox_backup/web/
git commit -m "feat: web UI with aiohttp routes and Jinja2 template"
```

---

### Task 8: Main entry point — run.py

**Files:**
- Create: `dropbox_backup/run.py`

**Step 1: Implement run.py**

Wires everything together: loads options, starts scheduler, starts web server.

```python
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
```

**Step 2: Commit**

```bash
git add dropbox_backup/run.py
git commit -m "feat: main entry point wiring options, auth, scheduler, and web server"
```

---

### Task 9: Final integration — verify file structure and add README

**Files:**
- Verify: all files under `dropbox_backup/`

**Step 1: Verify the final file structure**

```
dropbox_backup/
├── config.yaml
├── Dockerfile
├── requirements.txt
├── run.py
├── options.py
├── state.py
├── dropbox_auth.py
├── backup_engine.py
├── scheduler.py
└── web/
    ├── server.py
    └── templates/
        └── index.html
```

**Step 2: Build the Docker image locally to verify it compiles**

Run: `docker build -t dropbox-backup-test dropbox_backup/`
Expected: Image builds successfully.

**Step 3: Commit any fixes**

```bash
git add -A dropbox_backup/
git commit -m "chore: finalize addon structure and verify build"
```
