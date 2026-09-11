# Targeted Jellyfin library refresh (design)

**Repo:** [cmc0619/m3uparser](https://github.com/cmc0619/m3uparser)  
**Date:** 2026-09-11  
**Status:** Implemented (2026-09-11)

## Problem

`REFRESH_LIB=true` always calls Jellyfin `POST /Library/Refresh`, which scans **every** library. That is too heavy when only a few `.strm` files were added under `VODS/`. Unchanged `.strm` content is already preserved by `sync_directories` (copy only when missing or bytes differ), so existing titles do not need a metadata refresh on every run.

## Goals

- Support three refresh modes via `REFRESH_LIB`.
- When targeted: notify Jellyfin only about **newly added** movies / shows / episodes (new destination files from sync).
- Map m3uparser’s published `VODS` paths to Jellyfin’s internal mount via `JELLYFIN_VODS_PATH`.
- Leave URL-only updates of existing files without an automatic refresh (operator can refresh manually in Jellyfin).
- Do not fall back to a full library refresh when targeted mode cannot run.

## Non-goals

- Auto-detecting Jellyfin mount paths.
- Refreshing items whose `.strm` URL changed but the file already existed.
- Changing how staging vs `VODS/` sync works beyond collecting “added” paths.
- Wiring Jellyfin mounts on Unraid (operator responsibility; config is in transition).

## Environment

| Variable | Values | Behavior |
|---|---|---|
| `REFRESH_LIB` | `false` / unset | No Jellyfin library refresh |
| `REFRESH_LIB` | `true` | Full `POST /Library/Refresh` (current behavior) |
| `REFRESH_LIB` | `targeted` | `POST /Library/Media/Updated` only for newly added paths |
| `JELLYFIN_VODS_PATH` | e.g. `/data/vod` | Jellyfin-container path that mounts the same host tree as m3uparser’s `…/VODS` |

Existing `JELLYFIN_URL` and `API_KEY` (or ezpztv client auth) remain required for any refresh.

### Parsing note

Today `lib_refresh` is a bool via `str_to_bool()`. That must become a **mode string** (or equivalent enum) so `targeted` is not treated as false. Backward compatible: `true`/`yes`/`1` → full; `false`/empty → off; `targeted` → targeted.

## How “new” is defined

`sync_directories` already distinguishes:

- **Added** — destination file did not exist → `Added content` / `Content added`
- **Updated** — destination existed, bytes differed → `Updated content` / `Content updated`

**Targeted refresh uses only Added paths** (new movies, new episode `.strm` files, which implies new shows when their first episode appears).

Updated (URL rewrite) paths are **not** auto-refreshed.

## Path mapping

Published library roots (host-visible via volume):

- `{root_dir}/VODS/Movie_VOD`
- `{root_dir}/VODS/TV_VOD`
- `{root_dir}/VODS/Unsorted_VOD` (if enabled)

m3uparser absolute path example:

`/usr/src/app/VODS/TV_VOD/Some Show (2024)/Season 01/Some Show - S01E01.strm`

With `JELLYFIN_VODS_PATH=/data/vod`:

`/data/vod/TV_VOD/Some Show (2024)/Season 01/Some Show - S01E01.strm`

Mapping rule: replace the local `{root_dir}/VODS` prefix with `JELLYFIN_VODS_PATH` (normalize separators; strip trailing slashes on the env value).

## Targeted API

`POST /Library/Media/Updated` with a body of updates, e.g.:

```json
{
  "Updates": [
    { "Path": "/data/vod/TV_VOD/Some Show (2024)/Season 01/ep.strm", "UpdateType": "Created" }
  ]
}
```

Batch reasonably (e.g. one request per run, or chunk if very large). Paths must be Jellyfin-internal paths after mapping.

## Control flow

1. During movie/TV/(unsorted) `sync_directories`, collect absolute **added** destination paths.
2. After sync (and before/alongside existing Jellyfin tasks), run refresh based on mode:
   - **off** — log and skip
   - **full** — existing `/Library/Refresh`
   - **targeted**:
     - if no added paths → log “nothing new” and skip
     - if `JELLYFIN_VODS_PATH` unset/empty → log error/warning and skip (**no** full refresh)
     - else map paths and call `/Library/Media/Updated`
3. Guide refresh (`LIVE_TV`) stays independent of this change.

Both API-key path (`run_libraryapi_task`) and ezpztv client path (`run_library_task`) must honor the same modes.

## Files likely touched (implementation)

- `parser/config/variables.py` — parse `REFRESH_LIB` mode; add `JELLYFIN_VODS_PATH` / `jellyfin_vods_path`
- `parser/processors/handlers.py` — `sync_directories` returns or accumulates added paths
- `parser/parser_script.py` / `torf` — thread collected paths into Jellyfin refresh
- `parser/jellyfin_api/utility/apikey_jellyfin.py` — targeted update helper; branch in `run_libraryapi_task`
- `parser/jellyfin_api/libraries/library_mgmt.py` — same for `run_library_task`
- `README.md`, `m3uparser/m3uparser.env`, compose example — document modes + env
- `tests/` — unit tests for mode parsing, path mapping, sync “added” collection, and no full-refresh fallback

## Success criteria

- `REFRESH_LIB=true` still triggers a full library refresh.
- `REFRESH_LIB=targeted` with new `.strm` files notifies only those mapped paths.
- `REFRESH_LIB=targeted` with zero adds does not call Jellyfin library refresh APIs.
- `REFRESH_LIB=targeted` without `JELLYFIN_VODS_PATH` does not call full refresh.
- Existing sync content-compare behavior unchanged.
- Docs describe the three modes and the env var.

## Open points (resolved in this design)

- Path strategy: **env** `JELLYFIN_VODS_PATH` (not auto-detect).
- New episodes and new shows/movies: yes, via **added** destination files.
- Dual mode: `true` = everything; `targeted` = new only.
