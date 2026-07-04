import os

import pytest

# Provide dummy Spotify credentials so importing the package (which, until the
# lazy-init refactor lands, constructs a SpotifyOAuth at import time) never
# depends on real credentials or the network. setdefault leaves a real dev
# environment untouched. SpotifyOAuth construction makes no network calls.
os.environ.setdefault("SPOTIFY_CLIENT_ID", "test-client-id")
os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("SPOTIFY_REDIRECT_URI", "http://localhost:8888")


@pytest.fixture
def track_dict():
    return {
        'name': 'Song A',
        'id': 'track1',
        'artists': [{'name': 'Artist X', 'id': 'artist1'}],
        'album': {
            'name': 'Album A',
            'id': 'album1',
            'artists': [{'name': 'Artist X', 'id': 'artist1'}],
        },
        'track_number': 3,
        'duration_ms': 210000,
    }


@pytest.fixture
def album_dict():
    return {
        'name': 'Album A',
        'id': 'album1',
        'artists': [{'name': 'Artist X', 'id': 'artist1'}],
        'total_tracks': 2,
        'release_date': '2020-01-01',
        'genres': [],
        'tracks': {'items': [
            {'name': 'Song A', 'id': 'track1', 'artists': [{'name': 'Artist X', 'id': 'artist1'}]},
            {'name': 'Song B', 'id': 'track2', 'artists': [{'name': 'Artist X', 'id': 'artist1'}]},
        ]},
    }
