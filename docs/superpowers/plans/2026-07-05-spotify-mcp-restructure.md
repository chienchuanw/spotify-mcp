# spotify-mcp 分層重構 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 spotify-mcp 從 4 個混雜檔案重構成分層架構（server / tools / client / parsers / auth / errors），補齊播放控制、新增 Library 與 Playlist 管理，並建立核心邏輯單測。

**Architecture:** 方案 B 分層。`server.py` 只做 MCP 接線與分派；`tools.py` 放 Pydantic tool 定義與 handler；`client.py` 是 `SpotifyClient` facade（接受已建立的 spotipy 實例，方便測試）；`parsers.py` 是純函式；`auth.py` 負責 OAuth 設定、lazy client factory 與 `spotify-mcp-auth` CLI；`errors.py` 統一例外格式化。設計文件見 `docs/superpowers/specs/2026-07-05-spotify-mcp-refactor-design.md`。

**Tech Stack:** Python ≥3.12、mcp==1.3.0、spotipy==2.24.0、pydantic、python-dotenv、pytest（新增 dev 依賴）、uv。

## Global Constraints

- Python `requires-python = ">=3.12"`；使用 `match`/`case`、`X | None` 型別語法皆可。
- 依賴版本鎖定：`mcp==1.3.0`、`spotipy==2.24.0`，不得升降。
- **commit 訊息一律不加 `Co-Authored-By` / 任何 co-author trailer。**
- 工作分支 `refactor/spotify-mcp-restructure`，off `dev`；整合分支是 `dev`（非 main）。
- logging 一律用 stdlib `logging`（輸出 stderr），模組內以 `logging.getLogger(__name__)` 取得 logger；不得再用自製 print-based logger。
- Tool 對外名稱格式：`"Spotify" + 類別名`（例如 `SpotifyPlayback`），維持既有慣例以免破壞既有 client 設定。
- 測試不得呼叫真實 Spotify API；一律 mock `spotipy.Spotify`。
- 執行測試指令：`uv run pytest`。

---

### Task 1: 測試骨架 + 抽出 parsers.py

**Files:**
- Modify: `pyproject.toml`（新增 dev 依賴 pytest；新增 `[tool.pytest.ini_options]`）
- Create: `tests/conftest.py`
- Create: `tests/test_parsers.py`
- Create: `src/spotify_mcp/parsers.py`
- Modify: `src/spotify_mcp/spotify_api.py`（把 `from . import utils` 改成 `from . import parsers`，並將所有 `utils.` 前綴改為 `parsers.`）
- Delete: `src/spotify_mcp/utils.py`

**Interfaces:**
- Produces（供後續 task 使用的純函式，簽名與現 utils.py 一致）：
  - `parse_track(track_item: dict, detailed: bool = False) -> Optional[dict]`
  - `parse_artist(artist_item: dict, detailed: bool = False) -> Optional[dict]`
  - `parse_album(album_item: dict, detailed: bool = False) -> dict`
  - `parse_playlist(playlist_item: dict, username, detailed: bool = False) -> Optional[dict]`
  - `parse_search_results(results: dict, qtype: str, username: Optional[str] = None) -> dict`
  - `build_search_query(...) -> str`（原封不動搬過來，暫不接線）

- [ ] **Step 1: 加入 pytest 依賴與設定**

編輯 `pyproject.toml`，把 `[dependency-groups]` 區塊改為：

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

然後執行 `uv sync` 讓環境安裝 pytest。

Run: `uv sync`
Expected: 安裝 pytest，無錯誤。

- [ ] **Step 2: 建立 parsers.py（從 utils.py 搬移，清掉重複 import）**

Create `src/spotify_mcp/parsers.py`，內容為 utils.py 的 parse_* 與 build_search_query，import 去重：

```python
from collections import defaultdict
from typing import Optional, Dict, Callable, TypeVar
from urllib.parse import quote

T = TypeVar('T')


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
```

