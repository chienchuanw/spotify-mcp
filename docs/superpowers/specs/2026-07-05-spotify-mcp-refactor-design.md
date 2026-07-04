# spotify-mcp 重構設計

- **日期**：2026-07-05
- **狀態**：已通過設計，待寫實作計畫
- **定位**：`chienchuanw/spotify-mcp` 個人長期維護 fork（不回饋上游）

## 背景與目標

spotify-mcp 是一個 MCP server，讓 MCP client（如 Claude）透過 Spotify Web API 控制使用者的 Spotify —— 播放、搜尋、佇列、查詢資訊。底層使用 `spotipy`。

現有程式碼（4 檔、約 500 行）功能可用，但有數處死碼、import-time OAuth 風險、巨型 dispatch、自製 logger、零測試。本次重構同時達成四個目標：

1. **清理 + 穩定**現有功能
2. **結構分層**重構
3. **擴充功能**：播放控制補齊、Library 收藏管理、Playlist 管理
4. **補測試基礎建設**：核心邏輯單測

明確**不做**（YAGNI）：搜尋分頁、`build_search_query` 接線、整合測試、多檔拆分 Client。

## 設計決策（已與使用者確認）

| 決策 | 選擇 |
|---|---|
| Tool API 形狀 | 混合，按領域分群（中粒度 tool + action） |
| 擴充範圍 | 播放補齊 + Library + Playlist（不含搜尋分頁） |
| OAuth 流程 | 獨立 `spotify-mcp-auth` CLI 指令 |
| 測試深度 | 核心邏輯單測（pytest + mock spotipy），不碰真實 API |
| 架構 | 方案 B：分層（server / tools / client / parsers / auth / errors） |

## 1. 模組佈局與職責

```
src/spotify_mcp/
  __init__.py     main() 入口（不變）
  server.py       MCP 接線：list_tools 回傳所有 tool；call_tool 查 registry 分派
  tools.py        Tool 定義（Pydantic ToolModel）+ 每個 tool 的 handler 函式
  client.py       SpotifyClient facade：對外方法，內部委派 spotipy
  parsers.py      原 utils.py 的 parse_track/album/artist/playlist/search（純函式）
  auth.py         SpotifyOAuth 設定 + get_client() lazy factory + auth CLI
  errors.py       例外 → user-facing 文字的統一格式化
tests/
  conftest.py     共用 fixtures（fake spotipy、fake token）
  test_parsers.py
  test_validate.py
  test_handlers.py
```

**關鍵界線**：
- `server.py` 完全不碰 Spotify 細節，只認 tool name → handler 的 registry。
- `tools.py` 每個 handler 簽名 `(client, arguments) -> list[TextContent]`，不碰 MCP session。
- `client.py` 不碰 MCP 型別。

三層可各自獨立測試。

## 2. Tool 清單（對外 API surface）

| Tool | actions / 參數 | 對應 Client 方法 |
|---|---|---|
| `SpotifyPlayback` | `get / start / pause / skip / previous / seek / volume` | 現有 + previous_track / seek_to_position / set_volume（新接線） |
| `SpotifyQueue` | `add / get` | 不變 |
| `SpotifySearch` | query / qtype / limit | 不變 |
| `SpotifyGetInfo` | item_uri | 不變 |
| `SpotifyLibrary` | `get_liked / save / remove`（track ids） | 改寫 get_liked_songs、新增 save/remove |
| `SpotifyPlaylist` | `list / create / add_tracks / remove_tracks` | 新增 |

> 註：`SpotifyPlaylist` 的 `list` = 列出使用者自己的所有 playlist（`current_user_playlists`）。查詢**單一** playlist 的內容仍走既有的 `SpotifyGetInfo`，避免職責重疊。

**參數驗證**：`seek` 需 `position_ms`、`volume` 需 `volume_percent`、Playlist actions 需 `playlist_id` / `track_ids` / `name` 等。這些放同一 Pydantic model 的 Optional 欄位，handler 依 action 驗證必填 —— 缺就回明確錯誤訊息（不是回傳 None）。所有 tool model 的 action match 都要有 default case。

## 3. Client 設計

- 單一 `SpotifyClient` facade，方法依領域分段（playback / library / playlist 段落註解分隔）。先不拆多檔，超過 ~400 行再拆 mixin。
- 移除死碼：`recommendations`（"doesnt work"）、`set_username` 的無用 `device` 參數。
- `get_liked_songs`：從 print-stub 改成回傳 parsed 結果。
- `@validate` 裝飾器保留（好設計），補上 TODO 的 `RequestException` try/except，讓網路錯誤能被 errors.py 統一處理。
- `SCOPES` 統一：刪掉未使用的模組級 `SCOPES` list 與 `__init__` 裡的窄字串二選一，改用一份 `SCOPES`（涵蓋 playback + library + playlist modify），auth.py 與 client.py 共用。

## 4. 驗證流程（auth.py）

- **lazy factory**：`get_client()` 首次呼叫才建立 `SpotifyClient`，不再 import 時建立。handler 透過它取得 client。
- **`spotify-mcp-auth` CLI**：`pyproject.toml` 加第二個 entry point。跑一次 `SpotifyOAuth`（`open_browser=True`，spotipy 起本機 HTTP server 在 redirect port 攔 code），寫入 token 快取後結束。使用者安裝後跑一次 `uv run spotify-mcp-auth` 完成授權。
- **server 端**：只讀快取 token；若 `auth_ok()` 為 False 且無法 refresh，handler 回傳友善訊息「請先執行 spotify-mcp-auth 授權」，而非崩潰或卡在 stdin。

## 5. 錯誤處理（errors.py）

統一 `format_error(exc) -> str`，集中處理三類：
- `SpotifyException`（API 錯誤，device not found → 提示開 Spotify）
- `RequestException`（網路）
- 其他 `Exception`（fallback）

`call_tool` 的 try/except 收斂成一處呼叫 `format_error`，取代 server.py 重複的 except 區塊。logging 改用 stdlib `logging`（輸出 stderr，符合 MCP spec），丟掉自製 `setup_logger()` 假 Logger，支援 `exc_info=True` 保留 traceback。

## 6. 測試（pytest + mock spotipy）

- `test_parsers.py`：餵 Spotify 風格 fixture dict 給 parse_*，斷言瘦身結構（含 detailed=True 分支、單/多 artist、空值）。
- `test_validate.py`：mock client 的 `auth_ok`/`is_active_device`/`_get_candidate_device`，驗證 token 過期會 refresh、無 active device 會注入 candidate device。
- `test_handlers.py`：mock SpotifyClient，驗證各 tool handler 分派、必填參數缺漏的錯誤訊息、未知 action 處理。
- 不碰真實 Spotify API。`dev` dependency group 加 `pytest`。

## 額外順手清理（限動到的檔案內）

- 移除 server.py / utils.py 未使用 import。
- `assert name[:7] == "Spotify"` 改成正常條件檢查（避免 `-O` 移除 assert）。
- utils.py 重複 import 收掉。

## 遠端變更

repo origin 已改為 `git@github.com:chienchuanw/spotify-mcp.git`（原上游 URL 已移除）。
