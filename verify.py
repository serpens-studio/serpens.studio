#!/usr/bin/env python3
"""Post-build checks on ./dist. Exits non-zero on failure.

Resolves links the way nginx does (try_files $uri $uri/ =404).
"""
import os, re, sys, json

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')

fail, warn = [], []
def bad(m):  fail.append(m)
def soft(m): warn.append(m)

if not os.path.isdir(DIST):
    sys.exit("dist/ not found — run build.py first")

pages = []
for dirpath, _, files in os.walk(DIST):
    for f in files:
        if f.endswith('.html'):
            pages.append(os.path.join(dirpath, f))
pages.sort()

def resolve(url_path):
    """Mirror nginx `try_files $uri $uri/ =404`."""
    rel = url_path.lstrip('/')
    direct = os.path.join(DIST, rel)
    if os.path.isfile(direct):
        return True
    if os.path.isdir(direct) and os.path.isfile(os.path.join(direct, 'index.html')):
        return True
    return False

print(f"checking {len(pages)} pages in dist/\n")

seen_titles, seen_canon, placeholder_phone = {}, {}, set()
for p in pages:
    rel = '/' + os.path.relpath(p, DIST).replace(os.sep, '/')
    doc = open(p, encoding='utf-8').read()
    tag = rel.replace('/index.html', '/') or '/'

    # --- required head elements ---
    t = re.search(r'<title>(.*?)</title>', doc, re.S)
    if not t or not t.group(1).strip():
        bad(f"{tag}: missing <title>")
    else:
        title = t.group(1).strip()
        if len(title) > 65:
            soft(f"{tag}: title is {len(title)} chars (>65 may truncate in SERPs)")
        seen_titles.setdefault(title, []).append(tag)

    dsc = re.search(r'<meta name="description" content="(.*?)">', doc, re.S)
    if not dsc or not dsc.group(1).strip():
        bad(f"{tag}: missing meta description")
    elif len(dsc.group(1)) > 165:
        soft(f"{tag}: meta description is {len(dsc.group(1))} chars (>165 may truncate)")

    can = re.search(r'<link rel="canonical" href="(.*?)">', doc)
    if not can:
        bad(f"{tag}: missing canonical")
    else:
        seen_canon.setdefault(can.group(1), []).append(tag)

    if '<h1' not in doc:
        bad(f"{tag}: no <h1>")
    elif doc.count('<h1') > 1:
        soft(f"{tag}: {doc.count('<h1')} <h1> elements")

    if 'lang="en"' not in doc:
        bad(f"{tag}: <html> missing lang")

    # --- JSON-LD must parse ---
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            bad(f"{tag}: invalid JSON-LD ({e})")

    # --- every local link and asset must resolve ---
    # <img> checked separately: main.js has onerror placeholders.
    img_srcs = set(re.findall(r'<img[^>]+src="(/[^"#?]*)"', doc))
    for href in set(re.findall(r'(?:href|src)="(/[^"#?]*)"', doc)) - img_srcs:
        if not resolve(href):
            bad(f"{tag}: dead link -> {href}")

    # --- unreplaced build placeholders ---
    if 'REPLACE' in doc:
        bad(f"{tag}: leaked REPLACE marker")
    for note in re.findall(r'<!--\s*((?:TODO|FIXME|XXX)[^>]*?)-->', doc):
        bad(f"{tag}: author note leaked into output — {note.strip()[:70]}")
    if '000-0000' in doc:
        placeholder_phone.add(tag)

if placeholder_phone:
    # hard failure: the Dockerfile runs this, so a stale build arg shadowing
    # build.py's real number fails the deploy instead of shipping 000-0000
    bad(f"placeholder phone number on {len(placeholder_phone)} page(s) — a build arg "
        f"is shadowing the default in build.py")

# --- duplicate title / canonical detection ---
for title, where in seen_titles.items():
    if len(where) > 1:
        bad(f"duplicate <title> {title!r} on {', '.join(where)}")
for canon, where in seen_canon.items():
    if len(where) > 1:
        bad(f"duplicate canonical {canon} on {', '.join(where)}")

# --- sitemap sanity ---
sm = os.path.join(DIST, 'sitemap.xml')
if not os.path.isfile(sm):
    bad("sitemap.xml missing")
else:
    locs = re.findall(r'<loc>(.*?)</loc>', open(sm).read())
    if not locs:
        bad("sitemap.xml has no <loc> entries")
    origin = re.match(r'(https?://[^/]+)', locs[0]).group(1)
    for loc in locs:
        path = loc[len(origin):] or '/'
        if not resolve(path):
            bad(f"sitemap lists unbuildable URL: {loc}")
    # every indexable page should be in the sitemap
    listed = {loc[len(origin):] or '/' for loc in locs}
    for p in pages:
        rel = '/' + os.path.relpath(p, DIST).replace(os.sep, '/')
        tag = rel.replace('index.html', '')
        if rel == '/404.html':
            continue
        if tag not in listed:
            soft(f"{tag} is built but not in sitemap.xml")

for required in ['robots.txt', '404.html', 'og.png', 'logo.png']:
    if not os.path.isfile(os.path.join(DIST, required)):
        bad(f"missing required file: dist/{required}")

# exactly one hashed asset of each type
for sub, ext in (('css', '.css'), ('js', '.js')):
    found = [f for f in os.listdir(os.path.join(DIST, sub))] if os.path.isdir(os.path.join(DIST, sub)) else []
    hashed = [f for f in found if re.fullmatch(r'main\.[0-9a-f]{10}' + re.escape(ext), f)]
    if len(hashed) != 1:
        bad(f"expected exactly one hashed dist/{sub}/main.<hash>{ext}, found {found}")

# --- missing images (soft: onerror fallbacks) ---
for p in pages:
    doc = open(p, encoding='utf-8').read()
    for src in set(re.findall(r'<img[^>]+src="(/[^"]+)"', doc)):
        if not resolve(src):
            soft(f"image not present (onerror placeholder will show): {src}")

print("\n".join(f"WARN  {w}" for w in dict.fromkeys(warn)) or "no warnings")
print()
if fail:
    print("\n".join(f"FAIL  {f}" for f in fail))
    print(f"\n{len(fail)} failure(s), {len(set(warn))} warning(s)")
    sys.exit(1)
print(f"PASS — {len(pages)} pages, 0 failures, {len(set(warn))} warning(s)")