> 注意：`validate` 裝飾器**不**放這裡（它耦合 Client），Task 3 會放進 client.py。

- [ ] **Step 3: 建立 conftest fixtures**

Create `tests/conftest.py`：

```python
import pytest


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
```

- [ ] **Step 4: 寫 parser 失敗測試**

Create `tests/test_parsers.py`：

```python
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
```

- [ ] **Step 5: 執行測試確認失敗**

Run: `uv run pytest tests/test_parsers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spotify_mcp.parsers'`（若 Step 2 尚未存檔）或 import 錯誤。若 Step 2 已建立則應直接 PASS；此時仍執行以確認綠燈。

- [ ] **Step 6: 重接 spotify_api.py 的 import 並刪除 utils.py**

編輯 `src/spotify_mcp/spotify_api.py`：把第 10 行 `from . import utils` 改成 `from . import parsers as utils`（最小改動、保留內部 `utils.` 呼叫可運作）。

> 這是過渡措施：Task 3 建立 client.py 後、Task 6 會刪除 spotify_api.py。此處用 `as utils` 別名避免大量替換，同時讓 utils.py 可安全刪除。

然後刪除舊檔：

Run: `git rm src/spotify_mcp/utils.py`
Expected: utils.py 被移除。

- [ ] **Step 7: 執行全部測試 + 冒煙匯入**

Run: `uv run pytest -v && uv run python -c "import spotify_mcp; import spotify_mcp.parsers"`
Expected: 所有 parser 測試 PASS；套件可正常匯入。

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock tests/ src/spotify_mcp/parsers.py src/spotify_mcp/spotify_api.py
git commit -m "refactor: extract parsers module and add pytest scaffolding"
```

---

### Task 2: errors.py 統一錯誤格式化

**Files:**
- Create: `src/spotify_mcp/errors.py`
- Create: `tests/test_errors.py`

**Interfaces:**
- Produces: `format_error(exc: Exception) -> str`
  - `SpotifyException` → `"Spotify API error: <msg>"`；若訊息含 `NO_ACTIVE_DEVICE` 或 device 相關 → 附加提示「請確認 Spotify 已開啟」。
  - `requests.RequestException` → `"Network error contacting Spotify: <msg>"`。
  - 其他 → `"Unexpected error: <msg>"`。

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_errors.py`：

```python
from requests import RequestException
from spotipy import SpotifyException

from spotify_mcp.errors import format_error


def test_format_spotify_exception():
    exc = SpotifyException(404, -1, "not found")
    msg = format_error(exc)
    assert "Spotify API error" in msg


def test_format_no_active_device_hint():
    exc = SpotifyException(404, -1, "NO_ACTIVE_DEVICE")
    msg = format_error(exc)
    assert "Spotify" in msg and ("open" in msg.lower() or "開啟" in msg)


def test_format_request_exception():
    msg = format_error(RequestException("timeout"))
    assert "Network error" in msg


def test_format_generic_exception():
    msg = format_error(ValueError("boom"))
    assert "Unexpected error" in msg
    assert "boom" in msg
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spotify_mcp.errors'`

- [ ] **Step 3: 實作 errors.py**

Create `src/spotify_mcp/errors.py`：

```python
import logging

from requests import RequestException
from spotipy import SpotifyException

logger = logging.getLogger(__name__)


def format_error(exc: Exception) -> str:
    """Turn an exception into a concise, user-facing message for a TextContent reply."""
    if isinstance(exc, SpotifyException):
        text = str(exc)
        if "NO_ACTIVE_DEVICE" in text or "device" in text.lower():
            return f"Spotify API error: {text}. Please make sure Spotify is open on a device."
        return f"Spotify API error: {text}"
    if isinstance(exc, RequestException):
        return f"Network error contacting Spotify: {exc}"
    return f"Unexpected error: {exc}"
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_errors.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/spotify_mcp/errors.py tests/test_errors.py
git commit -m "feat: add errors module for unified exception formatting"
```

