"""Download-path resolution, with no Tk anywhere.

Which folder a batch downloads into, and which of the two fields any complaint
belongs against. The UI only puts the message on a label.
"""
import sys
import tempfile

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))

import os

from core import paths

with tempfile.TemporaryDirectory() as shared, tempfile.TemporaryDirectory() as local:
    missing = os.path.join(shared, "does-not-exist")
    a_file = os.path.join(shared, "a-file.txt")
    with open(a_file, "w", encoding="utf-8") as handle:
        handle.write("x")

    # --- 1. path_error names the specific problem -------------------------
    assert paths.path_error(shared) is None
    assert paths.path_error(missing) == paths.MISSING_PATH
    assert paths.path_error(a_file) == paths.FILE_NOT_FOLDER
    print("TEST 1 PASSED: path_error distinguishes missing, file, and fine")

    # --- 2. A local path overrides the shared one -------------------------
    assert paths.resolve_download_path(local, shared) == (local, None, None)
    print("TEST 2 PASSED: a local path wins over the shared Path")

    # --- 3. Blank local falls back to the shared Path ---------------------
    assert paths.resolve_download_path("", shared) == (shared, None, None)
    assert paths.resolve_download_path("   ", shared) == (shared, None, None)
    print("TEST 3 PASSED: blank (or whitespace) local defers to the shared Path")

    # --- 4. A bad local path reports against the local field --------------
    path, field, message = paths.resolve_download_path(missing, shared)
    assert path is None
    assert field == paths.LOCAL, field
    assert message == paths.MISSING_PATH, message

    path, field, message = paths.resolve_download_path(a_file, shared)
    assert (path, field, message) == (None, paths.LOCAL, paths.FILE_NOT_FOLDER)
    print("TEST 4 PASSED: a bad local path complains on the local field")

    # --- 5. A bad local path is NOT rescued by a good shared one ----------
    # Typing a wrong local path is a mistake to surface, not to silently paper
    # over by downloading somewhere else.
    path, field, _message = paths.resolve_download_path(missing, shared)
    assert path is None and field == paths.LOCAL
    print("TEST 5 PASSED: a good shared Path does not rescue a bad local one")

    # --- 6. A bad shared path reports against the shared field ------------
    path, field, message = paths.resolve_download_path("", missing)
    assert path is None
    assert field == paths.SHARED, field
    assert message == paths.MISSING_PATH, message
    print("TEST 6 PASSED: a bad shared Path complains on the shared field")

    # --- 7. Empty is only ever a complaint about the shared field ---------
    path, field, message = paths.resolve_download_path("", "")
    assert path is None
    assert field == paths.SHARED, field
    assert message == paths.EMPTY_PATH, message
    # Blank local with a usable shared path is perfectly fine.
    assert paths.resolve_download_path("", shared)[0] == shared
    print("TEST 7 PASSED: blank local is never an error; blank shared is")

    # --- 8. Surrounding whitespace is ignored on both fields --------------
    assert paths.resolve_download_path(f"  {local}  ", shared) == (local, None, None)
    assert paths.resolve_download_path("", f"  {shared}  ") == (shared, None, None)
    print("TEST 8 PASSED: both fields are stripped before use")

print("ALL TESTS PASSED")
