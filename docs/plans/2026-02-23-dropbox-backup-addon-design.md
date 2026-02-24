# Dropbox Backup Addon — Design

## Summary

A Home Assistant addon that backs up HA snapshots to Dropbox. It lists backups via the Supervisor API, downloads them, and uploads them to Dropbox using chunked uploads. Supports scheduled and manual triggers, OAuth2 with refresh tokens, and configurable retention.

## Architecture

- **Runtime**: Python 3, single async process using `aiohttp`
- **Web UI**: Served via HA ingress (sidebar integration). Minimal HTML/CSS, no frontend framework.
- **Dropbox SDK**: Official `dropbox` Python package for OAuth2 and chunked file uploads.
- **Scheduling**: asyncio loop with configurable interval (hours). Manual trigger via web UI button.
- **Persistent storage**: `/data/tokens.json` (OAuth tokens), `/data/uploaded.json` (upload tracking).

```
┌─────────────────────────────────────────────┐
│  Home Assistant Supervisor                   │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │  Dropbox Backup Addon (Docker)          │ │
│  │                                         │ │
│  │  aiohttp web server (ingress)           │ │
│  │    ├── /  → Status page + OAuth button  │ │
│  │    ├── /auth → Start OAuth flow         │ │
│  │    ├── /callback → OAuth callback       │ │
│  │    └── /trigger → Manual backup trigger │ │
│  │                                         │ │
│  │  Backup Engine (async)                  │ │
│  │    ├── GET supervisor/backups → list    │ │
│  │    ├── GET supervisor/backups/<slug>/dl │ │
│  │    └── Dropbox SDK chunked upload       │ │
│  │                                         │ │
│  │  Scheduler (asyncio loop)               │ │
│  │    └── Runs backup engine on interval   │ │
│  │                                         │ │
│  │  /data/ (persistent)                    │ │
│  │    ├── tokens.json (refresh token)      │ │
│  │    └── uploaded.json (tracking)         │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## OAuth2 Flow

1. User opens addon in HA sidebar (ingress)
2. Clicks "Authorize with Dropbox"
3. Addon redirects to Dropbox OAuth2 authorize URL (app key + redirect URI)
4. User authorizes on Dropbox
5. Dropbox redirects back to addon `/callback` with auth code
6. Addon exchanges auth code for access + refresh token
7. Tokens stored in `/data/tokens.json`

## Backup Flow

1. `GET http://supervisor/backups` with `Authorization: Bearer ${SUPERVISOR_TOKEN}`
2. Compare backup slugs against `/data/uploaded.json`
3. For each new backup:
   - Stream download from `GET http://supervisor/backups/{slug}/download`
   - Chunked upload to Dropbox at `{dropbox_backup_path}/{backup_name}_{date}.tar`
   - Record slug in `uploaded.json`
4. Retention: list files in Dropbox folder, delete oldest if count exceeds `max_backups_in_dropbox`

## Configuration

```yaml
options:
  dropbox_app_key: ""
  dropbox_app_secret: ""
  backup_interval_hours: 24
  max_backups_in_dropbox: 10
  dropbox_backup_path: "/HomeAssistant/Backups"
```

## Error Handling

- **No token**: UI shows "Not authorized" + authorize button. Engine skips runs.
- **Token expired**: Auto-refresh via refresh token. If refresh fails, mark as unauthorized, send HA persistent notification.
- **Supervisor API unreachable**: Log error, retry next scheduled run.
- **Upload fails mid-stream**: Do NOT mark as uploaded. Retry next run.
- **Large backups**: Stream chunks from Supervisor and upload chunks to Dropbox simultaneously to avoid memory pressure.

## Web UI (Ingress)

Minimal single-page UI:
- Status: Authorized / Not authorized
- Last backup: timestamp + result
- Next scheduled backup: timestamp
- Authorize button (when not authorized)
- Backup Now button (manual trigger)
- List of uploaded backups: name, date, Dropbox path

## File Structure

```
dropbox_backup/
├── config.yaml          # HA addon manifest
├── Dockerfile           # Alpine + Python
├── run.py               # Entry point
├── backup_engine.py     # Supervisor API + Dropbox upload logic
├── dropbox_auth.py      # OAuth2 flow
├── scheduler.py         # Async scheduling loop
├── web/
│   ├── server.py        # aiohttp routes
│   └── templates/
│       └── index.html   # Status page template
└── requirements.txt     # aiohttp, dropbox
```
