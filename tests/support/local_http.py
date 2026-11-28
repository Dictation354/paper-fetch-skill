"""Serve deterministic HTTP responses for browser integration tests."""

import pytest


@pytest.fixture
def local_responses():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    servers = []

    def start(responder):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, headers, body = responder(
                    self.path,
                    {key.lower(): value for key, value in self.headers.items()},
                )
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join()
