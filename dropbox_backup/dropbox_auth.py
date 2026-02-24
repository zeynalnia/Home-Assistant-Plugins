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
