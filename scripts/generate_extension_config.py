"""Keeps the browser extension's port range and app identity in sync with config.py.

A browser extension can't `import config`, so its copies of the port range and
the /ping identity string are generated from config.py instead of hand-kept in
sync. Run this after changing URL_SERVER_PORT / URL_SERVER_PORT_SPAN / APP_NAME:

    python3 scripts/generate_extension_config.py

Or check whether the checked-in files are stale (used by the test suite and
safe to wire into CI):

    python3 scripts/generate_extension_config.py --check
"""

import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import config

EXTENSION_DIR = os.path.join(PROJECT_ROOT, "chrome-extension")
GENERATED_CONFIG_PATH = os.path.join(EXTENSION_DIR, "generated_config.js")
MANIFEST_PATH = os.path.join(EXTENSION_DIR, "manifest.json")

GENERATED_HEADER = "// GENERATED FILE -- do not edit by hand.\n"
GENERATED_NOTE = (
    "// Source of truth: config.py (URL_SERVER_PORT, URL_SERVER_PORT_SPAN, APP_NAME).\n"
    "// Regenerate with: python3 scripts/generate_extension_config.py\n"
)


def host_permissions():
    return [f"http://127.0.0.1:{port}/*" for port in config.URL_SERVER_PORTS]


def generated_config_js():
    return (
        GENERATED_HEADER
        + GENERATED_NOTE
        + "\n"
        + f"const FIRST_PORT = {config.URL_SERVER_PORT};\n"
        + f"const PORT_SPAN = {config.URL_SERVER_PORT_SPAN};\n"
        + f'const APP_IDENTITY = "{config.APP_NAME}";\n'
    )


def updated_manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["host_permissions"] = host_permissions()
    return manifest, json.dumps(manifest, indent=2) + "\n"


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def check():
    """Returns a list of stale files; empty means everything is in sync."""
    stale = []
    if read(GENERATED_CONFIG_PATH) != generated_config_js():
        stale.append(GENERATED_CONFIG_PATH)
    _manifest, expected_manifest_text = updated_manifest()
    if read(MANIFEST_PATH) != expected_manifest_text:
        stale.append(MANIFEST_PATH)
    return stale


def generate():
    write(GENERATED_CONFIG_PATH, generated_config_js())
    _manifest, manifest_text = updated_manifest()
    write(MANIFEST_PATH, manifest_text)


if __name__ == "__main__":
    if "--check" in sys.argv:
        stale_files = check()
        if stale_files:
            print("Extension config is stale, run scripts/generate_extension_config.py:")
            for path in stale_files:
                print(f"  {os.path.relpath(path, PROJECT_ROOT)}")
            sys.exit(1)
        print("Extension config is in sync with config.py")
    else:
        generate()
        print(f"Wrote {os.path.relpath(GENERATED_CONFIG_PATH, PROJECT_ROOT)}")
        print(f"Wrote {os.path.relpath(MANIFEST_PATH, PROJECT_ROOT)}")
