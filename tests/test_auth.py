from unittest.mock import MagicMock

import pytest
from spotipy.oauth2 import SpotifyOauthError

import spotify_mcp.auth as auth


def test_auth_main_server_error_shows_allowlist_help(monkeypatch, capsys):
    mgr = MagicMock()
    mgr.get_access_token.side_effect = SpotifyOauthError(
        "Received error from auth server: server_error")
    monkeypatch.setattr(auth, "build_auth_manager", lambda open_browser=False: mgr)

    with pytest.raises(SystemExit) as exc:
        auth.auth_main()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "User Management" in out
    assert "allowlist" in out


def test_auth_main_other_oauth_error_is_reported(monkeypatch, capsys):
    mgr = MagicMock()
    mgr.get_access_token.side_effect = SpotifyOauthError("invalid_client")
    monkeypatch.setattr(auth, "build_auth_manager", lambda open_browser=False: mgr)

    with pytest.raises(SystemExit):
        auth.auth_main()

    out = capsys.readouterr().out
    assert "authorization failed" in out.lower()
    assert "invalid_client" in out


def test_auth_main_success(monkeypatch, capsys):
    mgr = MagicMock()
    mgr.get_access_token.return_value = "tok123"
    monkeypatch.setattr(auth, "build_auth_manager", lambda open_browser=False: mgr)

    auth.auth_main()

    assert "complete" in capsys.readouterr().out.lower()


def test_get_client_is_cached(monkeypatch):
    auth.reset_client()
    fake_sp = MagicMock()
    monkeypatch.setattr(auth, "_build_spotify", lambda: fake_sp)

    c1 = auth.get_client()
    c2 = auth.get_client()

    assert c1 is c2                      # cached singleton
    assert c1.sp is fake_sp              # wraps the built spotipy client


def test_scopes_cover_new_features():
    joined = " ".join(auth.SCOPES)
    assert "user-library-modify" in joined
    assert "playlist-modify-private" in joined
    assert "user-modify-playback-state" in joined