---

### Task 3: client.py — SpotifyClient facade + validate + 新方法

**Files:**
- Create: `src/spotify_mcp/client.py`
- Create: `tests/test_validate.py`

> spotify_api.py 暫時保留（server.py 仍在用），Task 6 flip 時刪除。此 task 建立獨立的 client.py。

**Interfaces:**
- Consumes: `spotify_mcp.parsers`（Task 1）
- Produces:
  - `validate(func)` 裝飾器：呼叫前若 `self.auth_ok()` 為 False 則呼叫 `self.auth_refresh()`；若 `self.is_active_device()` 為 False 則把 `self._get_candidate_device()` 塞進 `kwargs['device']`。
  - `class SpotifyClient`：
    - `__init__(self, sp)` — 存 `self.sp`、`self.auth_manager = sp.auth_manager`、`self.cache_handler = self.auth_manager.cache_handler`、`self.username = None`
    - `set_username(self)`
    - `search(self, query, qtype='track', limit=10, device=None)`
    - `get_info(self, item_uri) -> dict`
    - `get_current_track(self) -> Optional[dict]`
    - `start_playback(self, spotify_uri=None, device=None)`
    - `pause_playback(self, device=None)`
    - `skip_track(self, n=1, device=None)`
    - `previous_track(self, device=None)`
    - `seek_to_position(self, position_ms, device=None)`
    - `set_volume(self, volume_percent, device=None)`
    - `add_to_queue(self, track_id, device=None)`
    - `get_queue(self, device=None) -> dict`
    - `get_liked_tracks(self, limit=50, device=None) -> list`
    - `save_tracks(self, track_ids, device=None)`
    - `remove_tracks(self, track_ids, device=None)`
    - `get_playlists(self, limit=50, device=None) -> list`
    - `create_playlist(self, name, public=False, description='', device=None) -> dict`
    - `playlist_add_tracks(self, playlist_id, track_ids, device=None)`
    - `playlist_remove_tracks(self, playlist_id, track_ids, device=None)`
    - `is_track_playing(self) -> bool`
    - `get_devices(self) -> list`
    - `is_active_device(self) -> bool`
    - `_get_candidate_device(self)`
    - `auth_ok(self) -> bool`
    - `auth_refresh(self)`

- [ ] **Step 1: 寫 validate 失敗測試**

Create `tests/test_validate.py`：

```python
from unittest.mock import MagicMock

import pytest

from spotify_mcp.client import validate


class FakeClient:
    """Minimal object exercising the validate decorator."""

    def __init__(self, auth_ok, active_device):
        self._auth_ok = auth_ok
        self._active = active_device
        self.auth_refresh = MagicMock()
        self._get_candidate_device = MagicMock(return_value={'id': 'devX', 'name': 'Phone'})

    def auth_ok(self):
        return self._auth_ok

    def is_active_device(self):
        return self._active

    @validate
    def action(self, device=None):
        return device


def test_validate_refreshes_when_auth_expired():
    c = FakeClient(auth_ok=False, active_device=True)
    c.action()
    c.auth_refresh.assert_called_once()


def test_validate_skips_refresh_when_auth_ok():
    c = FakeClient(auth_ok=True, active_device=True)
    c.action()
    c.auth_refresh.assert_not_called()


def test_validate_injects_candidate_device_when_none_active():
    c = FakeClient(auth_ok=True, active_device=False)
    result = c.action()
    c._get_candidate_device.assert_called_once()
    assert result == {'id': 'devX', 'name': 'Phone'}


def test_validate_keeps_no_device_when_active():
    c = FakeClient(auth_ok=True, active_device=True)
    assert c.action() is None
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spotify_mcp.client'`

- [ ] **Step 3: 實作 client.py**

Create `src/spotify_mcp/client.py`：

```python
import functools
import logging
from typing import Callable, Optional, Dict, List, TypeVar

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
```

