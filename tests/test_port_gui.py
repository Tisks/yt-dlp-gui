"""End-to-end: what the app does at startup when ports are free / busy / exhausted."""
import socket
import sys

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
import gui
import notifier

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None

HOST = config.URL_SERVER_HOST


def occupy(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, port))
    sock.listen(1)
    return sock


def output_of(app):
    return app.tabs[0].output_text.get("1.0", "end").strip()


def error_of(app):
    return app.tabs[0].error_text.get("1.0", "end").strip()


def shutdown(app):
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()


held = []
try:
    # --- 1. Nothing in the way: preferred port, no noise in the UI -----------
    app = gui.DownloaderApp()
    assert app.server_port == config.URL_SERVER_PORT, app.server_port
    assert output_of(app) == "", output_of(app)
    assert error_of(app) == "", error_of(app)
    print(f"TEST 1 PASSED: took {config.URL_SERVER_PORT}, said nothing to the user")
    shutdown(app)

    # --- 2. Preferred port busy: next one, and the UI reports it -------------
    held.append(occupy(config.URL_SERVER_PORT))
    app = gui.DownloaderApp()
    assert app.server_port == config.URL_SERVER_PORT + 1, app.server_port
    assert f"Browser extension port: {config.URL_SERVER_PORT + 1}" in output_of(app), output_of(app)
    assert error_of(app) == "", error_of(app)
    print(f"TEST 2 PASSED: fell through to {app.server_port} and told the user")
    shutdown(app)

    # --- 3. Whole range busy: prompt, and honour what the user types ---------
    for port in config.URL_SERVER_PORTS:
        try:
            held.append(occupy(port))
        except OSError:
            pass

    asked = []

    def fake_ask(title, prompt, **kwargs):
        asked.append((title, prompt, kwargs))
        return 5099

    gui.simpledialog.askinteger = fake_ask

    app = gui.DownloaderApp()
    assert len(asked) == 1, asked
    title, prompt, kwargs = asked[0]
    assert title == "Port in use", title
    assert "5005-5015 are all in use" in prompt, prompt
    assert kwargs["minvalue"] == 1024 and kwargs["maxvalue"] == 65535, kwargs
    assert app.server_port == 5099, app.server_port
    print("TEST 3 PASSED: prompted once on an exhausted range and bound the port given")
    shutdown(app)

    # --- 4. User cancels: app still runs, shortcuts reported as off ----------
    gui.simpledialog.askinteger = lambda *a, **k: None
    app = gui.DownloaderApp()
    assert app.server_port is None, app.server_port
    assert app.url_server is None
    assert "Browser shortcuts are disabled" in error_of(app), error_of(app)
    print("TEST 4 PASSED: cancelling leaves the app usable with shortcuts off")
    shutdown(app)

    # --- 5. Bad port then good port: re-prompts instead of giving up --------
    attempts = [80, 5099]  # 80 is privileged, bind must fail

    def ask_twice(*a, **k):
        return attempts.pop(0)

    gui.simpledialog.askinteger = ask_twice
    app = gui.DownloaderApp()
    assert attempts == [], "expected both prompts to be consumed"
    assert app.server_port == 5099, app.server_port
    assert "Port 80 unavailable" in error_of(app), error_of(app)
    print("TEST 5 PASSED: unusable port re-prompts rather than failing outright")
    shutdown(app)

    print("ALL TESTS PASSED")
finally:
    for sock in held:
        sock.close()
