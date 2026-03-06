"""
Celery worker entrypoint for Render web service.
Render requires a process to bind to $PORT, but Celery doesn't.
This script runs a minimal HTTP health server in a background thread
alongside the Celery worker process.
"""
from __future__ import annotations
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"celery-worker"}')

    def log_message(self, *args):
        pass  # silence access logs


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()

    cmd = [
        sys.executable, "-m", "celery",
        "-A", "workers.celery_app", "worker",
        "--loglevel=info",
        "-Q", "search,er,ranking",
        "--pool=solo",
        "--concurrency=1",
    ]
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)
