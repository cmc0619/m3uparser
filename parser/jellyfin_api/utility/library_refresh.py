"""Helpers for Jellyfin library refresh modes (full vs targeted)."""
import json
import os


def map_vods_path(local_path, local_vods_dir, jellyfin_vods_path):
    """Map a path under local VODS to Jellyfin's internal VODS mount path."""
    local_root = os.path.normpath(local_vods_dir)
    path = os.path.normpath(local_path)
    # Allow prefix match with path separator so /VODS does not match /VODS_backup
    root_prefix = local_root if local_root.endswith(os.sep) else local_root + os.sep
    if path != local_root and not path.startswith(root_prefix):
        raise ValueError(f"Path {local_path!r} is not under VODS root {local_vods_dir!r}")
    rel = '' if path == local_root else os.path.relpath(path, local_root)
    jf_root = str(jellyfin_vods_path).rstrip('/').rstrip('\\')
    if not rel or rel == '.':
        return jf_root
    return jf_root + '/' + rel.replace('\\', '/')


def media_updated_payload(local_paths, local_vods_dir, jellyfin_vods_path, update_type='Created'):
    """Build Library/Media/Updated JSON body for newly added local paths."""
    updates = []
    for local_path in local_paths:
        mapped = map_vods_path(local_path, local_vods_dir, jellyfin_vods_path)
        updates.append({'Path': mapped, 'UpdateType': update_type})
    return {'Updates': updates}


def media_updated_body(local_paths, local_vods_dir, jellyfin_vods_path, update_type='Created'):
    """JSON string for Library/Media/Updated."""
    return json.dumps(media_updated_payload(local_paths, local_vods_dir, jellyfin_vods_path, update_type))
