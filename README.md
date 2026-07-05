# spotify-mcp MCP server

MCP project to connect Claude with Spotify. Built on top of [spotipy-dev's API](https://github.com/spotipy-dev/spotipy/tree/2.24.0).

## Features
- Start, pause, skip, go to previous, seek, and set volume
- Search for tracks/albums/artists/playlists
- Get info about a track/album/artist/playlist
- Manage the Spotify queue
- Manage your library (list/save/remove liked tracks)
- Manage playlists (list, create, add/remove tracks, delete)

## Available tools

The server exposes six domain-grouped tools. Most take an `action` argument.

| Tool | Actions | Notes |
|------|---------|-------|
| `SpotifyPlayback` | `get`, `start`, `pause`, `skip`, `previous`, `seek`, `volume` | `start` plays a `spotify_uri` or resumes; `seek` needs `position_ms`; `volume` needs `volume_percent` (0–100). Requires an active device + Premium. |
| `SpotifyQueue` | `add`, `get` | `add` needs `track_id`. |
| `SpotifySearch` | — | `query` (required), `qtype` (track/album/artist/playlist or comma-separated), `limit`. |
| `SpotifyGetInfo` | — | `item_uri` (required). Artist → albums + top tracks; album/playlist → tracks. |
| `SpotifyLibrary` | `get_liked`, `save`, `remove` | `save`/`remove` need `track_ids`. |
| `SpotifyPlaylist` | `list`, `create`, `add_tracks`, `remove_tracks`, `delete` | `create` needs `name`; track ops need `playlist_id` + `track_ids`; `delete` unfollows the playlist (Spotify has no hard delete). |

Playback/queue actions target the active Spotify device and require Premium. Search, get-info, library, and playlist management work without an open device.

## Demo

Make sure to turn on audio

<details>
  <summary>
    Video
  </summary>
  https://github.com/user-attachments/assets/20ee1f92-f3e3-4dfa-b945-ca57bc1e0894
  </summary>
</details>

## Configuration

### Getting Spotify API Keys
Create an account on [developer.spotify.com](https://developer.spotify.com/). Navigate to [the dashboard](https://developer.spotify.com/dashboard). 
Create an app with redirect_uri as http://127.0.0.1:8888. (You can choose any port you want, but Spotify now requires the loopback IP `127.0.0.1` for http redirects — `localhost` is rejected as insecure.) 
I set "APIs used" to "Web Playback SDK".

### Run this project locally
This project is not yet set up for ephemeral environments (e.g. `uvx` usage). 
Run this project locally by cloning this repo

```bash
git clone https://github.com/chienchuanw/spotify-mcp.git
```

Add this tool as a mcp server.

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`

On Windows: `%APPDATA%/Claude/claude_desktop_config.json`


  ```json
  "spotify": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/spotify_mcp",
        "run",
        "spotify-mcp"
      ],
      "env": {
        "SPOTIFY_CLIENT_ID": YOUR_CLIENT_ID,
        "SPOTIFY_CLIENT_SECRET": YOUR_CLIENT_SECRET,
        "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888"
      }
    }
  ```

### First-time authorization

Because the MCP server communicates over stdio, it cannot run the interactive
OAuth flow itself. Authorize once with the bundled CLI, which opens your browser
and captures the redirect on a local server:

```bash
uv --directory /path/to/spotify_mcp run spotify-mcp-auth
```

This caches an access/refresh token. The MCP server then reads that cached token
and refreshes it automatically. Re-run `spotify-mcp-auth` only if you revoke
access or change scopes.

### Troubleshooting
Please open an issue if you can't get this MCP working. Here are some tips:
1. Make sure `uv` is updated. I recommend version `>=0.54`.
2. Make sure claude has execution permisisons for the project: `chmod -R 755`.
3. Ensure you have Spotify premium (needed for running developer API). 

This MCP will emit logs to std err (as specified in the MCP) spec. On Mac the Claude Desktop app should emit these logs
to `~/Library/Logs/Claude`. 
On other platforms [you can find logs here](https://modelcontextprotocol.io/quickstart/user#getting-logs-from-claude-for-desktop).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/spotify_mcp run spotify-mcp
```

Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.


## TODO

Unfortunately, a bunch of cool features have [now been deprecated](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/) 
from the Spotify API. Most new features will be relatively minor or for the health of the project:
- adding API support for paginated search results/playlists/albums.

PRs appreciated! 

## Architecture

The package is organized into focused, single-responsibility modules:

```
src/spotify_mcp/
  __init__.py   entry points: main() (server) and auth_main() (auth CLI)
  server.py     MCP wiring — list_tools / call_tool dispatch to the registry
  tools.py      tool schemas (Pydantic) + per-domain handlers + registry
  client.py     SpotifyClient facade over spotipy + the @validate decorator
  parsers.py    pure functions that narrow Spotify's verbose JSON
  auth.py       OAuth config, SCOPES, lazy get_client() factory, auth CLI
  errors.py     exception -> user-facing message formatting
```

Key design points:

- **Lazy auth** — the Spotify client is built on first use via `get_client()`, never at import time, so the server starts without credentials and only touches Spotify when a tool is called.
- **`@validate`** — decorates playback/queue methods to refresh the token if expired and inject a candidate device when none is active. Catalog/library/playlist calls are intentionally undecorated (they need no device).
- **Layered boundaries** — `server` knows nothing of Spotify; `tools` handlers know nothing of the MCP session; `client` knows nothing of MCP types. Each layer is unit-testable in isolation.

## Development

Install dependencies (including the `dev` group) and run the test suite:

```bash
uv sync
uv run pytest
```

Tests mock `spotipy` and never touch the real Spotify API, so no credentials are needed to run them.

## Deployment

(todo)

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

This will create source and wheel distributions in the `dist/` directory.

3. Publish to PyPI:
```bash
uv publish
```

Note: You'll need to set PyPI credentials via environment variables or command flags:
- Token: `--token` or `UV_PUBLISH_TOKEN`
- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`
