# Start a simple static server for frontend_test on port 3000
param(
  [int]$Port = 3000
)

Write-Output "Starting static server on http://localhost:$Port"
Push-Location (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent)

# Use Python's http.server; enable CORS by wrapping responses via a small one-liner Python snippet
.venv\Scripts\python.exe - <<'PY'
import http.server, socketserver, sys
PORT = %d
class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:3000')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-API-Key')
        http.server.SimpleHTTPRequestHandler.end_headers(self)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving on port {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down')
PY

Pop-Location
