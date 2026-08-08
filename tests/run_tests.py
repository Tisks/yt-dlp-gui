#!/usr/bin/env python3
"""Run the whole test suite.

    python3 tests/run_tests.py            # everything
    python3 tests/run_tests.py tabs port  # only suites matching these substrings

Each suite is a standalone script that prints its own TEST ... PASSED lines and
exits non-zero on failure, so they can also be run individually while working on
one area. This runner just sequences them and summarises.
"""

import os
import socket
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)

sys.path.insert(0, PROJECT_ROOT)
import config  # noqa: E402  (needs PROJECT_ROOT on the path first)


def discover(patterns):
    names = sorted(
        name
        for name in os.listdir(TESTS_DIR)
        if name.startswith("test_") and name.endswith((".py", ".js"))
    )
    if not patterns:
        return names
    return [n for n in names if any(p in n for p in patterns)]


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((config.URL_SERVER_HOST, port))
            return True
        except OSError:
            return False


def preflight():
    """The port suites assume the app's default port is free.

    A running copy of the app holds it, which would surface as a confusing
    assertion deep inside a test rather than an obvious environment problem.
    """
    if port_is_free(config.URL_SERVER_PORT):
        return True
    print(
        f"! Port {config.URL_SERVER_PORT} is in use -- the port suites expect it free.\n"
        f"  Quit yt-dlp-gui first (osascript -e 'quit app \"{config.APP_NAME}\"') "
        "or run with a filter that skips them.\n"
    )
    return False


def have_node():
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def run_one(name):
    path = os.path.join(TESTS_DIR, name)
    if name.endswith(".js"):
        if not have_node():
            return "skip", "node not installed"
        command = ["node", path]
    else:
        # Each suite runs as its own subprocess, so -X utf8 on this parent
        # process (if the caller even set it) does not carry over -- it must
        # be passed to this exact invocation. Without it, Windows gives a
        # piped stdout the legacy ANSI codepage, which can't encode the
        # tick/close glyphs several suites print.
        command = [sys.executable, "-X", "utf8", path]

    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode == 0:
        return "pass", result.stdout
    return "fail", (result.stdout or "") + (result.stderr or "")


def main():
    patterns = sys.argv[1:]
    suites = discover(patterns)
    if not suites:
        print("No suites matched", patterns)
        return 1

    if any("port" in s for s in suites) and not preflight():
        return 2

    failures = []
    skipped = []
    for name in suites:
        status, output = run_one(name)
        if status == "pass":
            count = output.count("PASSED")
            print(f"  PASS  {name:32} ({count} checks)")
        elif status == "skip":
            skipped.append(name)
            print(f"  SKIP  {name:32} ({output})")
        else:
            failures.append((name, output))
            print(f"  FAIL  {name:32}")

    print()
    print(f"{len(suites) - len(failures) - len(skipped)} passed, "
          f"{len(failures)} failed, {len(skipped)} skipped")

    for name, output in failures:
        print(f"\n----- {name} -----\n{output.rstrip()}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
