import functools
import logging
from typing import Callable, Optional, Dict, TypeVar

from . import parsers

logger = logging.getLogger(__name__)

T = TypeVar('T')


def validate(func: Callable[..., T]) -> Callable[..., T]:
    """Ensure auth is fresh and a device is available before calling a Spotify method.

    - Refreshes the token if expired.
    - Injects a candidate device into kwargs['device'] when no device is active.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.auth_ok():
            self.auth_refresh()
        if not self.is_active_device():
            kwargs['device'] = self._get_candidate_device()
        return func(self, *args, **kwargs)

    return wrapper


class SpotifyClient:
    """Facade over a configured spotipy.Spotify instance."""

    def __init__(self, sp):
        self.sp = sp
        self.auth_manager = sp.auth_manager
        self.cache_handler = self.auth_manager.cache_handler
        self.username = None

    # ----- identity -----
    @validate
    def set_username(self, device=None):
        self.username = self.sp.current_user()['display_name']

    # ----- search / info -----
    @validate
    def search(self, query: str, qtype: str = 'track', limit=10, device=None):
        if self.username is None:
            self.set_username()
        results = self.sp.search(q=query, limit=limit, type=qtype)
        if not results:
            raise ValueError("No search results found.")
        return parsers.parse_search_results(results, qtype, self.username)

    def get_info(self, item_uri: str) -> dict:
        _, qtype, item_id = item_uri.split(":")
        match qtype:
            case 'track':
                return parsers.parse_track(self.sp.track(item_id), detailed=True)
            case 'album':
                return parsers.parse_album(self.sp.album(item_id), detailed=True)
            case 'artist':
                artist_info = parsers.parse_artist(self.sp.artist(item_id), detailed=True)
                albums = self.sp.artist_albums(item_id)
                top_tracks = self.sp.artist_top_tracks(item_id)['tracks']
                parsed = parsers.parse_search_results(
                    {'albums': albums, 'tracks': {'items': top_tracks}},
                    qtype="album,track",
                )
                artist_info['top_tracks'] = parsed['tracks']
                artist_info['albums'] = parsed['albums']
                return artist_info
            case 'playlist':
                if self.username is None:
                    self.set_username()
                playlist = self.sp.playlist(item_id)
                return parsers.parse_playlist(playlist, self.username, detailed=True)
        raise ValueError(f"Unknown qtype {qtype}")

    # ----- playback -----
    def get_current_track(self) -> Optional[Dict]:
        current = self.sp.current_user_playing_track()
        if not current:
            logger.info("No playback session found")
            return None
        if current.get('currently_playing_type') != 'track':
            logger.info("Current playback is not a track")
            return None
        track_info = parsers.parse_track(current['item'])
        if 'is_playing' in current:
            track_info['is_playing'] = current['is_playing']
        return track_info

    @validate
    def start_playback(self, spotify_uri=None, device=None):
        if not spotify_uri:
            if self.is_track_playing():
                logger.info("No uri provided and playback already active.")
                return
            if not self.get_current_track():
                raise ValueError("No uri provided and no current playback to resume.")

        if spotify_uri is not None:
            if spotify_uri.startswith('spotify:track:'):
                uris, context_uri = [spotify_uri], None
            else:
                uris, context_uri = None, spotify_uri
        else:
            uris, context_uri = None, None

        device_id = device.get('id') if device else None
        return self.sp.start_playback(uris=uris, context_uri=context_uri, device_id=device_id)

    @validate
    def pause_playback(self, device=None):
        playback = self.sp.current_playback()
        if playback and playback.get('is_playing'):
            self.sp.pause_playback(device.get('id') if device else None)

    @validate
    def skip_track(self, n=1, device=None):
        for _ in range(n):
            self.sp.next_track()

    @validate
    def previous_track(self, device=None):
        self.sp.previous_track()

    @validate
    def seek_to_position(self, position_ms, device=None):
        self.sp.seek_track(position_ms=position_ms)

    @validate
    def set_volume(self, volume_percent, device=None):
        self.sp.volume(volume_percent)

    # ----- queue -----
    @validate
    def add_to_queue(self, track_id: str, device=None):
        self.sp.add_to_queue(track_id, device.get('id') if device else None)

    @validate
    def get_queue(self, device=None):
        queue_info = self.sp.queue()
        queue_info['currently_playing'] = self.get_current_track()
        queue_info['queue'] = [parsers.parse_track(track) for track in queue_info.pop('queue')]
        return queue_info

    # ----- library -----
    @validate
    def get_liked_tracks(self, limit=50, device=None) -> list:
        results = self.sp.current_user_saved_tracks(limit=limit)
        return [parsers.parse_track(item['track']) for item in results['items']]

    @validate
    def save_tracks(self, track_ids, device=None):
        self.sp.current_user_saved_tracks_add(tracks=track_ids)

    @validate
    def remove_tracks(self, track_ids, device=None):
        self.sp.current_user_saved_tracks_delete(tracks=track_ids)

    # ----- playlists -----
    @validate
    def get_playlists(self, limit=50, device=None) -> list:
        if self.username is None:
            self.set_username()
        results = self.sp.current_user_playlists(limit=limit)
        return [parsers.parse_playlist(p, self.username) for p in results['items']]

    @validate
    def create_playlist(self, name, public=False, description='', device=None) -> dict:
        if self.username is None:
            self.set_username()
        user_id = self.sp.current_user()['id']
        playlist = self.sp.user_playlist_create(
            user_id, name, public=public, description=description)
        return parsers.parse_playlist(playlist, self.username)

    @validate
    def playlist_add_tracks(self, playlist_id, track_ids, device=None):
        self.sp.playlist_add_items(playlist_id, track_ids)

    @validate
    def playlist_remove_tracks(self, playlist_id, track_ids, device=None):
        self.sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)

    # ----- devices / auth -----
    def is_track_playing(self) -> bool:
        curr_track = self.get_current_track()
        return bool(curr_track and curr_track.get('is_playing'))

    def get_devices(self) -> list:
        return self.sp.devices()['devices']

    def is_active_device(self) -> bool:
        return any(device.get('is_active') for device in self.get_devices())

    def _get_candidate_device(self):
        devices = self.get_devices()
        if not devices:
            raise ConnectionError("No active device. Is Spotify open?")
        for device in devices:
            if device.get('is_active'):
                return device
        logger.info("No active device, assigning %s.", devices[0]['name'])
        return devices[0]

    def auth_ok(self) -> bool:
        try:
            token = self.cache_handler.get_cached_token()
            if token is None:
                logger.info("Auth check: no token exists")
                return False
            return not self.auth_manager.is_token_expired(token)
        except Exception as e:
            logger.error("Error checking auth status: %s", e)
            return False

    def auth_refresh(self):
        self.auth_manager.validate_token(self.cache_handler.get_cached_token())
