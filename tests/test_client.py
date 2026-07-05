"""Exercises SpotifyClient methods against a mocked spotipy.Spotify.

Complements test_validate (decorator in isolation) and test_handlers (client
mocked out) by covering the real @validate + client-method interaction — in
particular that non-playback methods do NOT gate on an active device, and that
playback methods forward the resolved device_id.
"""
from unittest.mock import MagicMock

import pytest

from spotify_mcp.client import SpotifyClient


def make_client(sp):
    """Build a SpotifyClient over a mock sp with a valid, non-expired token."""
    sp.auth_manager.is_token_expired.return_value = False
    sp.auth_manager.cache_handler.get_cached_token.return_value = {'access_token': 'tok'}
    return SpotifyClient(sp)


# ----- non-playback methods must not require an active device -----
def test_get_playlists_works_with_no_devices():
    sp = MagicMock()
    sp.devices.return_value = {'devices': []}  # Spotify closed everywhere
    sp.current_user.return_value = {'display_name': 'me', 'id': 'uid'}
    sp.current_user_playlists.return_value = {'items': [
        {'name': 'P1', 'id': 'p1', 'owner': {'display_name': 'me'}},
    ]}
    client = make_client(sp)

    result = client.get_playlists()

    assert result[0]['name'] == 'P1'
    sp.devices.assert_not_called()  # no device probing for a library call


def test_save_tracks_works_with_no_devices():
    sp = MagicMock()
    sp.devices.return_value = {'devices': []}
    client = make_client(sp)

    client.save_tracks(['t1', 't2'])

    sp.current_user_saved_tracks_add.assert_called_once_with(tracks=['t1', 't2'])
    sp.devices.assert_not_called()


def test_create_playlist_works_with_no_devices():
    sp = MagicMock()
    sp.devices.return_value = {'devices': []}
    sp.current_user.return_value = {'display_name': 'me', 'id': 'uid'}
    sp.user_playlist_create.return_value = {'name': 'New', 'id': 'p9', 'owner': {'display_name': 'me'}}
    client = make_client(sp)

    result = client.create_playlist('New')

    assert result['id'] == 'p9'
    sp.user_playlist_create.assert_called_once()
    sp.devices.assert_not_called()


# ----- playback methods forward the resolved device_id -----
@pytest.fixture
def inactive_device_client():
    sp = MagicMock()
    # A device exists but is not active -> validate should inject it as candidate.
    sp.devices.return_value = {'devices': [{'id': 'devX', 'name': 'Phone', 'is_active': False}]}
    # get_current_track path returns nothing playing.
    sp.current_user_playing_track.return_value = None
    return make_client(sp), sp


def test_previous_track_forwards_device_id(inactive_device_client):
    client, sp = inactive_device_client
    client.previous_track()
    sp.previous_track.assert_called_once_with('devX')


def test_seek_forwards_device_id(inactive_device_client):
    client, sp = inactive_device_client
    client.seek_to_position(5000)
    sp.seek_track.assert_called_once_with(position_ms=5000, device_id='devX')


def test_set_volume_forwards_device_id(inactive_device_client):
    client, sp = inactive_device_client
    client.set_volume(30)
    sp.volume.assert_called_once_with(30, 'devX')


def test_skip_forwards_device_id(inactive_device_client):
    client, sp = inactive_device_client
    client.skip_track(n=2)
    assert sp.next_track.call_count == 2
    sp.next_track.assert_called_with('devX')