> 對照舊碼刻意移除：`recommendations`（"doesnt work"）、`get_liked_songs` 的 print stub（改為 `get_liked_tracks`）、`set_username` 的無用註解。`skip_track`/`previous_track`/`seek_to_position`/`set_volume` 均加 `@validate` 與 `device` 參數以取得裝置處理。

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_validate.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 全套件冒煙**

Run: `uv run pytest -q && uv run python -c "import spotify_mcp.client"`
Expected: 全綠；client 可匯入。

- [ ] **Step 6: Commit**

```bash
git add src/spotify_mcp/client.py tests/test_validate.py
git commit -m "refactor: add SpotifyClient facade with validate and library/playlist methods"
```

---

### Task 4: auth.py — SCOPES + lazy factory + auth CLI

**Files:**
- Create: `src/spotify_mcp/auth.py`
- Create: `tests/test_auth.py`

**Interfaces:**
- Consumes: `spotify_mcp.client.SpotifyClient`（Task 3）
- Produces:
  - `SCOPES: list[str]`
  - `build_auth_manager(open_browser: bool = False) -> SpotifyOAuth`
  - `get_client() -> SpotifyClient`（模組級 lazy singleton；快取於 `_client`）
  - `reset_client() -> None`（測試用，清 `_client`）
  - `auth_main() -> None`（CLI 進入點）

- [ ] **Step 1: 寫 lazy factory 失敗測試**

Create `tests/test_auth.py`：

```python
from unittest.mock import MagicMock

import spotify_mcp.auth as auth


def test_get_client_is_cached(monkeypatch):
    auth.reset_client()
    fake_sp = MagicMock()
    monkeypatch.setattr(auth, "_build_spotify", lambda: fake_sp)

    c1 = auth.get_client()
    c2 = auth.get_client()

    assert c1 is c2                      # cached singleton
    assert c1.sp is fake_sp              # wraps the built spotipy client


def test_scopes_cover_new_features():
    joined = " ".join(auth.SCOPES)
    assert "user-library-modify" in joined
    assert "playlist-modify-private" in joined
    assert "user-modify-playback-state" in joined
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spotify_mcp.auth'`

- [ ] **Step 3: 實作 auth.py**

Create `src/spotify_mcp/auth.py`：

```python
import logging
import os

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from .client import SpotifyClient

load_dotenv()
logger = logging.getLogger(__name__)

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-library-read",
    "user-library-modify",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-private",
    "playlist-modify-public",
]

_client: SpotifyClient | None = None


def build_auth_manager(open_browser: bool = False) -> SpotifyOAuth:
    return SpotifyOAuth(
        scope=",".join(SCOPES),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        open_browser=open_browser,
    )


def _build_spotify() -> spotipy.Spotify:
    return spotipy.Spotify(auth_manager=build_auth_manager(open_browser=False))


def get_client() -> SpotifyClient:
    """Lazily build and cache the SpotifyClient (never at import time)."""
    global _client
    if _client is None:
        _client = SpotifyClient(_build_spotify())
    return _client


def reset_client() -> None:
    global _client
    _client = None


def auth_main() -> None:
    """CLI entry point: run the OAuth handshake once and cache the token."""
    logging.basicConfig(level=logging.INFO)
    auth_manager = build_auth_manager(open_browser=True)
    # Forces the interactive flow (spotipy starts a local server on the redirect port).
    token = auth_manager.get_access_token(as_dict=False)
    if token:
        print("Spotify authorization complete. Token cached.")
    else:
        print("Spotify authorization failed. Check your credentials and redirect URI.")
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add src/spotify_mcp/auth.py tests/test_auth.py
git commit -m "feat: add auth module with lazy client factory and auth CLI"
```

---

### Task 5: tools.py — tool 定義 + handlers + registry

**Files:**
- Create: `src/spotify_mcp/tools.py`
- Create: `tests/test_handlers.py`

