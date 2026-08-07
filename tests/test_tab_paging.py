"""Tab overflow paging: a fixed window of tabs plus the < > pager.

Aqua gives ttk.Notebook no tab overflow, so tabs past TABS_PER_PAGE are hidden
and reached through the pager. The selected tab must always stay reachable, and
the per-tab close hit-testing must keep working across pages.
"""
import sys
import tempfile
import time

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

import os

import platform_support as _ps
_ps.settings_path = (lambda d=tempfile.mkdtemp(prefix="ytdlpgui-test-"):
                     os.path.join(d, "settings.json"))

import download_tab
import gui
import notifier

for _module in (notifier, gui.notifier, download_tab.notifier):
    _module.notify = lambda *a: None


def settle(app):
    app.root.update_idletasks()
    app.root.update()


def visible(app):
    """Batch numbers currently drawn on the tab strip, in strip order.

    Reports tab.number rather than the position: numbers are handed out once
    and never reused, so after a close the two no longer agree.
    """
    return [
        tab.number
        for tab in app.tabs
        if str(app.notebook.tab(tab.frame, "state")) != "hidden"
    ]


app = gui.DownloaderApp()
try:
    settle(app)
    PER_PAGE = gui.TABS_PER_PAGE

    # --- 1. Below the threshold nothing is hidden and no pager shows ---------
    assert visible(app) == [1], visible(app)
    assert not app.pager_prev.winfo_ismapped(), "pager must stay hidden while tabs fit"
    while len(app.tabs) < PER_PAGE:
        app.add_tab()
    settle(app)
    assert visible(app) == list(range(1, PER_PAGE + 1)), visible(app)
    assert not app.pager_prev.winfo_ismapped(), "exactly TABS_PER_PAGE tabs still fit"
    print(f"TEST 1 PASSED: {PER_PAGE} tabs all visible, pager stays hidden")

    # --- 2. The pager appears on the overflowing tab -------------------------
    app.add_tab()  # the 9th
    settle(app)
    assert app.pager_prev.winfo_ismapped(), "pager must appear once tabs overflow"
    assert app.pager_next.winfo_ismapped()
    assert len(visible(app)) == PER_PAGE, visible(app)
    print(f"TEST 2 PASSED: pager appears at tab {PER_PAGE + 1}, window stays {PER_PAGE} wide")

    # --- 3. A newly added tab is always on screen and selected --------------
    assert app.tabs.index(app.active_tab()) == len(app.tabs) - 1
    assert app.tabs[-1].number in visible(app), f"new tab off-page: {visible(app)}"
    print("TEST 3 PASSED: a new tab past the page size pages itself into view")

    # --- 4. Adding the row of labels never widens past the window -----------
    while len(app.tabs) < 15:
        app.add_tab()
    settle(app)
    assert len(visible(app)) == PER_PAGE, visible(app)
    strip_fits = app.notebook.winfo_reqwidth() <= app.root.winfo_width() + 4
    assert strip_fits, (
        f"tab strip wants {app.notebook.winfo_reqwidth()}px in a "
        f"{app.root.winfo_width()}px window -- tabs will run off screen"
    )
    print(f"TEST 4 PASSED: 15 tabs, strip still fits ({app.notebook.winfo_reqwidth()}px)")

    # --- 5. Labels are the bare number, not "Batch N" -----------------------
    first = app.notebook.tab(app.tabs[0].frame, "text")
    second = app.notebook.tab(app.tabs[1].frame, "text")
    assert first == "1", first
    assert second.startswith("2") and gui.CLOSE_GLYPH in second, second
    assert "Batch" not in second
    print(f"TEST 5 PASSED: labels are bare numbers ({first!r}, {second!r})")

    # --- 6. Paging back moves the window and the selection ------------------
    app.notebook.select(app.tabs[14].frame)
    settle(app)
    assert 15 in visible(app)
    app._page_by(-gui.PAGER_STEP)
    settle(app)
    after_back = visible(app)
    assert after_back[0] == 1, after_back
    selected_number = app.active_tab().number
    assert selected_number in after_back, (
        f"selection {selected_number} is off the page {after_back}"
    )
    print(f"TEST 6 PASSED: paging back shows {after_back}, selection followed to {selected_number}")

    # --- 7. Pages overlap by one tab ----------------------------------------
    before = visible(app)
    app._page_by(gui.PAGER_STEP)
    settle(app)
    after = visible(app)
    overlap = set(before) & set(after)
    assert len(overlap) == 1, f"expected a 1-tab overlap, got {sorted(overlap)}"
    print(f"TEST 7 PASSED: {before} -> {after} overlap on {sorted(overlap)}")

    # --- 8. The arrows disable at each end ----------------------------------
    while app.page_start > 0:
        app._page_by(-gui.PAGER_STEP)
    settle(app)
    assert "disabled" in app.pager_prev.state(), app.pager_prev.state()
    assert "disabled" not in app.pager_next.state()
    while app.page_start < len(app.tabs) - gui.TABS_PER_PAGE:
        app._page_by(gui.PAGER_STEP)
    settle(app)
    assert "disabled" in app.pager_next.state(), app.pager_next.state()
    assert "disabled" not in app.pager_prev.state()
    print("TEST 8 PASSED: arrows disable at the first and last page")

    # --- 9. The off-page count is reported ----------------------------------
    text = app.pager_range.cget("text")
    assert "before" in text, text
    assert "after" not in text, f"on the last page nothing is after: {text!r}"
    app._page_by(-gui.PAGER_STEP)
    settle(app)
    assert "after" in app.pager_range.cget("text"), app.pager_range.cget("text")
    print(f"TEST 9 PASSED: off-page counts reported ({text.strip()!r})")

    # --- 10. Selecting an off-page tab drags the window to it ---------------
    app.notebook.select(app.tabs[0].frame)
    settle(app)
    assert 1 in visible(app), visible(app)
    app.notebook.select(app.tabs[14].frame)
    settle(app)
    assert 15 in visible(app), visible(app)
    print("TEST 10 PASSED: selecting an off-page tab pages it into view")

    # --- 11. Close hit-testing still uses absolute indices ------------------
    # hide()/add() leave index('@x,y') absolute, so the ✕ zones must still map
    # to the right tab on a later page.
    target = app.tabs[app.page_start + 1]
    app.notebook.select(target.frame)
    settle(app)
    absolute = app.notebook.index(target.frame)
    assert app.tabs[absolute] is target, "tab index no longer matches self.tabs"
    print(f"TEST 11 PASSED: tab {absolute + 1} still addressable by absolute index on page 2")

    # --- 12. Closing a tab leaves a real, visible tab selected -------------
    count_before = len(app.tabs)
    assert app.close_tab(target)
    settle(app)
    assert len(app.tabs) == count_before - 1
    active = app.active_tab()
    assert active is not None, "closing must not leave the '+' tab selected"
    assert active.number in visible(app), (
        f"selection {active.number} left off-page {visible(app)}"
    )
    print("TEST 12 PASSED: closing on a later page keeps a visible tab selected")

    # --- 13. Dropping back under the threshold retires the pager -----------
    while len(app.tabs) > PER_PAGE:
        app.close_tab(app.tabs[-1])
    settle(app)
    # Every remaining tab shows, keeping whatever number it was opened with.
    assert visible(app) == [t.number for t in app.tabs], visible(app)
    assert not app.pager_prev.winfo_ismapped(), "pager must retire when tabs fit again"
    assert app.page_start == 0
    print("TEST 13 PASSED: pager retires and all tabs return when back under the limit")

    # --- 14. Closing tab 9 of 8-9-10 leaves 8-10, and the count still says 9 --
    while len(app.tabs) > 1:
        app.close_tab(app.tabs[-1])
    while len(app.tabs) < 10:
        app.add_tab()
    settle(app)
    assert [t.number for t in app.tabs][-3:] == [8, 9, 10], [t.number for t in app.tabs]

    ninth = next(t for t in app.tabs if t.number == 9)
    assert app.close_tab(ninth)
    settle(app)
    remaining = [t.number for t in app.tabs]
    assert remaining[-2:] == [8, 10], remaining
    assert 9 not in remaining, remaining
    assert len(app.tabs) == 9, len(app.tabs)
    print(f"TEST 14 PASSED: closing 9 leaves ...{remaining[-2:]} with {len(app.tabs)} tabs open")

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
