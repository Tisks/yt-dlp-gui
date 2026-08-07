import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import config


class _Handler(BaseHTTPRequestHandler):
    url_queue = None

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == "/url":
            self._handle_url()
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


def start_server(url_queue):
    _Handler.url_queue = url_queue
    server = HTTPServer((config.URL_SERVER_HOST, config.URL_SERVER_PORT), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