**Interfaces:**
- Consumes: `spotify_mcp.client.SpotifyClient`（duck-typed；測試用 MagicMock）
- Produces:
  - `TOOL_MODELS: list[type[ToolModel]]`（順序：Playback, Search, Queue, GetInfo, Library, Playlist）
  - `HANDLERS: dict[str, Callable[[SpotifyClient, dict], list[types.TextContent]]]`，key 為 tool 對外名（`"SpotifyPlayback"` 等）
  - 每個 handler 簽名 `handle_xxx(client, arguments: dict) -> list[types.TextContent]`
  - handler 不捕捉例外（交給 server 層）；但缺必填參數時回傳含錯誤訊息的 `TextContent`（不 raise）。

- [ ] **Step 1: 寫 handler 失敗測試**

Create `tests/test_handlers.py`：

```python
import json
from unittest.mock import MagicMock

from spotify_mcp import tools


def _text(result):
    assert len(result) == 1
    return result[0].text


def test_playback_get_returns_track():
    client = MagicMock()
    client.get_current_track.return_value = {'name': 'Song A'}
    out = _text(tools.handle_playback(client, {'action': 'get'}))
    assert json.loads(out)['name'] == 'Song A'


def test_playback_get_no_track():
    client = MagicMock()
    client.get_current_track.return_value = None
    out = _text(tools.handle_playback(client, {'action': 'get'}))
    assert "No track" in out


def test_playback_skip_uses_num_skips():
    client = MagicMock()
    tools.handle_playback(client, {'action': 'skip', 'num_skips': 3})
    client.skip_track.assert_called_once_with(n=3)


def test_playback_seek_requires_position():
    client = MagicMock()
    out = _text(tools.handle_playback(client, {'action': 'seek'}))
    assert "position_ms" in out
    client.seek_to_position.assert_not_called()


def test_playback_volume_calls_client():
    client = MagicMock()
    tools.handle_playback(client, {'action': 'volume', 'volume_percent': 40})
    client.set_volume.assert_called_once_with(40)


def test_playback_unknown_action():
    client = MagicMock()
    out = _text(tools.handle_playback(client, {'action': 'nope'}))
    assert "Unknown" in out


def test_queue_add_requires_track_id():
    client = MagicMock()
    out = _text(tools.handle_queue(client, {'action': 'add'}))
    assert "track_id" in out
    client.add_to_queue.assert_not_called()


def test_library_save_requires_ids():
    client = MagicMock()
    out = _text(tools.handle_library(client, {'action': 'save'}))
    assert "track_ids" in out


def test_library_get_liked():
    client = MagicMock()
    client.get_liked_tracks.return_value = [{'name': 'S'}]
    out = _text(tools.handle_library(client, {'action': 'get_liked'}))
    assert json.loads(out)[0]['name'] == 'S'


def test_playlist_create_requires_name():
    client = MagicMock()
    out = _text(tools.handle_playlist(client, {'action': 'create'}))
    assert "name" in out


def test_playlist_add_tracks_calls_client():
    client = MagicMock()
    tools.handle_playlist(client, {
        'action': 'add_tracks', 'playlist_id': 'p1', 'track_ids': ['t1', 't2']})
    client.playlist_add_tracks.assert_called_once_with('p1', ['t1', 't2'])


def test_registry_has_all_tools():
    names = {m.as_tool().name for m in tools.TOOL_MODELS}
    assert names == set(tools.HANDLERS.keys())
    assert "SpotifyPlayback" in names
    assert "SpotifyPlaylist" in names
```

- [ ] **Step 2: 執行確認失敗**

Run: `uv run pytest tests/test_handlers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spotify_mcp.tools'`

- [ ] **Step 3: 實作 tools.py**

Create `src/spotify_mcp/tools.py`：

