import logging
import os
import sys

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError

from .client import SpotifyClient

load_dotenv()
logger = logging.getLogger(__name__)

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-library-read",
    "user-library-modify",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-private",
    "playlist-modify-public",
]

_client: SpotifyClient | None = None


def build_auth_manager(open_browser: bool = False) -> SpotifyOAuth:
    return SpotifyOAuth(
        scope=",".join(SCOPES),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        open_browser=open_browser,
    )


def _build_spotify() -> spotipy.Spotify:
    return spotipy.Spotify(auth_manager=build_auth_manager(open_browser=False))


def get_client() -> SpotifyClient:
    """Lazily build and cache the SpotifyClient (never at import time)."""
    global _client
    if _client is None:
        _client = SpotifyClient(_build_spotify())
    return _client


def reset_client() -> None:
    global _client
    _client = None


def _red(text: str) -> str:
    """Wrap text in bright-red ANSI, but only when writing to a real terminal."""
    if sys.stdout.isatty():
        return f"\033[91m{text}\033[0m"
    return text


# Auth-server errors that mean "this Spotify account can't authorize this app",
# almost always because the app is in Development Mode and the account isn't on
# its allowlist. Shown with a targeted fix instead of a raw traceback.
_ALLOWLIST_ERROR_MARKERS = ("server_error", "access_denied")

_ALLOWLIST_HELP = (
    "Spotify refused the authorization (server_error / access_denied).\n"
    "This almost always means your Spotify account is not on the app's allowlist "
    "while the app is in Development Mode.\n\n"
    "Fix:\n"
    "  1. Open your app at https://developer.spotify.com/dashboard\n"
    "  2. Go to User Management (Settings -> Users and Access)\n"
    "  3. Add the name + email of the exact Spotify account you log in with\n"
    "  4. Re-run: spotify-mcp-auth"
)


def auth_main() -> None:
    """CLI entry point: run the OAuth handshake once and cache the token."""
    logging.basicConfig(level=logging.INFO)
    auth_manager = build_auth_manager(open_browser=True)
    # Forces the interactive flow (spotipy starts a local server on the redirect port).
    try:
        token = auth_manager.get_access_token(as_dict=False)
    except SpotifyOauthError as e:
        message = str(e)
        if any(marker in message for marker in _ALLOWLIST_ERROR_MARKERS):
            print(_red(_ALLOWLIST_HELP))
        else:
            print(_red(f"Spotify authorization failed: {message}"))
        sys.exit(1)

    if token:
        print("Spotify authorization complete. Token cached.")
    else:
        print(_red("Spotify authorization failed. Check your credentials and redirect URI."))
        sys.exit(1)
