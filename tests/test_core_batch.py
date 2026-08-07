"""Batch state and download grouping, with no Tk anywhere."""
import sys

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))

from core import batch

# --- 1. Status covers the four states ------------------------------------
assert batch.status(0, False, False) == batch.IDLE
assert batch.status(2, False, False) == batch.BUSY
assert batch.status(0, True, False) == batch.OK
assert batch.status(0, True, True) == batch.FAIL
print("TEST 1 PASSED: idle / busy / ok / fail all reported")

# --- 2. Running always outranks a past result ----------------------------
# A tab must never read as idle or finished while yt-dlp is still writing
# files: the same counter decides whether the tab may be closed.
for has_run in (False, True):
    for had_failure in (False, True):
        assert batch.status(1, has_run, had_failure) == batch.BUSY, (has_run, had_failure)
print("TEST 2 PASSED: a running batch reads busy whatever its history")

# --- 3. Clearing every URL forgets a finished result ----------------------
assert batch.should_forget_result(0, True, has_any_url=False) is True
assert batch.should_forget_result(0, True, has_any_url=True) is False
print("TEST 3 PASSED: a finished result is forgotten once the URLs are cleared")

# --- 4. A running batch never forgets its state --------------------------
assert batch.should_forget_result(1, True, has_any_url=False) is False
print("TEST 4 PASSED: a running batch keeps its state even with no URLs")

# --- 5. Nothing to forget when it never ran ------------------------------
assert batch.should_forget_result(0, False, has_any_url=False) is False
print("TEST 5 PASSED: a batch that never ran has nothing to forget")

# --- 6. Identical flags share one yt-dlp invocation ----------------------
entries = [
    ("rowA", "urlA", False, "", "chrome"),
    ("rowB", "urlB", False, "", "chrome"),
]
grouped = batch.group_downloads(entries)
assert len(grouped) == 1, grouped
(key, rows, urls), = grouped
assert key == (False, "", "chrome"), key
assert rows == ["rowA", "rowB"], rows
assert urls == ["urlA", "urlB"], urls
print("TEST 6 PASSED: rows sharing flags collapse into one invocation")

# --- 7. Each differing flag splits the group -----------------------------
for differing in (
    ("rowB", "urlB", True, "", "chrome"),       # archive differs
    ("rowB", "urlB", False, "1-3", "chrome"),   # playlist items differ
    ("rowB", "urlB", False, "", "firefox"),     # browser differs
):
    grouped = batch.group_downloads([("rowA", "urlA", False, "", "chrome"), differing])
    assert len(grouped) == 2, (differing, grouped)
print("TEST 7 PASSED: archive, playlist-items and browser each split the group")

# --- 8. Groups keep first-seen order -------------------------------------
# So the processes start in the order the user typed their URLs.
entries = [
    ("r1", "u1", True, "", "chrome"),
    ("r2", "u2", False, "", "chrome"),
    ("r3", "u3", True, "", "chrome"),
]
grouped = batch.group_downloads(entries)
assert [key[0] for key, _rows, _urls in grouped] == [True, False], grouped
assert grouped[0][2] == ["u1", "u3"], grouped[0]
print("TEST 8 PASSED: groups keep first-seen order and gather their rows")

# --- 9. No entries means no invocations ----------------------------------
assert batch.group_downloads([]) == []
print("TEST 9 PASSED: nothing to download produces no groups")

print("ALL TESTS PASSED")
