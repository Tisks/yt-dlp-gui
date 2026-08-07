"""Persistence: what survives a restart, and what must never break startup."""
import glob
import json
import os
import sys
import tempfile
import time

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

import platform_support

# Keep a handle on the genuine implementation before we shadow it.
REAL_SETTINGS_PATH = platform_support.settings_path

# Redirect settings away from the real user file BEFORE anything reads it.
SETTINGS_DIR = tempfile.mkdtemp(prefix="ytdlpgui-settings-")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
platform_support.settings_path = lambda: SETTINGS_FILE

import config
import downloader
import gui
import notifier
import settings

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None
downloader.validate_url = lambda *a, **k: True
downloader.start_download = lambda command, *a: type("P", (), {"pid": 1})()


def pump(app, seconds=0.25):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


def close(app):
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()


def write_raw(text):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
        handle.write(text)


def clear():
    if os.path.exists(SETTINGS_FILE):
        os.remove(SETTINGS_FILE)


# --- 1. No file yet -> defaults, not a crash -------------------------------
clear()
values = settings.load()
assert values == {
    "path": "",
    "cookies_browser": config.DEFAULT_COOKIES_BROWSER,
    "auto_close_tabs": config.DEFAULT_AUTO_CLOSE,
}, values
print("TEST 1 PASSED: missing file falls back to defaults")

# --- 2. Round trip ---------------------------------------------------------
# load() drops browsers that aren't installed, so the round-trip value has to
# come from what this machine actually offers -- hardcoding "firefox" would
# fail on a Chrome-only machine.
ROUND_TRIP_BROWSER = config.COOKIE_BROWSER_CHOICES[-1]

with tempfile.TemporaryDirectory() as real_dir:
    assert settings.save(real_dir, ROUND_TRIP_BROWSER, config.AUTO_CLOSE_ON) is True
    values = settings.load()
    assert values == {
        "path": real_dir,
        "cookies_browser": ROUND_TRIP_BROWSER,
        "auto_close_tabs": config.AUTO_CLOSE_ON,
    }, values
    on_disk = json.load(open(SETTINGS_FILE, encoding="utf-8"))
    assert on_disk["version"] == 1, on_disk
    print("TEST 2 PASSED: save/load round trip, version stamped")

# --- 3. A corrupt file must not stop the app starting ----------------------
for junk in ("{not json", "", "[1,2,3]", "null", '{"path": 123}'):
    write_raw(junk)
    values = settings.load()
    assert values["cookies_browser"] in config.COOKIE_BROWSER_CHOICES, (junk, values)
    assert isinstance(values["path"], str), (junk, values)
print("TEST 3 PASSED: corrupt/garbage files fall back to defaults")

# --- 4. Uninstalled browser is dropped, stale path is kept -----------------
# "safari" is never in COOKIE_BROWSERS, so it stands in for any browser the
# user has since removed.
MISSING_PATH = os.path.join("definitely", "not", "here")
write_raw(json.dumps({"version": 1, "path": MISSING_PATH, "cookies_browser": "safari"}))
values = settings.load()
assert values["cookies_browser"] == config.DEFAULT_COOKIES_BROWSER, values
assert values["path"] == MISSING_PATH, values
print("TEST 4 PASSED: unavailable browser dropped, missing path kept for the warning")

# --- 5. Atomic write leaves no temp files behind ---------------------------
clear()
for _ in range(5):
    settings.save(SETTINGS_DIR, config.DEFAULT_COOKIES_BROWSER)
leftovers = glob.glob(os.path.join(SETTINGS_DIR, "settings-*.tmp"))
assert leftovers == [], leftovers
print("TEST 5 PASSED: no temp files left behind by repeated writes")

# --- 6. Unwritable location reports failure instead of raising -------------
# A path *through* a regular file is unwritable on every OS; /dev/null would
# only work on Unix, where Windows would happily create C:\dev\null\...
blocker = os.path.join(SETTINGS_DIR, "not-a-directory")
with open(blocker, "w", encoding="utf-8") as handle:
    handle.write("x")

original = platform_support.settings_path
platform_support.settings_path = lambda: os.path.join(blocker, "nope", "settings.json")
assert settings.save(SETTINGS_DIR, config.DEFAULT_COOKIES_BROWSER) is False
platform_support.settings_path = original
print("TEST 6 PASSED: unwritable location returns False, no exception")

# --- 7. Startup restores both widgets --------------------------------------
with tempfile.TemporaryDirectory() as saved_dir:
    browser = config.COOKIE_BROWSER_CHOICES[-1]
    settings.save(saved_dir, browser)

    app = gui.DownloaderApp()
    assert app.path_var.get() == saved_dir, app.path_var.get()
    assert app.cookies_browser_var.get() == browser, app.cookies_browser_var.get()
    print(f"TEST 7 PASSED: restored path and cookies_browser={browser!r} on startup")

    # --- 8. Starting a download persists the current values ---------------
    with tempfile.TemporaryDirectory() as new_dir:
        app.path_var.set(new_dir)
        app.cookies_browser_var.set(config.COOKIE_BROWSER_CHOICES[0])
        app.tabs[0].url_rows[0].entry.insert(0, "https://example.com/x")
        pump(app)
        app.tabs[0].on_download()
        pump(app)

        stored = settings.load()
        assert stored["path"] == new_dir, stored
        assert stored["cookies_browser"] == config.COOKIE_BROWSER_CHOICES[0], stored
        print("TEST 8 PASSED: a started download saves path and browser")

        # --- 9. An invalid path must not clobber the good one -------------
        app.path_var.set("/nope/does/not/exist")
        app.save_settings()
        stored = settings.load()
        assert stored["path"] == new_dir, f"bad path overwrote good one: {stored}"
        print("TEST 9 PASSED: invalid path keeps the last known-good one")

    close(app)

# --- 10. Closing the window saves ------------------------------------------
clear()
app = gui.DownloaderApp()
chosen = config.COOKIE_BROWSER_CHOICES[-1]
app.cookies_browser_var.set(chosen)
if getattr(app, "url_server", None) is not None:
    app.url_server.shutdown()
    app.url_server.server_close()
    app.url_server = None
app._on_close()
assert settings.load()["cookies_browser"] == chosen, settings.load()
print("TEST 10 PASSED: closing the window persists the dropdown")

# --- 11. Settings live outside the app bundle ------------------------------
real_path = REAL_SETTINGS_PATH()
assert "Application Support" in real_path or "AppData" in real_path, real_path
assert ".app/" not in real_path and "/Applications/" not in real_path, real_path
print(f"TEST 11 PASSED: settings path is user-scoped -> {real_path}")

print("ALL TESTS PASSED")
