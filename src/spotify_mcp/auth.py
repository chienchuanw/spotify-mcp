import logging
import os

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

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


def auth_main() -> None:
    """CLI entry point: run the OAuth handshake once and cache the token."""
    logging.basicConfig(level=logging.INFO)
    auth_manager = build_auth_manager(open_browser=True)
    # Forces the interactive flow (spotipy starts a local server on the redirect port).
    token = auth_manager.get_access_token(as_dict=False)
    if token:
        print("Spotify authorization complete. Token cached.")
    else:
        print("Spotify authorization failed. Check your credentials and redirect URI.")
