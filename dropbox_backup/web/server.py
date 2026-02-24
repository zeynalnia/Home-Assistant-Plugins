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
