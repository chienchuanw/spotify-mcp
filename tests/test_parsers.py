from spotify_mcp import parsers


def test_parse_track_basic(track_dict):
    result = parsers.parse_track(track_dict)
    assert result['name'] == 'Song A'
    assert result['id'] == 'track1'
    assert result['artist'] == 'Artist X'   # single artist -> 'artist'
    assert 'album' not in result            # not detailed


def test_parse_track_detailed(track_dict):
    result = parsers.parse_track(track_dict, detailed=True)
    assert result['album']['name'] == 'Album A'
    assert result['duration_ms'] == 210000
    assert result['track_number'] == 3
    assert result['artist']['name'] == 'Artist X'  # detailed -> parsed artist dict


def test_parse_track_multiple_artists():
    item = {'name': 'S', 'id': 'i', 'artists': [{'name': 'A', 'id': '1'}, {'name': 'B', 'id': '2'}]}
    result = parsers.parse_track(item)
    assert result['artists'] == ['A', 'B']  # plural key


def test_parse_track_none_returns_none():
    assert parsers.parse_track(None) is None


def test_parse_track_unplayable_flag():
    item = {'name': 'S', 'id': 'i', 'is_playable': False, 'artists': [{'name': 'A', 'id': '1'}]}
    assert parsers.parse_track(item)['is_playable'] is False


def test_parse_album_detailed(album_dict):
    result = parsers.parse_album(album_dict, detailed=True)
    assert result['total_tracks'] == 2
    assert len(result['tracks']) == 2
    assert result['artist']['name'] == 'Artist X'


def test_parse_search_results_tracks(track_dict):
    results = {'tracks': {'items': [track_dict, None]}}  # None filtered out
    parsed = parsers.parse_search_results(results, 'track')
    assert len(parsed['tracks']) == 1
    assert parsed['tracks'][0]['name'] == 'Song A'
