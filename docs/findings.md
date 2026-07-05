# Findings — spotify-mcp session (2026-07-05)

Key discoveries and decisions, most useful for future maintenance.

## Spotify platform quirks

- **`localhost` redirect URIs are rejected.** Spotify now requires the loopback
  IP literal `http://127.0.0.1:8888` for HTTP redirects (`localhost` returns
  "insecure"). README + config examples updated accordingly.
- **Development Mode allowlist.** New Spotify apps start in Development Mode; only
  accounts added under the app's User Management can authorize. Others get
  `server_error` / `access_denied` from the auth server. `auth_main` now detects
  these and prints red, actionable guidance instead of a raw traceback.
- **No hard playlist delete.** The Web API only offers unfollow
  (`current_user_unfollow_playlist`), which removes a playlist from the user's
  library (and from the owner's view). Exposed as the `delete` action.
- **Playback control needs Premium + an active device.** Library/playlist/search
  do not.

## Bugs found & fixed (via code review + live testing)

1. **Import-time OAuth.** The original built the Spotify client at module import,
   so importing the package required credentials and could trigger interactive
   auth over stdio. Fixed with a lazy `get_client()` factory.
2. **`@validate` device-gating on non-playback methods.** Library/playlist/search
   methods carried `@validate`, which raises `ConnectionError` when no device is
   open. These are plain Web API calls — un-gated them (verified live: they now
   work with Spotify closed). `set_username` too, since playlist calls it.
3. **Playback device_id not forwarded.** `previous`/`seek`/`volume`/`skip`
   accepted the injected device but discarded it, so device targeting no-op'd and
   still failed with `NO_ACTIVE_DEVICE`. Now forward `device.get('id')`.

## Design decisions

- **`@validate` scope:** applies only to methods that actually target a device
  (playback + queue). Everything else relies on spotipy's per-request token
  refresh.
- **Deliberate spec deviation:** `RequestException` propagates to `call_tool`'s
  single `except` → `format_error`, rather than being swallowed inside
  `@validate`. Same outcome, cleaner.
- **Tool naming:** kept the `Spotify<Name>` convention so existing client configs
  keep working.

## Verification

- Unit: 43 tests, mocked spotipy, no network.
- Live: all six tools exercised against a real account — search, get-info,
  playback get/skip/previous/seek/volume, queue add/get, library save→remove
  (restored), and a full playlist create→add→remove→delete round-trip (self-
  cleaning).
