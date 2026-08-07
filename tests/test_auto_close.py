"""Auto-close finished tabs: only successful batches, never the first tab."""
import sys
import tempfile
import time

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

import os as _os, tempfile as _tempfile
SETTINGS_DIR = _tempfile.mkdtemp(prefix="ytdlpgui-test-")
import platform_support as _ps
_ps.settings_path = lambda: _os.path.join(SETTINGS_DIR, "settings.json")

import config
import download_tab
import downloader
import gui
import notifier
import settings

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None
download_tab.notifier.notify = lambda *a: None
downloader.validate_url = lambda *a, **k: True

real_start = downloader.start_download
exit_code = [0]


def fake_start(command, out_q, err_q, done_q):
    # Drive success vs failure by exit code. Spawned via sys.executable rather
    # than true/false so the suite also runs on Windows.
    script = "" if exit_code[0] == 0 else "raise SystemExit(1)"
    return real_start([sys.executable, "-c", script], out_q, err_q, done_q)


downloader.start_download = fake_start


def pump(app, seconds=0.4):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


def run_batch(app, tab, url):
    app.notebook.select(tab.frame)
    tab.url_rows[0].entry.delete(0, "end")
    tab.url_rows[0].entry.insert(0, url)
    pump(app, 0.15)
    tab.on_download()
    for _ in range(60):
        pump(app, 0.1)
        if not tab.is_busy():
            break


app = gui.DownloaderApp()
try:
    with tempfile.TemporaryDirectory() as tmp:
        app.path_var.set(tmp)

        # --- 1. Off by default: a finished tab stays ----------------------
        assert app.auto_close_var.get() == config.AUTO_CLOSE_OFF, app.auto_close_var.get()
        tab2 = app.add_tab()
        exit_code[0] = 0
        run_batch(app, tab2, "https://example.com/ok1")
        assert tab2.status() == "ok", tab2.status()
        pump(app, 0.3)
        assert len(app.tabs) == 2, "auto-close is Off, tab should remain"
        print("TEST 1 PASSED: with auto-close Off a finished tab stays open")

        # --- 2. On: a successful batch closes itself ----------------------
        app.auto_close_var.set(config.AUTO_CLOSE_ON)
        pump(app, 0.4)
        assert len(app.tabs) == 1, f"successful tab should have auto-closed, have {len(app.tabs)}"
        print("TEST 2 PASSED: switching auto-close On closes the finished tab")

        # --- 3. A FAILED batch is kept, so its error log survives ---------
        tab3 = app.add_tab()
        exit_code[0] = 1
        run_batch(app, tab3, "https://example.com/bad")
        assert tab3.status() == "fail", tab3.status()
        pump(app, 0.4)
        assert tab3 in app.tabs, "a failed batch must not auto-close"
        assert len(app.tabs) == 2, len(app.tabs)
        print("TEST 3 PASSED: failed batch is kept despite auto-close being On")

        app.close_tab(tab3)

        # --- 4. The first tab is never auto-closed ------------------------
        exit_code[0] = 0
        run_batch(app, app.tabs[0], "https://example.com/ok2")
        assert app.tabs[0].status() == "ok"
        pump(app, 0.4)
        assert len(app.tabs) == 1, "first tab must survive auto-close"
        print("TEST 4 PASSED: first tab is never auto-closed")

        # --- 5. A busy tab is never auto-closed ---------------------------
        downloader.start_download = lambda c, o, e, d: real_start([sys.executable, "-c", "import time; time.sleep(5)"], o, e, d)
        tab5 = app.add_tab()
        app.notebook.select(tab5.frame)
        tab5.url_rows[0].entry.insert(0, "https://example.com/slow")
        pump(app, 0.15)
        tab5.on_download()
        pump(app, 0.4)
        assert tab5.is_busy()
        assert tab5 in app.tabs, "a running batch must never be auto-closed"
        print("TEST 5 PASSED: running batch is never auto-closed")
        tab5.on_cancel()
        for _ in range(100):
            pump(app, 0.1)
            if not tab5.is_busy():
                break

    # --- 6. The choice persists across a restart --------------------------
    app.save_settings()
    stored = settings.load()
    assert stored["auto_close_tabs"] == config.AUTO_CLOSE_ON, stored
    print("TEST 6 PASSED: auto-close choice is persisted")

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
