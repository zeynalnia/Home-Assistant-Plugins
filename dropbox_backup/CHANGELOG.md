# Changelog

All notable changes to this project are documented in this file.

## [0.5.7] - 2025

### Changed
- Renamed addon to "Dropbox HA Backup" and integration domain to `dropbox_ha_backup`
- Renamed repository to match GitHub repo name
- Added `.gitignore` for local settings and plan docs

## [0.5.5] - 2025

### Fixed
- Masked app secret in the configuration UI
- Enabled unbuffered Python output so logs appear in the addon Log tab

## [0.5.3] - 2025

### Added
- Trigger Backup button entity in the companion integration

### Fixed
- Removed `is_hassio` import; use `SUPERVISOR_TOKEN` environment variable for broader compatibility

## [0.5.1] - 2025

### Fixed
- Used `FlowResult` for broader HA version compatibility in config flow
- Bumped addon and integration versions to trigger rebuild

## [0.5.0] - 2025

### Added
- Companion Home Assistant integration with auto-discovery
  - 4 sensors: status, last run, next run, uploaded count
  - 1 binary sensor: Dropbox authorized
  - Config flow with Supervisor auto-discovery and manual entry
- `automatic_backup` option to enable/disable scheduled backups

## [0.4.1] - 2025

### Fixed
- Moved stdin reading to shell script for s6-overlay compatibility
- Used `rootfs/run.sh` instead of `services.d` for stdin support
- Added `CMD` to Dockerfile so `run.sh` is executed by s6-overlay

## [0.4.0] - 2025

### Added
- stdin trigger for manual backup from the HA addon panel
- Sensor entity state reporting via HA Core REST API
- Event bus integration (fires `dropbox_ha_backup.success` / `dropbox_ha_backup.failed`)
- JSON status API endpoint (`GET /status`)

## [0.3.0] - 2025

### Fixed
- Ingress compatibility with relative URLs
- Proper s6-overlay setup with HA base image

## [0.2.0] - 2025

### Changed
- Switched to plain Python Alpine base image (removed s6-overlay dependency)
- Resolved container startup issues with various base image configurations

## [0.1.1] - 2025

### Fixed
- Switched OAuth to no-redirect PKCE flow for addon compatibility
- Added missing `web/__init__.py`, fixed datetime import, cleaned up retention state

## [0.1.0] - 2025

### Added
- Initial addon scaffold with `config.yaml`, `Dockerfile`, and `requirements.txt`
- Persistent state helpers for tokens and upload tracking
- Addon options loader
- Dropbox OAuth2 module with PKCE flow and token refresh
- Backup engine with Supervisor download, Dropbox chunked upload, and retention policy
- Async backup scheduler with configurable interval
- Web UI with aiohttp routes and Jinja2 templates
- Main entry point wiring options, auth, scheduler, and web server
- `repository.yaml` for HA addon repository format
