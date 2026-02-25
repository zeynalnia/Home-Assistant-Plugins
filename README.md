# Dropbox HA Backup

A Home Assistant app (add-on) that automatically backs up your HA backups to Dropbox.

## Features

- Automatic scheduled backups (configurable interval)
- Manual backup trigger via HA button entity or web UI
- Chunked uploads for large backups
- Retention policy — automatically removes old backups from Dropbox
- Ingress-enabled web dashboard for status and authorization
- Companion HA integration with sensors and controls

## Prerequisites

1. A **Dropbox account**
2. A **Dropbox App** — create one at the [Dropbox App Console](https://www.dropbox.com/developers/apps):
   - Choose **Scoped access**
   - Choose **Full Dropbox** or **App folder** access
   - Under Permissions, enable `files.content.write` and `files.content.read`
   - Note your **App key** and **App secret**

## Installation

### 1. Add the repository

In Home Assistant, go to **Settings > Apps > App store** (three-dot menu) > **Repositories** and add:

> **Note:** On HA versions before 2026.2, the path is **Settings > Add-ons > Add-on Store**.

```
https://github.com/zeynalnia/Home-Assistant-Plugins
```

### 2. Install the addon

Find **Dropbox HA Backup** in the app store and click **Install**.

### 3. Configure

Go to the app's **Configuration** tab and enter your Dropbox App key and secret. Adjust other options as needed (see [Configuration](#configuration) below).

### 4. Start and authorize

Start the app, then open its **Web UI** (ingress). Click the authorization link, sign in to Dropbox, paste the authorization code back into the app UI, and click **Submit**.

The app will now back up your HA backups to Dropbox on the configured schedule.

## Companion Integration

The app automatically installs a companion Home Assistant integration (`Dropbox HA Backup`) that provides native HA entities. It should be discovered automatically — if not, add it manually via **Settings > Devices & Services > Add Integration**.

### Entities provided

| Entity | Type | Description |
|---|---|---|
| Backup Status | Sensor | Current state: `idle`, `running`, `success`, or `error` |
| Last Backup | Sensor | Timestamp of the last backup run |
| Next Backup | Sensor | Timestamp of the next scheduled backup |
| Uploaded Count | Sensor | Number of backups stored in Dropbox |
| Dropbox Authorized | Binary sensor | Whether the addon is authorized with Dropbox |
| Trigger Backup | Button | Press to manually start a backup |

## Configuration

| Option | Type | Default | Description |
|---|---|---|---|
| `dropbox_app_key` | string | `""` | Your Dropbox App key |
| `dropbox_app_secret` | password | `""` | Your Dropbox App secret |
| `automatic_backup` | boolean | `true` | Enable/disable automatic scheduled backups |
| `backup_interval_hours` | integer | `24` | Hours between automatic backups |
| `max_backups_in_dropbox` | integer | `10` | Maximum backups to keep in Dropbox (oldest removed first) |
| `dropbox_backup_path` | string | `"/HomeAssistant/Backups"` | Dropbox folder path for backups |

## Architecture

The app runs as a Docker container managed by the HA Supervisor. It consists of:

- **App** (`dropbox_backup/`) — aiohttp web server handling OAuth, backup scheduling, and Dropbox uploads
- **Companion integration** (`custom_components/dropbox_ha_backup/`) — auto-installed HA integration providing entities via `DataUpdateCoordinator`

## License

[MIT](LICENSE)
