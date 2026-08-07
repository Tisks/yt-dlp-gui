"""The '-' row button must lock (cursor + click-guard) during a download and unlock after."""
import sys
import tempfile
import time

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

# Keep tests off the real settings file.
import os as _os, tempfile as _tempfile
import platform_support as _ps
_ps.settings_path = (lambda d=_tempfile.mkdtemp(prefix="ytdlpgui-test-"):
                     _os.path.join(d, "settings.json"))

import downloader
import gui
import notifier
import platform_support

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None

real_start_download = downloader.start_download


def fake_start(command, stdout_queue, stderr_queue, done_queue):
    # A real long-lived subprocess so pending_downloads stays > 0 while checked.
    return real_start_download([sys.executable, "-c", "import time; time.sleep(5)"], stdout_queue, stderr_queue, done_queue)


downloader.start_download = fake_start


def pump(app, seconds=0.3):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


def close(app):
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()


app = gui.DownloaderApp()
try:
    row0 = app.tabs[0].url_rows[0]
    row1 = app.tabs[0]._add_url_row()
    row2 = app.tabs[0]._add_url_row()
    row0.entry.insert(0, "https://example.com/a")
    row1.entry.insert(0, "https://example.com/b")
    pump(app)

    # --- 1. First row has no remove button; the rest do -----------------------
    assert row0.remove_button is None, "first row must not have a '-' button"
    assert row1.remove_button is not None
    assert row2.remove_button is not None
    print("TEST 1 PASSED: only non-first rows carry a remove_button")

    # --- 2. Before any download, remove buttons are clickable -----------------
    assert str(row1.remove_button.cget("cursor")) == platform_support.CURSOR_CLICKABLE
    assert str(row2.remove_button.cget("cursor")) == platform_support.CURSOR_CLICKABLE
    print(f"TEST 2 PASSED: idle remove buttons show {platform_support.CURSOR_CLICKABLE!r}")

    # --- 3. Removing row2 while idle actually works (sanity, unrelated to lock)
    rows_before = len(app.tabs[0].url_rows)
    app.tabs[0]._on_remove_row_clicked(row2)
    pump(app)
    assert len(app.tabs[0].url_rows) == rows_before - 1
    assert row2 not in app.tabs[0].url_rows
    print("TEST 3 PASSED: remove still works normally while idle")

    # Re-add a second removable row for the download-lock checks below.
    row2 = app.tabs[0]._add_url_row()
    row2.entry.insert(0, "https://example.com/c")
    pump(app)

    with tempfile.TemporaryDirectory() as tmp_dir:
        app.path_var.set(tmp_dir)
        app.tabs[0].on_download()
        pump(app, 0.3)

        assert app.tabs[0].pending_downloads > 0, "expected a pending download"

        # --- 4. Cursor switches to the disabled/notallowed equivalent ---------
        assert str(row1.remove_button.cget("cursor")) == platform_support.CURSOR_DISABLED, (
            row1.remove_button.cget("cursor")
        )
        assert str(row2.remove_button.cget("cursor")) == platform_support.CURSOR_DISABLED
        print(f"TEST 4 PASSED: remove buttons show {platform_support.CURSOR_DISABLED!r} mid-download")

        # --- 5. Clicking while disabled is still a no-op (functional guard) ---
        rows_before = len(app.tabs[0].url_rows)
        app.tabs[0]._on_remove_row_clicked(row1)
        pump(app)
        assert len(app.tabs[0].url_rows) == rows_before, "row must not be removable mid-download"
        assert row1 in app.tabs[0].url_rows
        print("TEST 5 PASSED: clicking '-' mid-download does not remove the row")

        # --- 6. Cancel to force completion, then confirm re-enable ------------
        app.tabs[0].on_cancel()
        for _ in range(100):
            pump(app, 0.1)
            if app.tabs[0].pending_downloads == 0:
                break

        assert app.tabs[0].pending_downloads == 0
        assert str(row1.remove_button.cget("cursor")) == platform_support.CURSOR_CLICKABLE, (
            row1.remove_button.cget("cursor")
        )
        assert str(row2.remove_button.cget("cursor")) == platform_support.CURSOR_CLICKABLE
        print(f"TEST 6 PASSED: remove buttons return to {platform_support.CURSOR_CLICKABLE!r} once idle")

        # --- 7. And removal actually works again -------------------------------
        rows_before = len(app.tabs[0].url_rows)
        app.tabs[0]._on_remove_row_clicked(row1)
        pump(app)
        assert len(app.tabs[0].url_rows) == rows_before - 1
        assert row1 not in app.tabs[0].url_rows
        print("TEST 7 PASSED: remove works again after downloads finish")

    print("ALL TESTS PASSED")
finally:
    close(app)
