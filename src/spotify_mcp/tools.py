import json
import logging
from typing import Callable, Optional

import mcp.types as types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolModel(BaseModel):
    @classmethod
    def as_tool(cls):
        return types.Tool(
            name="Spotify" + cls.__name__,
            description=cls.__doc__,
            inputSchema=cls.model_json_schema(),
        )


# ----- tool schemas -----
class Playback(ToolModel):
    """Manage playback: get current track, start/resume, pause, skip, previous, seek, set volume.
    - get: info about the current track.
    - start: play spotify_uri, or resume if omitted.
    - pause / skip / previous.
    - seek: jump to position_ms.
    - volume: set volume_percent (0-100).
    """
    action: str = Field(description="One of: get, start, pause, skip, previous, seek, volume.")
    spotify_uri: Optional[str] = Field(default=None, description="URI for 'start'. If omitted, resumes.")
    num_skips: Optional[int] = Field(default=1, description="Number of tracks to skip for 'skip'.")
    position_ms: Optional[int] = Field(default=None, description="Target position for 'seek', in ms.")
    volume_percent: Optional[int] = Field(default=None, description="Volume 0-100 for 'volume'.")


class Search(ToolModel):
    """Search for tracks, albums, artists, or playlists on Spotify."""
    query: str = Field(description="query term")
    qtype: Optional[str] = Field(default="track", description="track, album, artist, playlist, or comma-separated.")
    limit: Optional[int] = Field(default=10, description="Max number of items to return.")


class Queue(ToolModel):
    """Manage the playback queue - get the queue or add a track."""
    action: str = Field(description="'add' or 'get'.")
    track_id: Optional[str] = Field(default=None, description="Track ID to add (required for 'add').")


class GetInfo(ToolModel):
    """Get detailed info about a Spotify item (track, album, artist, or playlist)."""
    item_uri: str = Field(description="URI like 'spotify:track:...'. artist->albums+top tracks; album/playlist->tracks.")


class Library(ToolModel):
    """Manage saved (liked) tracks.
    - get_liked: list saved tracks.
    - save / remove: add or remove track_ids from the library.
    """
    action: str = Field(description="'get_liked', 'save', or 'remove'.")
    track_ids: Optional[list[str]] = Field(default=None, description="Track IDs for 'save'/'remove'.")
    limit: Optional[int] = Field(default=50, description="Max items for 'get_liked'.")


class Playlist(ToolModel):
    """Manage playlists.
    - list: the current user's playlists.
    - create: make a new playlist (name required).
    - add_tracks / remove_tracks: modify a playlist's items (playlist_id + track_ids required).
    - delete: remove a playlist from your library (playlist_id required). Spotify has
      no hard delete; this unfollows it, which removes owned playlists from your view.
    """
    action: str = Field(description="'list', 'create', 'add_tracks', 'remove_tracks', or 'delete'.")
    playlist_id: Optional[str] = Field(default=None, description="Playlist ID for add/remove.")
    track_ids: Optional[list[str]] = Field(default=None, description="Track IDs for add/remove.")
    name: Optional[str] = Field(default=None, description="Name for 'create'.")
    public: Optional[bool] = Field(default=False, description="Whether a created playlist is public.")
    description: Optional[str] = Field(default="", description="Description for 'create'.")


# ----- helpers -----
def _text(s: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=s)]


def _json(obj) -> list[types.TextContent]:
    return _text(json.dumps(obj, indent=2))


# ----- handlers -----
def handle_playback(client, arguments: dict) -> list[types.TextContent]:
    action = arguments.get("action")
    match action:
        case "get":
            track = client.get_current_track()
            return _json(track) if track else _text("No track playing.")
        case "start":
            client.start_playback(spotify_uri=arguments.get("spotify_uri"))
            return _text("Playback starting.")
        case "pause":
            client.pause_playback()
            return _text("Playback paused.")
        case "skip":
            client.skip_track(n=int(arguments.get("num_skips", 1)))
            return _text("Skipped to next track.")
        case "previous":
            client.previous_track()
            return _text("Skipped to previous track.")
        case "seek":
            position_ms = arguments.get("position_ms")
            if position_ms is None:
                return _text("position_ms is required for seek action.")
            client.seek_to_position(int(position_ms))
            return _text(f"Seeked to {position_ms} ms.")
        case "volume":
            volume = arguments.get("volume_percent")
            if volume is None:
                return _text("volume_percent is required for volume action.")
            client.set_volume(int(volume))
            return _text(f"Volume set to {volume}.")
        case _:
            return _text(f"Unknown playback action: {action}.")


