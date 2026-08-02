#!/usr/bin/env python3
"""Free-scan form endpoint. Receives the JSON POST from site-src/main.js and
sends it on via Resend.

Exists because the site is static: RESEND_API_KEY can only live in something
server-side. Runs behind nginx at /api/, so requests are same-origin and no CORS
headers are needed.

Env:
  RESEND_API_KEY   required
  MAIL_TO          recipient            (default hello@serpens.studio)
  MAIL_FROM        verified Resend sender (default "Serpens Studio <scan@serpens.studio>")
  PORT             listen port          (default 8080)
  RATE_LIMIT       posts per IP per hour (default 5)
"""
import json, os, re, sys, time, urllib.error, urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY   = os.environ.get('RESEND_API_KEY', '').strip()
MAIL_TO   = os.environ.get('MAIL_TO', 'hello@serpens.studio').strip()
MAIL_FROM = os.environ.get('MAIL_FROM', 'Serpens Studio <scan@serpens.studio>').strip()
PORT      = int(os.environ.get('PORT', '8080'))
RATE      = int(os.environ.get('RATE_LIMIT', '5'))
# Local testing only: accept and log submissions without calling Resend.
# Never set this in production; it silently discards real leads.
DRY_RUN   = os.environ.get('MAIL_DRY_RUN', '').strip() == '1'

FIELDS   = ('business', 'name', 'phone', 'trade', 'city')
MAX_LEN  = 200
MAX_BODY = 8 * 1024

_hits = {}          # ip -> deque[timestamp]


def rate_limited(ip):
    now = time.time()
    q = _hits.setdefault(ip, deque())
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RATE:
        return True
    q.append(now)
    if len(_hits) > 10000:                      # crude cap, single instance
        for k in [k for k, v in _hits.items() if not v]:
            del _hits[k]
    return False


def clean(v):
    """Collapse whitespace, strip control chars, cap length."""
    v = re.sub(r'[\x00-\x1f\x7f]', ' ', str(v))
    return re.sub(r'\s+', ' ', v).strip()[:MAX_LEN]


def send(data):
    body = json.dumps({
        'from': MAIL_FROM,
        'to': [MAIL_TO],
        'reply_to': MAIL_TO,
        'subject': f"Free scan request — {data['business'] or 'unnamed'}",
        'text': "\n".join([
            "New free scan request.", "",
            f"Business : {data['business']}",
            f"Name     : {data['name']}",
            f"Phone    : {data['phone']}",
            f"Trade    : {data['trade']}",
            f"Area     : {data['city']}",
        ]),
    }).encode()
    req = urllib.request.Request(
        'https://api.resend.com/emails', data=body, method='POST',
        headers={'Authorization': f'Bearer {API_KEY}',
                 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


class Handler(BaseHTTPRequestHandler):
    server_version = 'scan'
    sys_version = ''

    def log_message(self, fmt, *a):
        sys.stderr.write("%s\n" % (fmt % a))

    def _json(self, code, payload):
        b = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == '/healthz':
            return self._json(200, {'ok': True, 'configured': bool(API_KEY)})
        self._json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path.rstrip('/') not in ('/scan', '/api/scan'):
            return self._json(404, {'error': 'not found'})

        # nginx sets X-Real-IP; fall back to the socket for direct calls
        ip = self.headers.get('X-Real-IP') or self.client_address[0]
        if rate_limited(ip):
            return self._json(429, {'error': 'rate limited'})

        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return self._json(400, {'error': 'bad length'})
        if length <= 0 or length > MAX_BODY:
            return self._json(400, {'error': 'bad length'})

        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8', 'replace'))
            if not isinstance(payload, dict):
                raise ValueError
        except ValueError:
            return self._json(400, {'error': 'bad json'})

        # honeypot: main.js drops it client-side, but a bot posting directly won't
        if clean(payload.get('website', '')):
            return self._json(200, {'ok': True})        # look successful, discard

        data = {f: clean(payload.get(f, '')) for f in FIELDS}
        if not data['business'] or not data['phone']:
            return self._json(400, {'error': 'business and phone required'})

        if DRY_RUN:
            self.log_message('DRY RUN, not sending: %s', json.dumps(data))
            return self._json(200, {'ok': True, 'dryRun': True})

        if not API_KEY:
            self.log_message('RESEND_API_KEY unset; dropping submission')
            return self._json(503, {'error': 'mail not configured'})

        try:
            send(data)
        except urllib.error.HTTPError as e:
            # never echo the response body: it can contain request details
            self.log_message('resend rejected: HTTP %s', e.code)
            return self._json(502, {'error': 'send failed'})
        except Exception as e:
            self.log_message('resend error: %s', type(e).__name__)
            return self._json(502, {'error': 'send failed'})

        self._json(200, {'ok': True})


if __name__ == '__main__':
    if not API_KEY:
        sys.stderr.write("warning: RESEND_API_KEY unset, submissions will 503\n")
    sys.stderr.write(f"scan handler on :{PORT} -> {MAIL_TO}\n")
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
