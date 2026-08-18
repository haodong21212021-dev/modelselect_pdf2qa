#!/usr/bin/env python3
import os
import socketserver
from http.server import SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", "9000"))
ROOT = "/workspace"

FILES = {
    "/": "reader.html",
    "/reader.html": "reader.html",
    "/index.html": "reader.html",
    "/api/wuji": "武极之圣造乾坤.md",
    "/wuji.md": "武极之圣造乾坤.md",
}


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        name = FILES.get(path)
        if not name:
            self.send_error(404, "Not Found")
            return
        full = os.path.join(ROOT, name)
        if not os.path.isfile(full):
            self.send_error(404, "File missing")
            return
        ctype = "text/html; charset=utf-8" if name.endswith(".html") else "text/plain; charset=utf-8"
        data = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    os.chdir(ROOT)
    with ThreadingHTTPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving {ROOT} on 0.0.0.0:{PORT}", flush=True)
        httpd.serve_forever()
