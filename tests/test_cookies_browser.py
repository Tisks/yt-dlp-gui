"""Cookie-source resolution: dropdown for manual rows, extension value for sent rows."""
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

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None
downloader.validate_url = lambda *a, **k: True

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


def cookies_flag(command):
    return command[command.index("--cookies-from-browser") + 1]


# --- 1. Detection only reports browsers with a real profile ----------------
with tempfile.TemporaryDirectory() as tmp:
    only_firefox = os.path.join(tmp, "ff")
    os.makedirs(only_firefox)
    real_dirs = platform_support.browser_profile_dirs
    platform_support.browser_profile_dirs = lambda: {
        "chrome": [os.path.join(tmp, "nope-chrome")],
        "firefox": [only_firefox],
        "opera": [os.path.join(tmp, "nope-opera")],
    }
    detected = platform_support.installed_browsers(("chrome", "firefox", "opera"))
    assert detected == ["firefox"], detected
    platform_support.browser_profile_dirs = real_dirs
print("TEST 1 PASSED: only browsers with an existing profile are detected")

# Preference is honoured when present, skipped when absent.
assert config.DEFAULT_COOKIES_BROWSER in config.COOKIE_BROWSER_CHOICES
print(f"TEST 2 PASSED: default {config.DEFAULT_COOKIES_BROWSER!r} is one of {config.COOKIE_BROWSER_CHOICES}")

app = gui.DownloaderApp()
try:
    # --- 3. A hand-typed row follows the dropdown --------------------------
    app.cookies_browser_var.set("firefox")
    app.tabs[0].url_rows[0].entry.insert(0, "https://example.com/a")
    pump(app)
    assert app.tabs[0]._row_cookies_browser(app.tabs[0].url_rows[0]) == "firefox"
    print("TEST 3 PASSED: manual row follows the dropdown")

    # --- 4. Changing the dropdown retroactively applies to manual rows -----
    app.cookies_browser_var.set("opera")
    assert app.tabs[0]._row_cookies_browser(app.tabs[0].url_rows[0]) == "opera"
    print("TEST 4 PASSED: manual row tracks a later dropdown change")

    # --- 5. An extension-sent row keeps its own browser --------------------
    app.url_queue.put(("https://example.com/from-firefox", "firefox"))
    pump(app)
    sent_row = next(r for r in app.tabs[0].url_rows if r.entry.get() == "https://example.com/from-firefox")
    assert sent_row.cookies_browser_var.get() == "firefox"
    assert app.tabs[0]._row_cookies_browser(sent_row) == "firefox", "extension value must win"
    assert app.cookies_browser_var.get() == "opera", "dropdown must be untouched"
    print("TEST 5 PASSED: extension row keeps firefox while the dropdown says opera")

    # --- 6. Both end up in the right yt-dlp commands -----------------------
    with tempfile.TemporaryDirectory() as out:
        app.path_var.set(out)
        started.clear()
        app.tabs[0].on_download()
        pump(app)

        flags = sorted(cookies_flag(c) for c in started)
        assert flags == ["firefox", "opera"], flags
        for command in started:
            browser = cookies_flag(command)
            urls = [a for a in command if a.startswith("https://")]
            if browser == "firefox":
                assert urls == ["https://example.com/from-firefox"], urls
            else:
                assert urls == ["https://example.com/a"], urls
    print("TEST 6 PASSED: rows split into separate commands with the right --cookies-from-browser")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()

# --- 7. url_server defers unknown browsers to the app ----------------------
import url_server

assert "brave" not in config.SUPPORTED_COOKIE_BROWSERS
assert config.SUPPORTED_COOKIE_BROWSERS == {"chrome", "firefox", "opera"}
print("TEST 7 PASSED: supported set narrowed to chrome/firefox/opera")

print("ALL TESTS PASSED")
