"""Verify the free-port scan, the /ping identity endpoint and the busy-range failure."""
import json
import queue
import socket
import sys
import urllib.request

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

import config
import url_server

HOST = config.URL_SERVER_HOST


def queues():
    return queue.Queue(), queue.Queue(), queue.Queue()


def occupy(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, port))
    sock.listen(1)
    return sock


held = []
servers = []
try:
    # --- 1. Clean start takes the preferred port -----------------------------
    server = url_server.start_server(*queues())
    servers.append(server)
    assert server.server_port == config.URL_SERVER_PORT, server.server_port
    print(f"TEST 1 PASSED: binds preferred port {config.URL_SERVER_PORT} when free")

    # --- 2. /ping identifies the app -----------------------------------------
    with urllib.request.urlopen(f"http://{HOST}:{server.server_port}/ping", timeout=5) as response:
        assert response.status == 200
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
        payload = json.loads(response.read())
    assert payload == {"app": "yt-dlp-gui"}, payload
    print(f"TEST 2 PASSED: /ping returns {payload} with CORS header")

    # An unknown GET path must 404 rather than masquerade as the app.
    try:
        urllib.request.urlopen(f"http://{HOST}:{server.server_port}/nope", timeout=5)
        raise AssertionError("expected 404 for unknown path")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, exc.code
    print("TEST 3 PASSED: unknown GET path 404s")

    # --- 4. Preferred port busy -> next free port ----------------------------
    second = url_server.start_server(*queues())
    servers.append(second)
    assert second.server_port == config.URL_SERVER_PORT + 1, second.server_port
    print(f"TEST 4 PASSED: falls through to {second.server_port} when {config.URL_SERVER_PORT} is taken")

    # Both are independently reachable and both identify as the app.
    for bound in servers:
        with urllib.request.urlopen(f"http://{HOST}:{bound.server_port}/ping", timeout=5) as response:
            assert json.loads(response.read())["app"] == "yt-dlp-gui"
    print("TEST 5 PASSED: each bound port answers /ping independently")

    # --- 6. Whole range busy -> OSError so the GUI can prompt ----------------
    for port in config.URL_SERVER_PORTS:
        if port in (s.server_port for s in servers):
            continue
        try:
            held.append(occupy(port))
        except OSError:
            pass  # something outside this test already holds it, equally fine

    try:
        url_server.start_server(*queues())
        raise AssertionError("expected OSError when every port in range is busy")
    except OSError as exc:
        message = str(exc)
    assert "No free port" in message, message
    print("TEST 6 PASSED: exhausted range raises OSError ->", message)

    # --- 7. Explicit port list (the custom-port prompt path) -----------------
    free_port = 5099
    custom = url_server.start_server(*queues(), ports=[free_port])
    servers.append(custom)
    assert custom.server_port == free_port, custom.server_port
    print(f"TEST 7 PASSED: custom port {free_port} honoured via ports=[...]")

    print("ALL TESTS PASSED")
finally:
    for server in servers:
        server.shutdown()
        server.server_close()
    for sock in held:
        sock.close()
