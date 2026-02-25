"""Web server for the Dropbox Backup addon (HA ingress)."""

import logging
from datetime import datetime
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
    app.router.add_post("/auth", handle_auth_submit)
    app.router.add_post("/trigger", handle_trigger)
    app.router.add_get("/status", handle_status)

    return app


async def handle_index(request: web.Request) -> web.Response:
    """Render the status page."""
    env = request.app["jinja_env"]
    scheduler = request.app["scheduler"]
    auth = request.app["dropbox_auth"]

    template = env.get_template("index.html")
    html = template.render(
        authorized=auth.is_authorized(),
        last_run=scheduler.last_run,
        next_run=scheduler.next_run,
        last_result=scheduler.last_result,
        uploaded=load_uploaded(),
    )
    return web.Response(text=html, content_type="text/html")


async def handle_auth(request: web.Request) -> web.Response:
    """Show the Dropbox authorization URL and code input form."""
    env = request.app["jinja_env"]
    auth = request.app["dropbox_auth"]
    auth_url = auth.start_auth()

    template = env.get_template("auth.html")
    html = template.render(
        auth_url=auth_url,
    )
    return web.Response(text=html, content_type="text/html")


async def handle_auth_submit(request: web.Request) -> web.Response:
    """Handle the authorization code submitted by the user."""
    auth = request.app["dropbox_auth"]
    data = await request.post()
    auth_code = data.get("auth_code", "")
    if not auth_code:
        raise web.HTTPFound("./auth")
    try:
        auth.finish_auth(auth_code)
        raise web.HTTPFound("./")
    except web.HTTPFound:
        raise
    except Exception as exc:
        _logger.error("OAuth authorization failed: %s", exc)
        env = request.app["jinja_env"]
        auth_url = auth.start_auth()
        template = env.get_template("auth.html")
        html = template.render(
            auth_url=auth_url,
            error=str(exc),
        )
        return web.Response(text=html, content_type="text/html")


def _wants_json(request: web.Request) -> bool:
    accept = request.headers.get("Accept", "")
    return "application/json" in accept


async def handle_trigger(request: web.Request) -> web.Response:
    """Manually trigger a backup."""
    scheduler = request.app["scheduler"]
    run_backup_fn = request.app["run_backup_fn"]
    try:
        result = await run_backup_fn()
        scheduler.last_run = datetime.now()
        scheduler.last_result = result
        if _wants_json(request):
            return web.json_response({"status": "success", "result": result})
        raise web.HTTPFound("./")
    except web.HTTPFound:
        raise
    except Exception as exc:
        _logger.error("Manual backup failed: %s", exc)
        if _wants_json(request):
            return web.json_response(
                {"status": "error", "error": str(exc)}, status=500
            )
        return web.Response(text=f"Backup failed: {exc}", status=500)


async def handle_status(request: web.Request) -> web.Response:
    """Return current addon state as JSON."""
    scheduler = request.app["scheduler"]
    auth = request.app["dropbox_auth"]

    def _fmt_dt(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    data = {
        "state": request.app.get("backup_state", "idle"),
        "authorized": auth.is_authorized(),
        "last_run": _fmt_dt(scheduler.last_run),
        "next_run": _fmt_dt(scheduler.next_run),
        "last_result": scheduler.last_result,
        "interval_hours": scheduler.interval_hours,
    }
    return web.json_response(data)
