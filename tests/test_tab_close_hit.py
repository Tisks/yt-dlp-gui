"""Clicking the ✕ glyph closes a tab; clicking the label body just selects it.

Aqua ignores custom ttk tab elements, so the ✕ is part of the tab text and the
close region is hit-tested by hand -- worth testing precisely because of that.
"""
import sys
import time

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

import os as _os, tempfile as _tempfile
import platform_support as _ps
_ps.settings_path = (lambda d=_tempfile.mkdtemp(prefix="ytdlpgui-test-"):
                     _os.path.join(d, "settings.json"))

import tkinter as tk

import config
import download_tab
import downloader
import gui
import notifier

notified = []
notifier.notify = lambda title, message: notified.append(message)
gui.notifier.notify = lambda title, message: notified.append(message)
download_tab.notifier.notify = lambda title, message: notified.append(message)

real_start = downloader.start_download


class FakeEvent:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def pump(app, seconds=0.25):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


def tab_span(app, index, y=12):
    xs = []
    for x in range(0, 900, 2):
        try:
            if app.notebook.index(f"@{x},{y}") == index:
                xs.append(x)
        except tk.TclError:
            continue
    return (xs[0], xs[-1]) if xs else None


app = gui.DownloaderApp()
try:
    app.add_tab()
    app.add_tab()
    pump(app)
    app.root.update_idletasks()
    assert len(app.tabs) == 3, len(app.tabs)

    span1 = tab_span(app, 1)
    assert span1 is not None, "could not locate tab 1 on the tab strip"
    left, right = span1
    print(f"TEST 0 INFO: tab 1 spans x={left}..{right}")

    # --- 1. Clicking the left part of the label does NOT close -------------
    result = app._on_notebook_click(FakeEvent(left + 4, 12))
    pump(app)
    assert result is None, "a label-body click must fall through to normal selection"
    assert len(app.tabs) == 3, f"label click closed a tab: {len(app.tabs)}"
    print("TEST 1 PASSED: clicking the tab label body does not close it")

    # --- 2. Clicking within the ✕ zone at the right edge closes ------------
    result = app._on_notebook_click(FakeEvent(right - 2, 12))
    pump(app)
    assert result == "break", "close click must swallow the event"
    assert len(app.tabs) == 2, f"expected the tab to close, have {len(app.tabs)}"
    print(f"TEST 2 PASSED: clicking within {gui.CLOSE_ZONE_PX}px of the right edge closes the tab")

    # --- 3. The first tab ignores close clicks entirely --------------------
    app.root.update_idletasks()
    span0 = tab_span(app, 0)
    result = app._on_notebook_click(FakeEvent(span0[1] - 2, 12))
    pump(app)
    assert result is None, "first tab must not report a close hit"
    assert len(app.tabs) == 2, len(app.tabs)
    print("TEST 3 PASSED: first tab's right edge is not a close target")

    # --- 4. Clicking the '+' tab is never treated as a close --------------
    app.root.update_idletasks()
    plus_index = app.notebook.index(app.plus_frame)
    span_plus = tab_span(app, plus_index)
    if span_plus:
        before = len(app.tabs)
        result = app._on_notebook_click(FakeEvent(span_plus[1] - 2, 12))
        assert result is None, "'+' must not be closable"
        assert len(app.tabs) == before
    print("TEST 4 PASSED: '+' tab is not closable")

    # --- 5. A busy tab clicked on its ✕ warns instead of closing ----------
    downloader.start_download = lambda c, o, e, d: real_start([sys.executable, "-c", "import time; time.sleep(5)"], o, e, d)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        app.path_var.set(tmp)
        busy = app.tabs[1]
        app.notebook.select(busy.frame)
        busy.url_rows[0].entry.insert(0, "https://example.com/busy")
        pump(app)
        busy.on_download()
        pump(app, 0.3)
        assert busy.is_busy()

        notified.clear()
        app.root.update_idletasks()
        span = tab_span(app, 1)
        app._on_notebook_click(FakeEvent(span[1] - 2, 12))
        pump(app)

        assert len(app.tabs) == 2, "busy tab must survive a close click"
        assert download_tab.TAB_BUSY_MESSAGE in notified, notified
        print("TEST 5 PASSED: closing a busy tab warns instead")

        busy.on_cancel()
        for _ in range(100):
            pump(app, 0.1)
            if not busy.is_busy():
                break

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
