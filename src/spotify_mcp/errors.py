import logging

from requests import RequestException
from spotipy import SpotifyException

logger = logging.getLogger(__name__)


def format_error(exc: Exception) -> str:
    """Turn an exception into a concise, user-facing message for a TextContent reply."""
    if isinstance(exc, SpotifyException):
        text = str(exc)
        if "NO_ACTIVE_DEVICE" in text or "device" in text.lower():
            return f"Spotify API error: {text}. Please make sure Spotify is open on a device."
        return f"Spotify API error: {text}"
    if isinstance(exc, RequestException):
        return f"Network error contacting Spotify: {exc}"
    return f"Unexpected error: {exc}"
