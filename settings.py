"""Remembers the handful of choices the user would otherwise retype every launch.

Settings are a convenience: any failure here falls back to defaults rather than
surfacing an error, because a bad settings file must never stop the app starting.
"""

import json
import os
import tempfile

import config
import platform_support

SETTINGS_VERSION = 1


def defaults():
    return {
        "path": "",
        "cookies_browser": config.DEFAULT_COOKIES_BROWSER,
        "auto_close_tabs": config.DEFAULT_AUTO_CLOSE,
        "cookies_file": "",
    }


def load():
    values = defaults()

    try:
        with open(platform_support.settings_path(), encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return values

    if not isinstance(stored, dict):
        return values

    # A saved folder that no longer exists is kept on purpose: showing it with
    # the usual "Path doesn't exist" warning beats a mysteriously blank field.
    path = stored.get("path")
    if isinstance(path, str):
        values["path"] = path

    # A browser that has since been uninstalled must not reach yt-dlp.
    browser = stored.get("cookies_browser")
    if isinstance(browser, str) and browser in config.COOKIE_BROWSER_CHOICES:
        values["cookies_browser"] = browser

    auto_close = stored.get("auto_close_tabs")
    if isinstance(auto_close, str) and auto_close in config.AUTO_CLOSE_CHOICES:
        values["auto_close_tabs"] = auto_close

    # Unlike path, a missing cookies file is silently dropped rather than
    # kept-with-a-warning: it's a deliberate override, and passing yt-dlp a
    # stale --cookies path would fail every download until the user notices.
    cookies_file = stored.get("cookies_file")
    if isinstance(cookies_file, str) and (not cookies_file or os.path.isfile(cookies_file)):
        values["cookies_file"] = cookies_file

    return values


def save(path, cookies_browser, auto_close_tabs=config.DEFAULT_AUTO_CLOSE, cookies_file=""):
    target = platform_support.settings_path()
    payload = {
        "version": SETTINGS_VERSION,
        "path": path,
        "cookies_browser": cookies_browser,
        "auto_close_tabs": auto_close_tabs,
        "cookies_file": cookies_file,
    }

    temp_name = None
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        # Write to a sibling temp file and rename over the target, so an
        # interrupted write can't leave a truncated file for the next launch.
        # Two app instances can run at once, which makes this worth doing.
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=os.path.dirname(target),
            prefix="settings-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, indent=2)
        os.replace(temp_name, target)
        return True
    except OSError:
        if temp_name and os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        return False
