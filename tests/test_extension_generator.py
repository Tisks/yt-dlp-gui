"""The generator keeps chrome-extension/*.js and manifest.json in sync with config.py."""
import importlib
import json
import subprocess
import sys

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))
sys.path.insert(0, _bootstrap_os.path.join(PROJECT_ROOT, "scripts"))

import config
import generate_extension_config as gen

# --- 1. Checked-in files are already in sync (this is the real regression) -
stale = gen.check()
assert stale == [], f"checked-in files are stale, run the generator: {stale}"
print("TEST 1 PASSED: chrome-extension files match config.py right now")

# --- 2. host_permissions is derived, not hand-typed ------------------------
expected = [f"http://127.0.0.1:{p}/*" for p in config.URL_SERVER_PORTS]
assert gen.host_permissions() == expected, gen.host_permissions()
manifest = json.load(open(gen.MANIFEST_PATH, encoding="utf-8"))
assert manifest["host_permissions"] == expected, manifest["host_permissions"]
print(f"TEST 2 PASSED: {len(expected)} host_permissions entries match URL_SERVER_PORTS exactly")

# --- 3. generated_config.js values match config.py --------------------------
content = open(gen.GENERATED_CONFIG_PATH, encoding="utf-8").read()
assert f"FIRST_PORT = {config.URL_SERVER_PORT};" in content, content
assert f"PORT_SPAN = {config.URL_SERVER_PORT_SPAN};" in content, content
assert f'APP_IDENTITY = "{config.APP_NAME}";' in content, content
print("TEST 3 PASSED: generated_config.js values match config.py constants")

# --- 4. --check exits non-zero the moment config.py and the checked-in ----
# --- files disagree, so drift can't silently ship -------------------------
original_span = config.URL_SERVER_PORT_SPAN
try:
    config.URL_SERVER_PORT_SPAN = original_span + 1
    config.URL_SERVER_PORTS = range(config.URL_SERVER_PORT, config.URL_SERVER_PORT + config.URL_SERVER_PORT_SPAN)
    stale = gen.check()
    assert gen.MANIFEST_PATH in stale, stale
finally:
    config.URL_SERVER_PORT_SPAN = original_span
    config.URL_SERVER_PORTS = range(config.URL_SERVER_PORT, config.URL_SERVER_PORT + config.URL_SERVER_PORT_SPAN)
print("TEST 4 PASSED: an out-of-sync config.py is detected as stale")

# --- 5. The CLI --check exit code is what a CI step would rely on ---------
result = subprocess.run(
    [sys.executable, gen.__file__ if hasattr(gen, "__file__") else "scripts/generate_extension_config.py", "--check"],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
)
assert result.returncode == 0, result.stdout + result.stderr
assert "in sync" in result.stdout, result.stdout
print("TEST 5 PASSED: `--check` exits 0 with the checked-in files as they are now")

# --- 6. config.APP_NAME is the one place notification titles + identity ---
# --- + settings folder + extension identity all trace back to ------------
import platform_support

assert config.APP_NAME == platform_support.APP_NAME == "yt-dlp-gui"
assert config.URL_SERVER_IDENTITY == config.APP_NAME
assert config.WINDOW_TITLE == config.APP_NAME.upper()
print(f"TEST 6 PASSED: APP_NAME={config.APP_NAME!r} backs identity, window title and settings dir")

# --- 7. Every notifier.notify() call site uses config.APP_NAME, not a -----
# --- hand-typed string. Covers both modules that raise notifications. ------
import re

total = 0
for module in ("gui.py", "download_tab.py"):
    source = open(_bootstrap_os.path.join(PROJECT_ROOT, module), encoding="utf-8").read()
    calls = re.findall(r"notifier\.notify\(\s*([^,]+),", source)
    assert calls, f"no notifier.notify( calls found in {module} -- did they move again?"
    assert all(c.strip() == "config.APP_NAME" for c in calls), (module, calls)
    total += len(calls)

assert total >= 8, f"expected the full set of notify sites, found {total}"
print(f"TEST 7 PASSED: all {total} notifier.notify() call sites across gui.py + download_tab.py use config.APP_NAME")

print("ALL TESTS PASSED")
