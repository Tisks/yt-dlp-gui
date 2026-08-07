"""No bare tk.Canvas may show beside the URL rows.

tk.Canvas and tk.Label paint an opaque background, while the ttk widgets around
them let the notebook pane show through. Any canvas wider than its rows -- or a
tk.Label in the row -- therefore renders as a visibly different-coloured block.
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


app = gui.DownloaderApp()
try:
    tab = app.tabs[0]
    settle(app)

    # --- 1. The rows canvas never extends past its content -------------------
    for extra in range(0, 4):
        if extra:
            tab._add_url_row()
        settle(app)
        canvas_w = tab.rows_canvas.winfo_width()
        content_w = tab.rows_frame.winfo_width()
        assert canvas_w <= content_w, (
            f"{extra + 1} row(s): {canvas_w - content_w}px of bare canvas exposed "
            "beside the checkbox -- it will render as a different-coloured block"
        )
    print("TEST 1 PASSED: no bare canvas exposed at 1-4 rows")

    # --- 2. The scrollbar stays against the canvas ---------------------------
    # (the canvas no longer expands, so a right-packed scrollbar would drift)
    assert tab.rows_scrollbar.winfo_ismapped(), "expected a scrollbar past MAX_VISIBLE_ROWS"
    canvas_right = tab.rows_canvas.winfo_rootx() + tab.rows_canvas.winfo_width()
    gap = tab.rows_scrollbar.winfo_rootx() - canvas_right
    assert 0 <= gap <= 2, f"scrollbar drifted {gap}px away from the canvas"
    print(f"TEST 2 PASSED: scrollbar sits flush against the canvas (gap {gap}px)")

    # --- 3. Row widgets must be themed, not raw tk ---------------------------
    # A tk.Label paints its own background and shows as a block on the pane.
    for index, row in enumerate(tab.url_rows):
        assert row.tick_label.winfo_class() == "TLabel", (
            f"row {index} tick label is {row.tick_label.winfo_class()}, "
            "must be a ttk.Label so it does not paint its own background"
        )
    print(f"TEST 3 PASSED: all {len(tab.url_rows)} tick labels are themed ttk.Label")

    # --- 4. The tick still colours correctly through ttk --------------------
    row = tab.url_rows[0]
    row.tick_label.config(text=download_tab.TICK_OK, foreground=download_tab.TICK_OK_FG)
    settle(app)
    assert row.tick_label.cget("text") == download_tab.TICK_OK
    assert str(row.tick_label.cget("foreground")) == download_tab.TICK_OK_FG
    row.tick_label.config(text=download_tab.TICK_FAIL, foreground=download_tab.TICK_FAIL_FG)
    settle(app)
    assert str(row.tick_label.cget("foreground")) == download_tab.TICK_FAIL_FG
    print("TEST 4 PASSED: ✓/✗ colouring still works on ttk.Label")

    # --- 5. Holds for a freshly created tab too ------------------------------
    tab2 = app.add_tab()
    settle(app)
    canvas_w = tab2.rows_canvas.winfo_width()
    content_w = tab2.rows_frame.winfo_width()
    assert canvas_w <= content_w, f"new tab exposes {canvas_w - content_w}px of canvas"
    assert tab2.url_rows[0].tick_label.winfo_class() == "TLabel"
    print("TEST 5 PASSED: a newly added tab is clean too")

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
