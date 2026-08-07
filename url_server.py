import http.server
import json
import threading

import config
import platform_support


class _URLRequestHandler(http.server.BaseHTTPRequestHandler):
    url_queue = None
    download_queue = None
    check_archive_queue = None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        # Lets the extension confirm this port belongs to us and not to some
        # unrelated service that happens to be listening in our range.
        if self.path == "/ping":
            body = json.dumps({"app": config.URL_SERVER_IDENTITY}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    def do_POST(self):
        if self.path == "/url":
            self._handle_url()
        elif self.path == "/download":
            self._handle_download()
        elif self.path == "/check-archive":
            self._handle_check_archive()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_url(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            url = payload.get("url", "").strip()
            browser = payload.get("browser", "").strip().lower()
        except (json.JSONDecodeError, AttributeError):
            url = ""
            browser = ""

        # An empty value means "whatever the app's own dropdown is set to".
        if browser not in config.SUPPORTED_COOKIE_BROWSERS:
            browser = ""

        if url:
            _URLRequestHandler.url_queue.put((url, browser))
            self.send_response(200)
        else:
            self.send_response(400)

        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _handle_download(self):
        _URLRequestHandler.download_queue.put(True)
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _handle_check_archive(self):
        _URLRequestHandler.check_archive_queue.put(True)
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass


class _URLServer(http.server.HTTPServer):
    # Windows' SO_REUSEADDR lets a second process bind a port that is already
    # actively in use, which would make the free-port scan below report success
    # on an occupied port. Only POSIX gets the TIME_WAIT convenience.
    allow_reuse_address = not platform_support.IS_WINDOWS


def start_server(url_queue, download_queue, check_archive_queue, ports=None):
    """Bind the first free port in `ports` and serve on it.

    Returns the running server; read `server.server_port` for the chosen port.
    Raises OSError if every candidate port is taken.
    """
    _URLRequestHandler.url_queue = url_queue
    _URLRequestHandler.download_queue = download_queue
    _URLRequestHandler.check_archive_queue = check_archive_queue

    candidates = list(config.URL_SERVER_PORTS if ports is None else ports)
    last_error = None
    for port in candidates:
        try:
            server = _URLServer((config.URL_SERVER_HOST, port), _URLRequestHandler)
        except OSError as exc:
            last_error = exc
            continue
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    raise OSError(f"No free port in {candidates[0]}-{candidates[-1]}: {last_error}")
