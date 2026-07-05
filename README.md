# spotify-mcp

An MCP (Model Context Protocol) server that lets an AI agent such as Claude control Spotify — playback, search, queue, library, and playlists — through the Spotify Web API. Built on [spotipy](https://github.com/spotipy-dev/spotipy/tree/2.24.0).

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Available tools](#available-tools)
- [Demo](#demo)
- [Getting started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Create a Spotify app](#create-a-spotify-app)
  - [Install and register the server](#install-and-register-the-server)
  - [Configuration](#configuration)
  - [First-time authorization](#first-time-authorization)
- [Project structure](#project-structure)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

spotify-mcp exposes Spotify as a set of MCP tools so that an agent can start and control playback, search the catalog, manage the queue, curate your saved tracks, and build playlists on your behalf. It runs locally over stdio and talks to Spotify using your own developer credentials.

The server is organized into small, single-responsibility modules and authenticates lazily: it starts without contacting Spotify and only builds an authenticated client the first time a tool is actually called. A separate CLI command handles the one-time OAuth authorization, so the server itself never needs an interactive browser flow.

This is a personal, actively-maintained fork of [varunneal/spotify-mcp](https://github.com/varunneal/spotify-mcp).

## Features

- Playback control: start, pause, skip, previous, seek, and set volume
- Search for tracks, albums, artists, and playlists
- Get detailed info about a track, album, artist, or playlist
- Manage the playback queue (add, get)
- Manage your library: list, save, and remove liked tracks
- Manage playlists: list, create, add/remove tracks, and delete
- Lazy authentication with a dedicated `spotify-mcp-auth` CLI for first-time login

## Available tools

The server exposes six domain-grouped tools. Most take an `action` argument.

| Tool | Actions | Notes |
|------|---------|-------|
| `SpotifyPlayback` | `get`, `start`, `pause`, `skip`, `previous`, `seek`, `volume` | `start` plays a `spotify_uri` or resumes; `seek` needs `position_ms`; `volume` needs `volume_percent` (0–100). Requires an active device and Premium. |
| `SpotifyQueue` | `add`, `get` | `add` needs `track_id`. |
| `SpotifySearch` | — | `query` (required), `qtype` (track/album/artist/playlist or comma-separated), `limit`. |
| `SpotifyGetInfo` | — | `item_uri` (required). Artist resolves to albums + top tracks; album/playlist resolve to their tracks. |
| `SpotifyLibrary` | `get_liked`, `save`, `remove` | `save`/`remove` need `track_ids`. |
| `SpotifyPlaylist` | `list`, `create`, `add_tracks`, `remove_tracks`, `delete` | `create` needs `name`; track ops need `playlist_id` + `track_ids`; `delete` unfollows the playlist (Spotify has no hard delete). |

Playback and queue actions target the active Spotify device and require Premium. Search, get-info, library, and playlist management work without an open device.

## Demo

Make sure to turn on audio.

<details>
  <summary>Video</summary>
  https://github.com/user-attachments/assets/20ee1f92-f3e3-4dfa-b945-ca57bc1e0894
</details>

## Getting started

### Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) (recommended `>= 0.54`)
- A Spotify account. Spotify Premium is required for playback control (search, library, and playlist management work without Premium).
- A Spotify developer application (see below)

### Create a Spotify app

1. Sign in at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and create an app.
2. Set the redirect URI to `http://127.0.0.1:8888`. You may choose any port, but Spotify now requires the loopback IP `127.0.0.1` for HTTP redirects — `localhost` is rejected as insecure.
3. Under the app's API settings, enable **Web API**.
4. While the app is in Development Mode, add the Spotify account you will authorize with under **User Management**. Accounts that are not on this list are rejected during authorization with a `server_error`.
5. Copy the Client ID and Client Secret.

### Install and register the server

Clone the repository:

```bash
git clone https://github.com/chienchuanw/spotify-mcp.git
```

Register it as an MCP server in your client. For the Claude desktop app, edit the config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

```json
"spotify": {
  "command": "uv",
  "args": [
    "--directory",
    "/path/to/spotify-mcp",
    "run",
    "spotify-mcp"
  ],
  "env": {
    "SPOTIFY_CLIENT_ID": "YOUR_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET": "YOUR_CLIENT_SECRET",
    "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888"
  }
}
```

### Configuration

The server reads three variables, from the MCP client `env` block above or from a `.env` file in the project root:

| Variable | Required | Description |
|----------|----------|-------------|
| `SPOTIFY_CLIENT_ID` | yes | Client ID from your Spotify app |
| `SPOTIFY_CLIENT_SECRET` | yes | Client Secret from your Spotify app |
| `SPOTIFY_REDIRECT_URI` | yes | Must exactly match the redirect URI configured in the dashboard, e.g. `http://127.0.0.1:8888` |

Example `.env`:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888
```

### First-time authorization

Because the MCP server communicates over stdio, it cannot run the interactive OAuth flow itself. Authorize once with the bundled CLI, which opens your browser and captures the redirect on a local server:

```bash
uv --directory /path/to/spotify-mcp run spotify-mcp-auth
```

This caches an access/refresh token. The server then reads that cached token and refreshes it automatically. Re-run `spotify-mcp-auth` only if you revoke access or change scopes. If your account is not on the app's allowlist, the command prints guidance on how to fix it instead of a traceback.

## Project structure

```
src/spotify_mcp/
  __init__.py   entry points: main() (server) and auth_main() (auth CLI)
  server.py     MCP wiring — list_tools / call_tool dispatch to the registry
  tools.py      tool schemas (Pydantic) + per-domain handlers + registry
  client.py     SpotifyClient facade over spotipy + the @validate decorator
  parsers.py    pure functions that narrow Spotify's verbose JSON
  auth.py       OAuth config, SCOPES, lazy get_client() factory, auth CLI
  errors.py     exception -> user-facing message formatting
tests/          pytest suite, mocks spotipy (no network, no credentials)
docs/           design spec, implementation plan, and session status files
```

Key design points:

- **Lazy auth** — the Spotify client is built on first use via `get_client()`, never at import time, so the server starts without credentials and only touches Spotify when a tool is called.
- **`@validate`** — decorates playback/queue methods to refresh the token if expired and inject a candidate device when none is active. Catalog, library, and playlist calls are intentionally undecorated because they need no device.
- **Layered boundaries** — `server` knows nothing of Spotify, `tools` handlers know nothing of the MCP session, and `client` knows nothing of MCP types. Each layer is unit-testable in isolation.

## Development

Install dependencies (including the `dev` group) and run the test suite:

```bash
uv sync
uv run pytest
```

The tests mock `spotipy` and never touch the real Spotify API, so no credentials are needed to run them.

You can also inspect the server interactively with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/spotify-mcp run spotify-mcp
```

## Troubleshooting

- Make sure `uv` is up to date (`>= 0.54` recommended).
- Ensure the client has execution permissions for the project: `chmod -R 755 /path/to/spotify-mcp`.
- Playback control requires Spotify Premium and an active device — open Spotify (desktop app, phone app, or the web player at [open.spotify.com](https://open.spotify.com)) and start playing so a device is available.
- `redirect_uri: insecure` during authorization means you are using `localhost`; switch both the dashboard and `SPOTIFY_REDIRECT_URI` to `http://127.0.0.1:8888`.
- `server_error` / `access_denied` during authorization usually means your account is not on the app's User Management allowlist while the app is in Development Mode.
- The server logs to stderr per the MCP spec. On macOS, the Claude desktop app writes these to `~/Library/Logs/Claude`. See the [MCP logging docs](https://modelcontextprotocol.io/quickstart/user#getting-logs-from-claude-for-desktop) for other platforms.

## Contributing

Contributions are welcome. Fork the repository, create a feature branch off `dev`, run the test suite (`uv run pytest`), and open a pull request against `dev`.

Deprecated Spotify recommendation endpoints are out of scope. Possible future work includes paginated search/playlist/album results and a deployment story for ephemeral (`uvx`) usage.

## License

Released under the [MIT License](LICENSE). This project is derived from the original [spotify-mcp](https://github.com/varunneal/spotify-mcp) by Varun Srivastava, also MIT-licensed; the original copyright notice is retained in the `LICENSE` file.
