import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import config


class _Handler(BaseHTTPRequestHandler):
    url_queue = None
    download_queue = None
    check_archive_queue = None

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == "/url":
            self._handle_url()
        elif self.path == "/download":
            self._handle_trigger(self.download_queue)
        elif self.path == "/check-archive":
            self._handle_trigger(self.check_archive_queue)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_url(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            url = payload.get("url", "").strip()
        except (ValueError, AttributeError):
            url = ""

        if url:
            self.url_queue.put(url)
            self.send_response(200)
        else:
            self.send_response(400)
        self.end_headers()

    def _handle_trigger(self, trigger_queue):
        trigger_queue.put(True)
        self.send_response(200)
        self.end_headers()


def start_server(url_queue, download_queue, check_archive_queue):
    _Handler.url_queue = url_queue
    _Handler.download_queue = download_queue
    _Handler.check_archive_queue = check_archive_queue
    server = HTTPServer((config.URL_SERVER_HOST, config.URL_SERVER_PORT), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
