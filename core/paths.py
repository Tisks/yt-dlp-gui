"""Where a batch downloads to, decided without touching a widget."""

import os

EMPTY_PATH = "Empty download path"
MISSING_PATH = "Path doesn't exist"
FILE_NOT_FOLDER = "Path points to a file instead of a folder"

# Which of the two path fields a message belongs against.
LOCAL = "local"
SHARED = "shared"


def path_error(path):
    """Why `path` is unusable as a download folder, or None if it is fine."""
    if not os.path.exists(path):
        return MISSING_PATH
    if not os.path.isdir(path):
        return FILE_NOT_FOLDER
    return None


def resolve_download_path(local_path, shared_path):
    """Pick the folder to download into.

    Returns (path, field, message). `path` is None when validation failed, and
    `field` says which input the message belongs against, so the caller can put
    it on that field's own warning label.

    A local path overrides the shared one. A blank local path is not an error --
    it simply means "use the Path above" -- so the empty-value complaint only
    ever applies to the shared field.
    """
    local_path = local_path.strip()
    if local_path:
        error = path_error(local_path)
        return (None, LOCAL, error) if error else (local_path, None, None)

    shared_path = shared_path.strip()
    if not shared_path:
        return None, SHARED, EMPTY_PATH

    error = path_error(shared_path)
    return (None, SHARED, error) if error else (shared_path, None, None)
