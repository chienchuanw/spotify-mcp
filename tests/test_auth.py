from unittest.mock import MagicMock

import spotify_mcp.auth as auth


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
