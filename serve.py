#!/usr/bin/env python3
"""Local preview server mirroring nginx/site.conf.

    python3 serve.py [port]     # default 8080

Reproduces clean URLs, redirects, status codes and headers so a local check
matches production. Preview only; the Docker image is the real thing.
"""
import os, re, sys, functools, urllib.request, urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
# where form-handler/handler.py is listening; nginx uses http://form:8080/scan
FORM_UPSTREAM = os.environ.get('FORM_UPSTREAM', 'http://127.0.0.1:8099/scan')

# matches the nginx canonical-slash location
DIRPATH = re.compile(r'^(/[^.]*[^/])$')
ASSET_1D  = re.compile(r'\.(css|js)$', re.I)
ASSET_30D = re.compile(r'\.(png|jpe?g|gif|webp|avif|svg|ico|woff2?)$', re.I)

CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://*.googletagmanager.com; "
       "style-src 'self' 'unsafe-inline'; "
       "font-src 'self'; "
       "img-src 'self' data: https://www.googletagmanager.com https://*.google-analytics.com https://*.g.doubleclick.net; "
       "connect-src 'self' https:; "
       "form-action 'self' https:; "
       "frame-src https://www.googletagmanager.com; "
       "frame-ancestors 'self'; "
       "base-uri 'self'; "
       "object-src 'none'")


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *a):
        sys.stderr.write("  %s\n" % (fmt % a))

    def _common_headers(self, path):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy',
                         'geolocation=(), microphone=(), camera=()')
        self.send_header('Content-Security-Policy', CSP)
        # Real policy advertised via X-Prod-Cache-Control; served no-store so
        # edits show up immediately.
        if ASSET_1D.search(path):
            prod = 'max-age=31536000, immutable'   # content-hashed
        elif ASSET_30D.search(path):
            prod = 'max-age=2592000'
        elif path in ('/robots.txt', '/sitemap.xml'):
            prod = 'max-age=3600'
        else:
            prod = 'no-cache'
        self.send_header('X-Prod-Cache-Control', prod)
        self.send_header('Cache-Control', 'no-store, must-revalidate')

    def _send(self, code, body, ctype, path='/'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self._common_headers(path)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _not_found(self):
        page = os.path.join(ROOT, '404.html')
        if os.path.isfile(page):
            self._send(404, open(page, 'rb').read(), 'text/html; charset=utf-8')
        else:
            self._send(404, b'404', 'text/plain')

    def do_HEAD(self): self.do_GET()

    def do_POST(self):
        """Proxy /api/scan to the form handler, as nginx does in production.
        Start it with:  PORT=8099 MAIL_DRY_RUN=1 python3 form-handler/handler.py"""
        if self.path.split('?')[0] != '/api/scan':
            return self._not_found()
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return self._send(400, b'{"error":"bad length"}', 'application/json')
        body = self.rfile.read(length) if length else b''
        req = urllib.request.Request(
            FORM_UPSTREAM, data=body, method='POST',
            headers={'Content-Type': 'application/json',
                     'X-Real-IP': self.client_address[0]})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                out, code = r.read(), r.status
        except urllib.error.HTTPError as e:
            out, code = e.read(), e.code
        except Exception as e:
            sys.stderr.write(f"  form upstream unreachable ({type(e).__name__}); "
                             f"start it on {FORM_UPSTREAM}\n")
            out, code = b'{"error":"upstream unreachable"}', 502
        self._send(code, out, 'application/json')

    def do_GET(self):
        path = self.path.split('?', 1)[0].split('#', 1)[0]

        if path == '/healthz':
            return self._send(200, b'ok\n', 'text/plain')

        # legacy URLs, keep in step with nginx/site.conf
        legacy = {'/services': '/pricing/',
                  '/work': '/results/econ-windows/',
                  '/work/scoutmap': '/results/econ-windows/',
                  '/work/meridian': '/results/econ-windows/'}
        if path in legacy:
            self.send_response(301)
            self.send_header('Location', legacy[path])
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        # block dotfiles
        if any(seg.startswith('.') for seg in path.split('/') if seg):
            return self._not_found()

        target = os.path.normpath(os.path.join(ROOT, path.lstrip('/')))
        if not target.startswith(ROOT):          # path traversal
            return self._not_found()

        # canonical trailing slash: /pricing -> /pricing/  (only if the dir exists)
        if DIRPATH.match(path) and os.path.isdir(target):
            self.send_response(301)
            self.send_header('Location', path + '/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        if os.path.isdir(target):
            index = os.path.join(target, 'index.html')
            if not os.path.isfile(index):        # index-less dir -> 404, not 403
                return self._not_found()
            target = index
        elif not os.path.isfile(target):
            return self._not_found()

        ctype = self.guess_type(target)
        with open(target, 'rb') as fh:
            body = fh.read()
        self._send(200, body, ctype, path)


if not os.path.isdir(ROOT):
    sys.exit("dist/ not found — run: python3 build.py")

print(f"Serpens Studio preview  ->  http://localhost:{PORT}/")
print(f"serving {ROOT}   (Ctrl-C to stop)\n")
HTTPServer(('127.0.0.1', PORT), functools.partial(Handler, directory=ROOT)).serve_forever()