def handle_search(client, arguments: dict) -> list[types.TextContent]:
    results = client.search(
        query=arguments.get("query", ""),
        qtype=arguments.get("qtype", "track"),
        limit=arguments.get("limit", 10),
    )
    return _json(results)


def handle_queue(client, arguments: dict) -> list[types.TextContent]:
    action = arguments.get("action")
    match action:
        case "add":
            track_id = arguments.get("track_id")
            if not track_id:
                return _text("track_id is required for add action.")
            client.add_to_queue(track_id)
            return _text("Track added to queue.")
        case "get":
            return _json(client.get_queue())
        case _:
            return _text(f"Unknown queue action: {action}. Supported: add, get.")


def handle_getinfo(client, arguments: dict) -> list[types.TextContent]:
    return _json(client.get_info(item_uri=arguments.get("item_uri")))


def handle_library(client, arguments: dict) -> list[types.TextContent]:
    action = arguments.get("action")
    match action:
        case "get_liked":
            return _json(client.get_liked_tracks(limit=arguments.get("limit", 50)))
        case "save":
            track_ids = arguments.get("track_ids")
            if not track_ids:
                return _text("track_ids is required for save action.")
            client.save_tracks(track_ids)
            return _text(f"Saved {len(track_ids)} track(s) to library.")
        case "remove":
            track_ids = arguments.get("track_ids")
            if not track_ids:
                return _text("track_ids is required for remove action.")
            client.remove_tracks(track_ids)
            return _text(f"Removed {len(track_ids)} track(s) from library.")
        case _:
            return _text(f"Unknown library action: {action}. Supported: get_liked, save, remove.")


def handle_playlist(client, arguments: dict) -> list[types.TextContent]:
    action = arguments.get("action")
    match action:
        case "list":
            return _json(client.get_playlists(limit=arguments.get("limit", 50)))
        case "create":
            name = arguments.get("name")
            if not name:
                return _text("name is required for create action.")
            playlist = client.create_playlist(
                name,
                public=arguments.get("public", False),
                description=arguments.get("description", ""),
            )
            return _json(playlist)
        case "add_tracks":
            playlist_id = arguments.get("playlist_id")
            track_ids = arguments.get("track_ids")
            if not playlist_id or not track_ids:
                return _text("playlist_id and track_ids are required for add_tracks action.")
            client.playlist_add_tracks(playlist_id, track_ids)
            return _text(f"Added {len(track_ids)} track(s) to playlist.")
        case "remove_tracks":
            playlist_id = arguments.get("playlist_id")
            track_ids = arguments.get("track_ids")
            if not playlist_id or not track_ids:
                return _text("playlist_id and track_ids are required for remove_tracks action.")
            client.playlist_remove_tracks(playlist_id, track_ids)
            return _text(f"Removed {len(track_ids)} track(s) from playlist.")
        case "delete":
            playlist_id = arguments.get("playlist_id")
            if not playlist_id:
                return _text("playlist_id is required for delete action.")
            client.delete_playlist(playlist_id)
            return _text("Playlist removed from your library.")
        case _:
            return _text(f"Unknown playlist action: {action}. Supported: list, create, add_tracks, remove_tracks, delete.")


TOOL_MODELS = [Playback, Search, Queue, GetInfo, Library, Playlist]

HANDLERS: dict[str, Callable] = {
    "SpotifyPlayback": handle_playback,
    "SpotifySearch": handle_search,
    "SpotifyQueue": handle_queue,
    "SpotifyGetInfo": handle_getinfo,
    "SpotifyLibrary": handle_library,
    "SpotifyPlaylist": handle_playlist,
}