```python
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
    """
    action: str = Field(description="'list', 'create', 'add_tracks', or 'remove_tracks'.")
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
        case _:
            return _text(f"Unknown playlist action: {action}. Supported: list, create, add_tracks, remove_tracks.")


TOOL_MODELS = [Playback, Search, Queue, GetInfo, Library, Playlist]

HANDLERS: dict[str, Callable] = {
    "SpotifyPlayback": handle_playback,
    "SpotifySearch": handle_search,
    "SpotifyQueue": handle_queue,
    "SpotifyGetInfo": handle_getinfo,
    "SpotifyLibrary": handle_library,
    "SpotifyPlaylist": handle_playlist,
}
```

- [ ] **Step 4: 執行確認通過**

Run: `uv run pytest tests/test_handlers.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add src/spotify_mcp/tools.py tests/test_handlers.py
git commit -m "feat: add tools module with domain-grouped handlers and registry"
```

---

### Task 6: Flip — 重寫 server.py、__init__、pyproject，刪除 spotify_api.py

**Files:**
- Modify: `src/spotify_mcp/server.py`（完全重寫）
- Modify: `src/spotify_mcp/__init__.py`
- Modify: `pyproject.toml`（新增 `spotify-mcp-auth` entry point）
- Delete: `src/spotify_mcp/spotify_api.py`

**Interfaces:**
- Consumes: `tools.TOOL_MODELS`、`tools.HANDLERS`、`auth.get_client`、`auth.auth_main`、`errors.format_error`
- Produces: `server.main()`（async）、`main()`（`__init__`，同步入口）

- [ ] **Step 1: 重寫 server.py**

Replace 全檔 `src/spotify_mcp/server.py`：

```python
import logging
import sys

import mcp.types as types
import mcp.server.stdio
from mcp.server import Server

from .auth import get_client
from .errors import format_error
from .tools import TOOL_MODELS, HANDLERS

logger = logging.getLogger(__name__)

server = Server("spotify-mcp")


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return []


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return []


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools = [model.as_tool() for model in TOOL_MODELS]
    logger.info("Available tools: %s", [t.name for t in tools])
    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    logger.info("Tool called: %s with arguments: %s", name, arguments)
    handler = HANDLERS.get(name)
    if handler is None:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        client = get_client()
        return handler(client, arguments or {})
    except Exception as e:
        logger.error("Error handling %s: %s", name, e, exc_info=True)
        return [types.TextContent(type="text", text=format_error(e))]


async def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

- [ ] **Step 2: 更新 __init__.py**

Replace `src/spotify_mcp/__init__.py`：

```python
import asyncio

from . import server
from .auth import auth_main


def main():
    """Main entry point for the MCP server."""
    asyncio.run(server.main())


