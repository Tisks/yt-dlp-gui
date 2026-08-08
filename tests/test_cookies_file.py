"""A user-supplied cookies file overrides --cookies-from-browser entirely."""
import os
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

import config
import downloader
import gui
import notifier
import platform_support
import settings

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None

started = []


def fake_start(command, *a):
    started.append(command)

    class P:
        pid = 1

    return P()


downloader.start_download = fake_start


def pump(app, seconds=0.3):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as handle:
    handle.write(b"# Netscape HTTP Cookie File\n")
    COOKIES_PATH = handle.name

app = gui.DownloaderApp()
try:
    # --- 1. Starts empty, dropdown enabled, Clear disabled ------------------
    assert app.cookies_file_var.get() == ""
    assert str(app.cookies_browser_combo.cget("state")) == "readonly"
    assert str(app.cookies_file_clear_button.cget("state")) == "disabled"
    print("TEST 1 PASSED: starts with no cookies file, dropdown enabled")

    # --- 2. Setting it disables the dropdown, enables Clear ------------------
    app.cookies_file_var.set(COOKIES_PATH)
    pump(app)
    assert str(app.cookies_browser_combo.cget("state")) == "disabled"
    assert str(app.cookies_file_clear_button.cget("state")) == "normal"
    assert app.cookies_file_label.cget("text") == os.path.basename(COOKIES_PATH)
    print("TEST 2 PASSED: setting a cookies file disables the browser dropdown")

    # --- 3. Clearing it restores the dropdown --------------------------------
    app._on_clear_cookies_file()
    pump(app)
    assert app.cookies_file_var.get() == ""
    assert str(app.cookies_browser_combo.cget("state")) == "readonly"
    assert str(app.cookies_file_clear_button.cget("state")) == "disabled"
    assert app.cookies_file_label.cget("text") == "Not set"
    print("TEST 3 PASSED: clearing it restores the browser dropdown")

    # --- 4. A download uses --cookies instead of --cookies-from-browser -----
    with tempfile.TemporaryDirectory() as out:
        app.path_var.set(out)
        app.cookies_file_var.set(COOKIES_PATH)
        app.tabs[0].url_rows[0].entry.insert(0, "https://example.com/a")
        pump(app)

        started.clear()
        app.tabs[0].on_download()
        pump(app)

        assert len(started) == 1, started
        command = started[0]
        assert "--cookies-from-browser" not in command, command
        assert command[command.index("--cookies") + 1] == COOKIES_PATH, command
    print("TEST 4 PASSED: download command uses --cookies, not --cookies-from-browser")

    # --- 5. Clearing it reverts new downloads to --cookies-from-browser -----
    # A fresh tab: tab 0's download from TEST 4 never "completes" (fake_start
    # doesn't drive done_queue), so it would still read as busy.
    with tempfile.TemporaryDirectory() as out:
        tab = app.add_tab()
        app.path_var.set(out)
        app._on_clear_cookies_file()
        tab.url_rows[0].entry.insert(0, "https://example.com/b")
        pump(app)

        started.clear()
        tab.on_download()
        pump(app)

        assert len(started) == 1, started
        command = started[0]
        assert "--cookies" not in command, command
        assert "--cookies-from-browser" in command, command
    print("TEST 5 PASSED: clearing the file reverts to --cookies-from-browser")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
    if os.path.exists(COOKIES_PATH):
        os.remove(COOKIES_PATH)

# --- 6. Settings restore the cookies file on startup ------------------------
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as handle:
    handle.write(b"# Netscape HTTP Cookie File\n")
    restored_path = handle.name

try:
    with tempfile.TemporaryDirectory() as saved_dir:
        settings.save(saved_dir, config.DEFAULT_COOKIES_BROWSER, cookies_file=restored_path)

        app = gui.DownloaderApp()
        try:
            assert app.cookies_file_var.get() == restored_path, app.cookies_file_var.get()
            assert str(app.cookies_browser_combo.cget("state")) == "disabled"
            print("TEST 6 PASSED: a saved cookies file is restored and disables the dropdown on startup")
        finally:
            if getattr(app, "url_server", None) is not None:
                app.url_server.shutdown()
                app.url_server.server_close()
            app.root.destroy()
finally:
    if os.path.exists(restored_path):
        os.remove(restored_path)

print("ALL TESTS PASSED")
