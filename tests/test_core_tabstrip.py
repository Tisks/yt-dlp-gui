"""Tab paging arithmetic, with no Tk anywhere.

The paging rules are the most intricate state in the app and have produced the
most bugs -- a stranded last tab, a page that snapped back to the selection.
Pinned down here as arithmetic, they run in milliseconds instead of through a
live notebook, and the awkward cases can be swept exhaustively.
"""
import sys

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))

from core import tabstrip

SIZE = 8

# --- 1. Everything fits: no paging at all ---------------------------------
for total in range(0, SIZE + 1):
    assert tabstrip.visible_window(total, 0, None, SIZE) == (0, total), total
print(f"TEST 1 PASSED: 0-{SIZE} tabs all show, unpaged")

# --- 2. Past the page size the window is exactly one page wide ------------
for total in range(SIZE + 1, 40):
    start, end = tabstrip.visible_window(total, 0, None, SIZE)
    assert (start, end) == (0, SIZE), (total, start, end)
print("TEST 2 PASSED: past the limit the window is exactly one page")

# --- 3. The window never runs past either edge ----------------------------
for total in (9, 15, 30, 120):
    for page_start in range(-3, total + 3):
        start, end = tabstrip.visible_window(total, page_start, None, SIZE)
        assert 0 <= start, (total, page_start, start)
        assert end <= total, (total, page_start, end)
        assert end - start == SIZE, (total, page_start, start, end)
print("TEST 3 PASSED: window stays in range for any page_start, even absurd ones")

# --- 4. The selected tab is always on the page ----------------------------
# This is what keeps a selected tab from being hidden -- which ttk answers by
# falling back to the '+' tab, and the app reads that as "new batch".
for total in (9, 15, 30, 120):
    for selected in range(total):
        for page_start in (0, 3, total // 2, total):
            start, end = tabstrip.visible_window(total, page_start, selected, SIZE)
            assert start <= selected < end, (total, selected, page_start, start, end)
print("TEST 4 PASSED: the selection is on the page for every start/selection pair")

# --- 5. '+' selected (None) leaves the page where it was ------------------
start, _end = tabstrip.visible_window(20, 6, None, SIZE)
assert start == 6, start
print("TEST 5 PASSED: a None selection does not drag the page")

# --- 6. Turning pages reaches both ends, from anywhere --------------------
# The bug this pins: clamping a turn against the wrong bound stopped the last
# turn short and left the final tab unreachable through the pager.
for total in (9, 15, 30, 120):
    last_page = total - SIZE
    for start_at in (0, 1, 7, last_page, last_page // 2):
        page = start_at
        for _turn in range(total):
            page = tabstrip.turn_page(page, 1, total, SIZE)
        assert page == last_page, (total, start_at, page)
        for _turn in range(total):
            page = tabstrip.turn_page(page, -1, total, SIZE)
        assert page == 0, (total, start_at, page)
print("TEST 6 PASSED: repeated turns land exactly on the first and last page")

# --- 7. Every tab is reachable by turning pages ---------------------------
for total in (9, 15, 30, 120):
    seen = set()
    page = 0
    for _turn in range(total + 2):
        start, end = tabstrip.visible_window(total, page, None, SIZE)
        seen.update(range(start, end))
        page = tabstrip.turn_page(page, 1, total, SIZE)
    assert seen == set(range(total)), (total, sorted(set(range(total)) - seen))
print("TEST 7 PASSED: paging right visits every tab, including the last")

# --- 8. Consecutive pages overlap by exactly one tab ----------------------
page = 0
before = set(range(*tabstrip.visible_window(30, page, None, SIZE)))
page = tabstrip.turn_page(page, 1, 30, SIZE)
after = set(range(*tabstrip.visible_window(30, page, None, SIZE)))
assert len(before & after) == 1, sorted(before & after)
print(f"TEST 8 PASSED: pages share exactly one tab ({sorted(before & after)})")

# --- 9. turn_page is inert when everything fits ---------------------------
for direction in (-1, 1):
    assert tabstrip.turn_page(0, direction, 5, SIZE) == 0
print("TEST 9 PASSED: turning does nothing while every tab fits")

# --- 10. landing_index only moves a selection that fell off --------------
assert tabstrip.landing_index(5, 0, 8) is None, "on-page selection must be left alone"
assert tabstrip.landing_index(None, 0, 8) is None, "'+' has nowhere to land"
assert tabstrip.landing_index(14, 2, 10) == 9, "must land on the page's last tab"
assert tabstrip.landing_index(0, 4, 12) == 4, "must land on the page's first tab"
print("TEST 10 PASSED: landing_index moves only off-page selections, to the nearest edge")

# --- 11. The off-page annotation counts both sides -----------------------
assert tabstrip.offscreen_text(0, 8, 8) == "", repr(tabstrip.offscreen_text(0, 8, 8))
assert tabstrip.offscreen_text(0, 8, 15).strip() == "7 after"
assert tabstrip.offscreen_text(7, 15, 15).strip() == "7 before"
assert tabstrip.offscreen_text(4, 12, 20).strip() == "4 before, 8 after"
print("TEST 11 PASSED: off-page counts read correctly on both sides")

# --- 12. Labels carry number, status and close glyph ---------------------
assert tabstrip.tab_label(1, "", False, "x") == "1"
assert tabstrip.tab_label(1, "✓", False, "x") == "1 ✓"
assert tabstrip.tab_label(12, "", True, "✕") == "12   ✕"
assert tabstrip.tab_label(12, "●", True, "✕") == "12 ●   ✕"
assert "Batch" not in tabstrip.tab_label(3, "✓", True, "✕")
print("TEST 12 PASSED: labels are bare numbers with glyphs appended")

# --- 13. Numbering follows the open tabs, never a running total ----------
assert tabstrip.next_tab_number([]) == 1
assert tabstrip.next_tab_number([1]) == 2
assert tabstrip.next_tab_number([1, 2, 3]) == 4
# Closing tab 2 of 1-2-3 leaves 1-3; the next tab is 4, not a backfilled 2.
assert tabstrip.next_tab_number([1, 3]) == 4
# After opening and closing 30 tabs only tab 1 is left: the next one is 2.
assert tabstrip.next_tab_number([1]) == 2
print("TEST 13 PASSED: numbering follows what is open, gaps are not backfilled")

print("ALL TESTS PASSED")