__all__ = ['main', 'auth_main', 'server']
```

- [ ] **Step 3: 刪除舊 client 檔**

Run: `git rm src/spotify_mcp/spotify_api.py`
Expected: 檔案移除。

- [ ] **Step 4: 更新 pyproject entry points**

編輯 `pyproject.toml` 的 `[project.scripts]`：

```toml
[project.scripts]
spotify-mcp = "spotify_mcp:main"
spotify-mcp-auth = "spotify_mcp:auth_main"
```

- [ ] **Step 5: 冒煙匯入 + 全套件測試**

Run: `uv run python -c "import spotify_mcp; from spotify_mcp import server, tools, auth, errors, client, parsers; print('ok')"`
Expected: 印出 `ok`，無 import 錯誤，且**不觸發** OAuth（get_client 為 lazy）。

Run: `uv run pytest -q`
Expected: 全綠。

- [ ] **Step 6: 驗證 list_tools 回傳 6 個工具（不需真實 API）**

Run:
```bash
uv run python -c "import asyncio; from spotify_mcp.server import handle_list_tools; print([t.name for t in asyncio.run(handle_list_tools())])"
```
Expected: `['SpotifyPlayback', 'SpotifySearch', 'SpotifyQueue', 'SpotifyGetInfo', 'SpotifyLibrary', 'SpotifyPlaylist']`

- [ ] **Step 7: Commit**

```bash
git add src/spotify_mcp/server.py src/spotify_mcp/__init__.py pyproject.toml
git commit -m "refactor: wire server to tools registry, lazy client, and auth CLI"
```

---

### Task 7: 文件更新與收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 README 的授權與功能說明**

在 README「Configuration」段落後、`Troubleshooting` 前，加入授權步驟：

```markdown
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
```

並在「Features」清單補上新能力：

```markdown
- Start, pause, skip, go to previous, seek, and set volume
- Search for tracks/albums/artists/playlists
- Get info about a track/album/artist/playlist
- Manage the Spotify queue
- Manage your library (list/save/remove liked tracks)
- Manage playlists (list, create, add/remove tracks)
```

同時把 TODO 段落中「adding API support for managing playlists」「tests」兩項移除或標記為已完成。

- [ ] **Step 2: 最終未使用 import 掃描**

Run: `uv run python -W error -c "import spotify_mcp.server, spotify_mcp.tools, spotify_mcp.client, spotify_mcp.auth, spotify_mcp.errors, spotify_mcp.parsers"`
Expected: 無警告、無錯誤。人工快速掃過各檔頂端 import，確認沒有殘留未使用項（例如 server.py 不應再有 base64/Enum/datetime/Path 等）。

- [ ] **Step 3: 全套件最終確認**

Run: `uv run pytest -q`
Expected: 全綠。

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document auth CLI and new library/playlist features"
```

---

## Self-Review

**Spec coverage：**
- 模組佈局（server/tools/client/parsers/auth/errors + tests）→ Tasks 1–6 全數建立；conftest/test_* → Tasks 1,2,3,4,5。✅
- Tool 清單（Playback 補 previous/seek/volume、Queue、Search、GetInfo、Library、Playlist list/create/add/remove）→ Task 5 全覆蓋；Playlist `list` 對應 spec 修正。✅
- Client 設計（單一 facade、移除 recommendations、rewrite get_liked、@validate 全覆蓋、SCOPES 統一）→ Task 3 + Task 4（SCOPES 移到 auth.py 單一來源）。✅
- 驗證流程（lazy get_client、spotify-mcp-auth CLI、server 只讀快取、友善訊息）→ Task 4 + Task 6；「請先執行 spotify-mcp-auth」友善訊息由 auth 失敗時 spotipy 例外經 `format_error` 呈現（Task 2 對 device/API 錯誤已處理；未授權會拋 SpotifyException/RequestException → 統一訊息）。✅
- 錯誤處理（format_error 三類、call_tool 單一 except、stdlib logging + exc_info）→ Task 2 + Task 6。✅
- 測試（parsers/validate/handlers + mock spotipy、dev 加 pytest）→ Tasks 1–5。✅
- 額外清理（移除未使用 import、去除 assert 前綴檢查、utils 重複 import）→ Task 1（parsers 去重）、Task 6（server 重寫消除 assert 與未用 import）、Task 7 Step 2 掃描。✅
- 遠端變更 → 已於實作前完成（origin 指向使用者 repo）。✅

**與 spec 的細微偏離（刻意）：**
- spec 3 提「在 @validate 內補 RequestException try/except」。本計畫改為讓 RequestException 自然傳播到 `call_tool` 的單一 except → `format_error`，達到相同「網路錯誤走 errors.py」目標，且避免裝飾器吞例外。功能等價、更乾淨。

**Placeholder scan：** 無 TBD/TODO 佔位；所有 code step 均含完整程式碼。✅

**Type consistency：** `get_client()`/`SpotifyClient(sp)`/`validate`/handler 簽名 `(client, arguments)`/`HANDLERS` key 命名（`SpotifyXxx`）在 Tasks 3–6 一致。`get_liked_tracks`、`save_tracks`、`playlist_add_tracks` 等方法名在 client.py 與 tools.py 呼叫端一致。✅
