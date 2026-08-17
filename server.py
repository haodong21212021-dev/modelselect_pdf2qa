import http.server
import socketserver
import os

PORT = 9000

class NovelHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            with open('/workspace/index.html', 'rb') as f:
                self.wfile.write(f.read())
        elif self.path == '/api/mei':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            with open('/workspace/honkai3_mei_full.txt', 'rb') as f:
                self.wfile.write(f.read())
        elif self.path == '/api/bronya':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            with open('/workspace/honkai3_bronya_full.txt', 'rb') as f:
                self.wfile.write(f.read())
        elif self.path == '/api/seele':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            with open('/workspace/honkai3_seele_full.txt', 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    os.chdir('/workspace')
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), NovelHandler) as httpd:
        print(f"Serving at port {PORT}")
        httpd.serve_forever()
