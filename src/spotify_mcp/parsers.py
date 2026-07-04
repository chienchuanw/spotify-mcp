from collections import defaultdict
from typing import Optional, Dict
from urllib.parse import quote


def parse_track(track_item: dict, detailed: bool = False) -> Optional[dict]:
    if not track_item:
        return None
    narrowed_item = {
        'name': track_item['name'],
        'id': track_item['id'],
    }

    if 'is_playing' in track_item:
        narrowed_item['is_playing'] = track_item['is_playing']

    if detailed:
        narrowed_item['album'] = parse_album(track_item.get('album'))
        for k in ['track_number', 'duration_ms']:
            narrowed_item[k] = track_item.get(k)

    if not track_item.get('is_playable', True):
        narrowed_item['is_playable'] = False

    artists = [a['name'] for a in track_item['artists']]
    if detailed:
        artists = [parse_artist(a) for a in track_item['artists']]

    if len(artists) == 1:
        narrowed_item['artist'] = artists[0]
    else:
        narrowed_item['artists'] = artists

    return narrowed_item


def parse_artist(artist_item: dict, detailed: bool = False) -> Optional[dict]:
    if not artist_item:
        return None
    narrowed_item = {
        'name': artist_item['name'],
        'id': artist_item['id'],
    }
    if detailed:
        narrowed_item['genres'] = artist_item.get('genres')
    return narrowed_item


def parse_playlist(playlist_item: dict, username, detailed: bool = False) -> Optional[dict]:
    if not playlist_item:
        return None
    narrowed_item = {
        'name': playlist_item['name'],
        'id': playlist_item['id'],
        'owner': playlist_item['owner']['display_name'],
        'user_is_owner': playlist_item['owner']['display_name'] == username,
    }
    if detailed:
        narrowed_item['description'] = playlist_item.get('description')
        tracks = []
        for t in playlist_item['tracks']['items']:
            tracks.append(parse_track(t['track']))
        narrowed_item['tracks'] = tracks
    return narrowed_item


def parse_album(album_item: dict, detailed: bool = False) -> dict:
    narrowed_item = {
        'name': album_item['name'],
        'id': album_item['id'],
    }

    artists = [a['name'] for a in album_item['artists']]

    if detailed:
        tracks = []
        for t in album_item['tracks']['items']:
            tracks.append(parse_track(t))
        narrowed_item["tracks"] = tracks
        artists = [parse_artist(a) for a in album_item['artists']]

        for k in ['total_tracks', 'release_date', 'genres']:
            narrowed_item[k] = album_item.get(k)

    if len(artists) == 1:
        narrowed_item['artist'] = artists[0]
    else:
        narrowed_item['artists'] = artists

    return narrowed_item


def parse_search_results(results: Dict, qtype: str, username: Optional[str] = None):
    _results = defaultdict(list)
    for q in qtype.split(","):
        match q:
            case "track":
                for item in results['tracks']['items']:
                    if not item:
                        continue
                    _results['tracks'].append(parse_track(item))
            case "artist":
                for item in results['artists']['items']:
                    if not item:
                        continue
                    _results['artists'].append(parse_artist(item))
            case "playlist":
                for item in results['playlists']['items']:
                    if not item:
                        continue
                    _results['playlists'].append(parse_playlist(item, username))
            case "album":
                for item in results['albums']['items']:
                    if not item:
                        continue
                    _results['albums'].append(parse_album(item))
            case _:
                raise ValueError(f"Unknown qtype {qtype}")
    return dict(_results)


def build_search_query(base_query: str,
                       artist: Optional[str] = None,
                       track: Optional[str] = None,
                       album: Optional[str] = None,
                       year: Optional[str] = None,
                       year_range: Optional[tuple[int, int]] = None,
                       genre: Optional[str] = None,
                       is_hipster: bool = False,
                       is_new: bool = False) -> str:
    """Build a Spotify search query string with optional filters (currently unused)."""
    filters = []
    if artist:
        filters.append(f"artist:{artist}")
    if track:
        filters.append(f"track:{track}")
    if album:
        filters.append(f"album:{album}")
    if year:
        filters.append(f"year:{year}")
    if year_range:
        filters.append(f"year:{year_range[0]}-{year_range[1]}")
    if genre:
        filters.append(f"genre:{genre}")
    if is_hipster:
        filters.append("tag:hipster")
    if is_new:
        filters.append("tag:new")
    query_parts = [base_query] + filters
    return quote(" ".join(query_parts))
