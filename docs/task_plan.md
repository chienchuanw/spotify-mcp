# Task Plan — spotify-mcp restructure & feature work

**Status:** ✅ Complete (2026-07-05). All work merged into `dev`.

## Goal

Understand and refactor the spotify-mcp server (agent-controlled Spotify over MCP)
from a personal-fork standpoint: clean up + stabilize, restructure into layers,
extend features, and add a test base.

## Scope & status

| Area | Item | Status |
|------|------|:-:|
| Restructure | Split into server / tools / client / parsers / auth / errors modules | ✅ |
| Restructure | Remove `spotify_api.py` + `utils.py`; kill dead code | ✅ |
| Stability | Lazy OAuth client (`get_client()`) — no import-time auth | ✅ |
| Stability | stdlib logging, unified `format_error`, unused-import sweep | ✅ |
| Auth | `spotify-mcp-auth` CLI for first-time authorization | ✅ |
| Auth | Friendly red guidance on allowlist / `server_error` | ✅ |
| Feature | Playback: previous / seek / volume (+ device_id forwarding) | ✅ |
| Feature | Library: get_liked / save / remove | ✅ |
| Feature | Playlist: list / create / add_tracks / remove_tracks / delete | ✅ |
| Tests | pytest + mocked spotipy — parsers/validate/errors/auth/handlers/client | ✅ 43 passing |
| Docs | Design spec + implementation plan under `docs/superpowers/` | ✅ |
| Docs | README refresh (tools, architecture, auth, development) | ✅ |

## Explicitly out of scope (YAGNI)

- Paginated search/playlist/album results
- Wiring up `build_search_query` (artist/year/genre filters) — kept, unused
- Integration tests (unit tests only)

## Reference docs

- Design: `docs/superpowers/specs/2026-07-05-spotify-mcp-refactor-design.md`
- Plan: `docs/superpowers/plans/2026-07-05-spotify-mcp-restructure.md`
