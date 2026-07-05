# Progress Log — spotify-mcp

## 2026-07-05 — Restructure, features, live verification

Repo re-pointed to `chienchuanw/spotify-mcp` (personal fork). Default/integration
branch is `dev`. Delivered via three reviewed PRs, each rebase-merged after a
code-review subagent pass.

### PR #1 — Layered refactor + Library/Playlist + tests (`refactor/spotify-mcp-restructure`)
- Split the 3 mixed files into `server` / `tools` / `client` / `parsers` / `auth`
  / `errors`; deleted `spotify_api.py` + `utils.py`.
- Lazy `get_client()`, `spotify-mcp-auth` CLI, stdlib logging, unified errors.
- New features: playback previous/seek/volume, Library, Playlist.
- pytest scaffolding (29 tests at merge).
- Review found 2 real bugs (device-gating on library/playlist; device_id not
  forwarded) → fixed before merge; added `test_client.py`.

### PR #2 — Follow-up fixes from live testing (`fix/live-test-followups`)
- Un-gated `search` (was failing "No active device" when Spotify closed).
- Friendly red auth guidance on allowlist / `server_error`.
- README redirect URI → `127.0.0.1`.
- 40 tests. Reviewed (GO), live-verified read-only + playback + queue + library.

### PR #3 — Playlist delete (`feat/playlist-delete`)
- `delete` action via `current_user_unfollow_playlist`.
- 43 tests. Reviewed (GO), live-verified full create→add→remove→delete round-trip.

### Session archive
- README refreshed (Available tools, Architecture, Development sections).
- Status docs written to `docs/`.

## Current state

- `dev` @ latest, **43 tests passing**, all six tools live-verified.
- MCP server fully functional against a real Spotify account.

## Possible next steps

- Shuffle / repeat toggle on `SpotifyPlayback`.
- Paginated search / playlist / album results.
- Deployment story (currently TODO in README).
