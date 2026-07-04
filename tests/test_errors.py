from requests import RequestException
from spotipy import SpotifyException

from spotify_mcp.errors import format_error


def test_format_spotify_exception():
    exc = SpotifyException(404, -1, "not found")
    msg = format_error(exc)
    assert "Spotify API error" in msg


def test_format_no_active_device_hint():
    exc = SpotifyException(404, -1, "NO_ACTIVE_DEVICE")
    msg = format_error(exc)
    assert "Spotify" in msg and ("open" in msg.lower() or "開啟" in msg)


def test_format_request_exception():
    msg = format_error(RequestException("timeout"))
    assert "Network error" in msg


def test_format_generic_exception():
    msg = format_error(ValueError("boom"))
    assert "Unexpected error" in msg
    assert "boom" in msg
