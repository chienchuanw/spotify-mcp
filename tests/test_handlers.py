import json
from unittest.mock import MagicMock

from spotify_mcp import tools


def _text(result):
    assert len(result) == 1
    return result[0].text


def test_playback_get_returns_track():
    client = MagicMock()
    client.get_current_track.return_value = {'name': 'Song A'}
    out = _text(tools.handle_playback(client, {'action': 'get'}))
    assert json.loads(out)['name'] == 'Song A'


def test_playback_get_no_track():
    client = MagicMock()
    client.get_current_track.return_value = None
    out = _text(tools.handle_playback(client, {'action': 'get'}))
    assert "No track" in out


def test_playback_skip_uses_num_skips():
    client = MagicMock()
    tools.handle_playback(client, {'action': 'skip', 'num_skips': 3})
    client.skip_track.assert_called_once_with(n=3)


def test_playback_seek_requires_position():
    client = MagicMock()
    out = _text(tools.handle_playback(client, {'action': 'seek'}))
    assert "position_ms" in out
    client.seek_to_position.assert_not_called()


def test_playback_volume_calls_client():
    client = MagicMock()
    tools.handle_playback(client, {'action': 'volume', 'volume_percent': 40})
    client.set_volume.assert_called_once_with(40)


def test_playback_unknown_action():
    client = MagicMock()
    out = _text(tools.handle_playback(client, {'action': 'nope'}))
    assert "Unknown" in out


def test_queue_add_requires_track_id():
    client = MagicMock()
    out = _text(tools.handle_queue(client, {'action': 'add'}))
    assert "track_id" in out
    client.add_to_queue.assert_not_called()


def test_library_save_requires_ids():
    client = MagicMock()
    out = _text(tools.handle_library(client, {'action': 'save'}))
    assert "track_ids" in out


def test_library_get_liked():
    client = MagicMock()
    client.get_liked_tracks.return_value = [{'name': 'S'}]
    out = _text(tools.handle_library(client, {'action': 'get_liked'}))
    assert json.loads(out)[0]['name'] == 'S'


def test_playlist_create_requires_name():
    client = MagicMock()
    out = _text(tools.handle_playlist(client, {'action': 'create'}))
    assert "name" in out


def test_playlist_add_tracks_calls_client():
    client = MagicMock()
    tools.handle_playlist(client, {
        'action': 'add_tracks', 'playlist_id': 'p1', 'track_ids': ['t1', 't2']})
    client.playlist_add_tracks.assert_called_once_with('p1', ['t1', 't2'])


def test_playlist_delete_requires_id():
    client = MagicMock()
    out = _text(tools.handle_playlist(client, {'action': 'delete'}))
    assert "playlist_id" in out
    client.delete_playlist.assert_not_called()


def test_playlist_delete_calls_client():
    client = MagicMock()
    out = _text(tools.handle_playlist(client, {'action': 'delete', 'playlist_id': 'p1'}))
    client.delete_playlist.assert_called_once_with('p1')
    assert "removed" in out.lower()


def test_registry_has_all_tools():
    names = {m.as_tool().name for m in tools.TOOL_MODELS}
    assert names == set(tools.HANDLERS.keys())
    assert "SpotifyPlayback" in names
    assert "SpotifyPlaylist" in names
