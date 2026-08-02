#!/usr/bin/env python3
# Serpens Studio static site generator — python3 build.py → ./dist
import os, re, shutil, html, json, datetime, hashlib

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
SRC  = os.path.join(ROOT, 'site-src')

def env(key, default):
    v = os.environ.get(key, '').strip()
    return v if v else default

# Deploy-time config; all overridable by env (see .env.example).
BASE          = env('SITE_BASE_URL', "https://serpens.studio").rstrip('/')
# NAP-of-record. Must match the Google Business Profile.
PHONE_DISPLAY = env('SITE_PHONE_DISPLAY', "(602) 905-7835")
PHONE_TEL     = env('SITE_PHONE_TEL', "+16029057835")
EMAIL         = env('SITE_EMAIL', "hello@serpens.studio")
# Free-scan form POST target. Same-origin: nginx proxies /api/scan to the form
# service. If that service isn't deployed the path 404s and main.js falls back to
# composing a mailto, so this default is safe for a static-only deploy too.
FORM_ENDPOINT = env('SITE_FORM_ENDPOINT', "/api/scan")
YEAR          = env('SITE_YEAR', str(datetime.date.today().year))

# GBP permalink. Use ?cid=; /maps/place/ URLs carry session params.
GBP_URL = env('SITE_GBP_URL', "https://maps.google.com/?cid=16126195117637674079")

# schema sameAs, comma-separated. GBP first, then profiles.
SAME_AS = [u.strip() for u in env(
    'SITE_SAME_AS',
    f"{GBP_URL},https://github.com/serpens-studio").split(',') if u.strip()]

# SITE_HOURS="Mo,Tu,We,Th,Fr 08:00-17:00". Omitted unless set; must match GBP.
def _hours(spec):
    if not spec:
        return None
    try:
        days, hours = spec.rsplit(' ', 1)
        opens, closes = hours.split('-')
        return [{"@type": "OpeningHoursSpecification",
                 "dayOfWeek": [d.strip() for d in days.split(',') if d.strip()],
                 "opens": opens.strip(), "closes": closes.strip()}]
    except ValueError:
        raise SystemExit(f'build.py: SITE_HOURS must look like "Mo,Tu,We,Th,Fr 08:00-17:00", got {spec!r}')

HOURS = _hours(env('SITE_HOURS', ''))

# Google Tag Manager. Set SITE_GTM_ID="" to build without analytics.
GTM_ID = env('SITE_GTM_ID', "GTM-NNG894NK")
if GTM_ID and not re.fullmatch(r'GTM-[A-Z0-9]{4,}', GTM_ID):
    raise SystemExit(f'build.py: SITE_GTM_ID must look like "GTM-XXXXXXX", got {GTM_ID!r}')

# Standard GTM loader. Placed as high in <head> as possible; the noscript iframe
# goes immediately after <body>. Both are omitted entirely when GTM_ID is empty,
# so a build with analytics off ships no third-party script at all.
GTM_HEAD = (f"""<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});"""
            f"""var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;"""
            f"""j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})"""
            f"""(window,document,'script','dataLayer','{GTM_ID}');</script>\n""") if GTM_ID else ""
GTM_BODY = (f"""<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM_ID}" """
            f"""height="0" width="0" style="display:none;visibility:hidden" title="Google Tag Manager"></iframe></noscript>\n""") if GTM_ID else ""

CITIES = ["Phoenix","Scottsdale","Mesa","Chandler","Gilbert","Glendale","Tempe","Peoria",
          "Paradise Valley","Cave Creek","Queen Creek","Surprise","Goodyear","Avondale",
          "Buckeye","Fountain Hills","Anthem","Sun City","Litchfield Park","Apache Junction"]

TERRITORIES = "Phoenix · Scottsdale & Paradise Valley · Mesa & East Valley · Chandler & Gilbert · Glendale & Peoria · West Valley"

# ---------------- TRADE DATA ----------------
TRADES = [
 dict(slug="window-door-contractor-seo-phoenix", name="Windows & Doors", short="window & door",
   h1a="Window & door contractors:", h1b="the map decides who quotes the job.",
   searches=["window replacement near me","door installation phoenix","energy efficient windows phoenix","window repair near me","french door installation"],
   ticket="$8,000–$20,000", jobword="a whole-home window replacement",
   pain="Homeowners replacing windows collect two or three quotes and stop. Those quotes go to whoever appears in the map pack when they search — everyone else never hears the phone ring.",
   angle="Desert heat makes energy-efficient replacement a year-round search in Phoenix. The contractors winning it are rarely the best installers — they're the ones with complete profiles, steady reviews, and city pages Google can actually read.",
   desc='Window and door contractor SEO across the Phoenix metro. Own the map for “window replacement near me”: geo-grid tracking, review flow, call attribution.',
   status="Phoenix is taken (Econ Windows). All other territories open.", taken=True),
 dict(slug="roofing-contractor-seo-phoenix", name="Roofing", short="roofing",
   h1a="Roofers:", h1b="monsoon season is a search term.",
   searches=["roof repair phoenix","roofing companies near me","tile roof repair","roof replacement cost phoenix","emergency roof repair"],
   ticket="$10,000–$30,000", jobword="a full re-roof",
   pain="After every monsoon cell rolls through, search volume for roof repair spikes for a week. The roofers who own the map that week book out their month. Everyone else chases storm chasers' leftovers.",
   angle="Roofing is the most review-sensitive trade on the list — homeowners are terrified of getting burned. A profile with steady, recent reviews and photo proof of local work converts searches the big lead-gen sites can't touch.",
   desc='Roofing SEO in Phoenix. Every monsoon cell spikes roof repair searches for a week — the roofers who own the map that week book out the month.',
   status="All territories open.", taken=False),
 dict(slug="garage-door-company-seo-phoenix", name="Garage Doors", short="garage door",
   h1a="Garage door companies:", h1b="broken spring searches happen at 7am.",
   searches=["garage door repair near me","garage door spring replacement","garage door installation phoenix","garage door opener repair"],
   ticket="$400–$4,000", jobword="a door replacement",
   pain="Garage door work is same-day urgency: the door won't open, the car is trapped, and the homeowner calls the first number on the map. Second place doesn't get a callback.",
   angle="This trade is plagued by bait-and-switch national call centers ranking on the map with fake local addresses. A genuinely local, verified profile with real reviews is the exact thing Google has been rewarding — and homeowners are actively looking for it.",
   desc='Garage door SEO in Phoenix. Broken-spring searches are same-day urgency, and homeowners call the first real local company on the map, not the call centers.',
   status="All territories open.", taken=False),
 dict(slug="hvac-contractor-seo-phoenix", name="HVAC", short="HVAC",
   h1a="HVAC contractors:", h1b="in Phoenix, AC failure is an emergency.",
   searches=["ac repair phoenix","hvac companies near me","ac not cooling","ac replacement cost phoenix","emergency ac repair"],
   ticket="$6,000–$15,000", jobword="a system replacement",
   pain="When it's 114° and the AC quits, nobody scrolls past the top three. Summer search volume in this metro is enormous and brutally local — the map decides who answers the emergency and who quotes the replacement that follows.",
   angle="HVAC is the most competitive map in the Valley, which means half-built profiles die here. Complete service categories, review velocity, and city pages are the minimum table stakes — and most independent shops have none of the three.",
   desc="HVAC SEO in Phoenix, where a failed AC is an emergency. The Valley's most competitive map — complete categories, review velocity and city pages are table stakes",
   status="All territories open.", taken=False),
 dict(slug="painting-contractor-seo-phoenix", name="Painting", short="painting",
   h1a="Painters:", h1b="sun-blasted stucco is your lead engine.",
   searches=["exterior painters phoenix","house painters near me","stucco painting phoenix","interior painting cost","cabinet painting near me"],
   ticket="$3,000–$8,000", jobword="an exterior repaint",
   pain="Arizona sun destroys exterior paint on a schedule — every neighborhood repaints in waves. The painter who owns the map in that neighborhood picks up the whole wave; the rest bid against each other on Nextdoor.",
   angle="Painting buyers lean harder on photos than any other trade. A profile with a steady stream of before/after uploads outranks and outconverts bigger companies posting nothing.",
   desc='Painting contractor SEO in Phoenix. Arizona sun repaints neighborhoods in waves; the painter who owns that map picks up the whole wave, not one bid.',
   status="All territories open.", taken=False),
 dict(slug="flooring-contractor-seo-phoenix", name="Flooring", short="flooring",
   h1a="Flooring contractors:", h1b="tile and LVP searches never stop here.",
   searches=["flooring installation phoenix","tile installers near me","vinyl plank flooring installation","carpet replacement phoenix"],
   ticket="$4,000–$12,000", jobword="a whole-home flooring job",
   pain="Flooring is showroom-versus-installer warfare: big-box stores capture searches and sub the work out. Independent installers with a strong map presence take those same customers direct — at direct pricing.",
   angle="Most flooring installers have profiles listing two categories out of nine and zero city pages. That gap is the whole opportunity — the searches exist, the competition on the map is thinner than the work deserves.",
   desc='Flooring installer SEO in Phoenix. Take tile and LVP searches direct from the big-box showrooms — the map competition here is thinner than the work deserves.',
   status="All territories open.", taken=False),
 dict(slug="shutters-shade-contractor-seo-phoenix", name="Shutters & Shade", short="shutters & shade",
   h1a="Shutter & shade companies:", h1b="everyone in this valley wants shade.",
   searches=["plantation shutters phoenix","patio shade installation","motorized shades near me","awning installation phoenix","sun screens phoenix"],
   ticket="$2,500–$10,000", jobword="a whole-home shutter install",
   pain="Shade is a permanent Phoenix priority, but the search landscape is fragmented across shutters, screens, awnings, and pergolas. Companies that structure their profile and pages around every variant capture demand competitors don't even see.",
   angle="This trade has the least sophisticated local SEO competition on our list. Basic work done properly — categories, service pages, review flow — moves the map faster here than anywhere else.",
   desc='Shutters, screens, awnings and shade SEO in Phoenix. The least contested map on our list: categories and service pages move it faster than anywhere else.',
   status="All territories open.", taken=False),
 dict(slug="glass-shower-door-seo-phoenix", name="Glass & Shower Doors", short="glass & shower door",
   h1a="Glass & shower door companies:", h1b="frameless is a map-pack purchase.",
   searches=["shower door installation phoenix","frameless shower doors near me","glass replacement phoenix","mirror installation near me"],
   ticket="$1,200–$5,000", jobword="a frameless enclosure",
   pain="Shower glass buyers are remodelers mid-project — they need it measured this week and installed before the contractor's punch list. They call the top of the map and book the first company that answers with a date.",
   angle="Glass shops live off remodel timing, which makes response speed and review recency the ranking levers that matter. Call tracking proves which searches book — and which slip to the shop one pin over.",
   desc='Glass and shower door SEO in Phoenix. Frameless buyers are mid-remodel and book the first shop that answers with a date. Map visibility and review recency decide.',
   status="All territories open.", taken=False),
]

TRADE_INDEX = {t['slug']: t for t in TRADES}


TOKENS = {
    '{{PHONE_TEL}}':     PHONE_TEL,
    '{{PHONE_DISPLAY}}': PHONE_DISPLAY,
    '{{EMAIL}}':         EMAIL,
    '{{BASE}}':          BASE,
    '{{YEAR}}':          YEAR,
}

def subst(text):
    """Fill {{TOKEN}} placeholders in a source file with the configured values."""
    for k, v in TOKENS.items():
        text = text.replace(k, v)
    left = re.findall(r'\{\{[A-Z_]+\}\}', text)
    if left:
        raise SystemExit(f"build.py: unknown token(s) in source: {sorted(set(left))}")
    return text

CSS = subst(open(os.path.join(SRC,'main.css')).read())
JS  = subst(open(os.path.join(SRC,'main.js')).read())
# Loaded before the home page so it can link them.
CITY_PAGES = json.loads(subst(open(os.path.join(SRC,'cities.json')).read()))['cities']

# extra CSS for subpages
CSS += """
/* subpage chrome */
.pagehead{background:var(--ink);color:var(--paper);position:relative;overflow:hidden}
.pagehead::before{content:"";position:absolute;inset:0;background-image:radial-gradient(rgba(245,242,236,.055) 1px,transparent 1px);background-size:26px 26px;pointer-events:none}
.pagehead::after{content:"";position:absolute;top:-260px;right:-200px;width:640px;height:640px;background:radial-gradient(circle,rgba(240,86,30,.2),transparent 62%);pointer-events:none}
.pagehead .wrap{position:relative;z-index:1;padding-top:clamp(44px,6vw,76px);padding-bottom:clamp(44px,6vw,76px)}
.crumbs{font-family:var(--disp);font-weight:600;font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim-dark);margin-bottom:18px}
.crumbs a:hover{color:var(--orange-hot)}
.pagehead h1{font-size:clamp(40px,6.5vw,76px);max-width:16ch}
.pagehead .hero-sub{margin-bottom:clamp(22px,3vw,32px)}
.searchtags{display:flex;flex-wrap:wrap;gap:9px;margin:4px 0 26px}
.searchtags span{font-family:var(--disp);font-weight:700;font-size:13.5px;letter-spacing:.08em;text-transform:uppercase;color:rgba(245,242,236,.75);border:1px solid rgba(245,242,236,.25);padding:7px 13px}
/* Inline SVG magnifier rather than U+1F50D. The emoji was requesting text
   presentation via U+FE0E, which most systems have no glyph for — colour emoji
   fonts only ship the emoji presentation — so it rendered as tofu. */
.searchtags span::before{content:"";display:inline-block;width:.82em;height:.82em;margin-right:.55em;vertical-align:-.06em;opacity:.6;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23F5F2EC' stroke-width='2.4' stroke-linecap='round'%3E%3Ccircle cx='10.5' cy='10.5' r='6.5'/%3E%3Cpath d='M15.5 15.5 L21 21'/%3E%3C/svg%3E") center/contain no-repeat}
.two-col{display:flex;flex-wrap:wrap;gap:clamp(26px,4vw,56px)}
.two-col>div{flex:1 1 380px}
.prose p{color:var(--steel);margin-bottom:16px;max-width:62ch}
.prose p b{color:var(--ink)}
.prose h2,.prose h3{font-family:var(--disp);font-weight:800;text-transform:uppercase;font-size:clamp(26px,3.4vw,36px);margin:28px 0 12px}
.ticket-box{background:var(--white);border:1px solid var(--line-l);border-left:4px solid var(--orange);padding:22px 24px;margin:22px 0}
.ticket-box b{font-family:var(--disp);font-weight:900;font-size:clamp(28px,3.4vw,38px);display:block;line-height:1.05}
.ticket-box span{font-family:var(--disp);font-weight:600;font-size:12.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}
.avail{display:inline-flex;align-items:center;gap:10px;font-family:var(--disp);font-weight:800;font-size:14px;letter-spacing:.14em;text-transform:uppercase;border:1px solid var(--line-l);padding:10px 16px;margin:6px 0 20px}
.avail i{width:9px;height:9px;border-radius:50%}
.avail.open{color:var(--green)}.avail.open i{background:var(--green)}
.avail.part{color:var(--red)}.avail.part i{background:var(--red)}
.contact-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:18px}
.ccard{background:var(--white);border:1px solid var(--line-l);border-top:4px solid var(--orange);padding:26px}
.ccard h3{font-family:var(--disp);font-weight:800;text-transform:uppercase;font-size:22px;margin-bottom:8px}
.ccard p{color:var(--steel);font-size:15px;margin-bottom:14px}
.ccard a.big-link{font-family:var(--disp);font-weight:800;font-size:20px;color:var(--orange);letter-spacing:.04em}
.legal{max-width:760px}
.legal h2{font-family:var(--disp);font-weight:800;text-transform:uppercase;font-size:24px;margin:26px 0 10px}
.legal p,.legal li{color:var(--steel);font-size:15.5px;margin-bottom:12px}
.legal ul{padding-left:22px}
.tradelinks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:14px}
.tl{background:var(--white);border:1px solid var(--line-l);padding:20px 22px;display:flex;align-items:center;justify-content:space-between;gap:12px;font-family:var(--disp);font-weight:800;font-size:18px;letter-spacing:.04em;text-transform:uppercase;transition:border-color .15s,transform .15s}
.tl:hover{border-color:var(--orange);transform:translateY(-2px)}
.tl .go{color:var(--orange)}
"""

def nav(active=""):
    def a(href, label, key):
        # .nav-item keeps these text links out of the way of .nav-phone and .btn,
        # which are siblings in .nav-links and must not inherit link styling.
        cls = "nav-item on" if key == active else "nav-item"
        return f'<a class="{cls}" href="{href}">{label}</a>'
    return f'''<nav class="nav" aria-label="Main">
  <div class="wrap">
    <a class="logo" href="/" aria-label="Serpens Studio — home">
      <span class="logo-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M4 19 L4 6 L10 6 L10 11 L14 11 L14 6 L20 6 L20 19 L14 19 L14 14 L10 14 L10 19 Z" fill="#fff"/></svg></span>
      <span><b>Serpens</b><small>Studio · Phoenix AZ</small></span>
    </a>
    <div class="nav-links">
      {a('/#trades','Trades','trades')}
      {a('/pricing/','Pricing','pricing')}
      {a('/websites/','Websites','websites')}
      {a('/results/econ-windows/','Results','results')}
      {a('/process/','Process','process')}
      <a class="nav-phone" href="tel:{PHONE_TEL}" aria-label="Call Serpens Studio">
        <svg viewBox="0 0 24 24"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.9 21 3 13.1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.2.2 2.4.6 3.6.1.3 0 .7-.2 1l-2.3 2.2z"/></svg>
        <span>{PHONE_DISPLAY}</span>
      </a>
      <a class="btn" href="/free-scan/">Free Scan <span class="ar">→</span></a>
    </div>
  </div>
</nav>'''

def footer():
    # All eight: site-wide link for every trade page.
    trade_links = "\n        ".join(f'<a href="/{t["slug"]}/">{html.escape(t["name"])} SEO</a>' for t in TRADES)
    # Site-wide links to the city pages.
    city_links = "\n        ".join(
        f'<a href="/{c["slug"]}/">{html.escape(c["city"])} SEO</a>' for c in CITY_PAGES)
    return f'''<footer>
  <div class="wrap">
    <div class="foot-top">
      <div class="foot-brand">
        <a class="logo" href="/"><span class="logo-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M4 19 L4 6 L10 6 L10 11 L14 11 L14 6 L20 6 L20 19 L14 19 L14 14 L10 14 L10 19 Z" fill="#fff"/></svg></span><span><b>Serpens</b><small>Studio · Phoenix AZ</small></span></a>
        <p>Local search for home improvement contractors across the Phoenix metro — windows, roofing, garage doors, HVAC and more. Geo-grid rank tracking, call attribution, honest monthly reporting.</p>
      </div>
      <div class="foot-col">
        <h4>Trades</h4>
        {trade_links}
        <a href="/websites/">Contractor Website Design</a>
      </div>
      <div class="foot-col">
        <h4>Cities</h4>
        {city_links}
      </div>
      <div class="foot-col">
        <h4>Company</h4>
        <a href="/pricing/">Pricing</a>
        <a href="/process/">Process</a>
        <a href="/results/econ-windows/">Case Study</a>
        <a href="/about/">About</a>
        <a href="/free-scan/">Free Scan</a>
      </div>
      <div class="foot-col">
        <h4>Contact</h4>
        <a href="mailto:{EMAIL}">{EMAIL}</a>
        <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a>
        <a href="/contact/">Contact</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
      </div>
    </div>
    <div class="foot-bottom">
      <span>© {YEAR} Serpens Studio · Phoenix, Arizona</span>
      <span>Local SEO for home improvement contractors — {", ".join(CITIES[:8])}</span>
    </div>
  </div>
</footer>
<div class="mobile-cta">
  <a class="call" href="tel:{PHONE_TEL}">Call Now</a>
  <a class="scan" href="/free-scan/">Free Scan</a>
</div>'''

# Strip source TODOs from output.
NOTE_RE = re.compile(r'[ \t]*<!--\s*(?:TODO|FIXME|XXX|NOTE|REPLACE|WIRE-UP)\b.*?-->\n?', re.S)

def page(path, title, desc, body, active="", schema=None, extra_head=""):
    canonical = BASE + path
    schema_tag = f'\n<script type="application/ld+json">\n{json.dumps(schema, indent=1)}\n</script>' if schema else ""
    doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{GTM_HEAD}
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#14120F">
<meta name="geo.region" content="US-AZ"><meta name="geo.placename" content="Phoenix"><meta name="ICBM" content="33.4484, -112.0740">
<meta property="og:type" content="website"><meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="Serpens Studio">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:image" content="{BASE}/og.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Serpens Studio — local SEO for Phoenix contractors">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%2314120F'/%3E%3Cpath d='M8 22 L8 10 L14 10 L14 14 L20 14 L20 10 L24 10 L24 22 L18 22 L18 18 L12 18 L12 22 Z' fill='%23F0561E'/%3E%3C/svg%3E">
<link rel="preload" href="/fonts/BarlowCondensed-900.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/Barlow-400.woff2" as="font" type="font/woff2" crossorigin>
<script>document.documentElement.className+=" js"</script>
<link rel="stylesheet" href="{CSS_HREF}">{extra_head}{schema_tag}
</head>
<body>
{GTM_BODY}<a class="skip" href="#main">Skip to content</a>
{nav(active)}
<main id="main">
{body}
</main>
{footer()}
<script src="{JS_HREF}" defer></script>
</body>
</html>'''
    doc = NOTE_RE.sub('', doc)
    out = os.path.join(DIST, path.lstrip('/'))
    if path.endswith('/'):
        os.makedirs(out, exist_ok=True)
        out = os.path.join(out, 'index.html')
    else:
        os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out,'w').write(doc)
    return path

def crumbs(items):
    parts = []
    for i, (label, href) in enumerate(items):
        last = i == len(items) - 1
        parts.append(html.escape(label) if (last or not href)
                     else f'<a href="{href}">{html.escape(label)}</a>')
    return '<p class="crumbs">' + ' &nbsp;/&nbsp; '.join(parts) + '</p>'

def breadcrumb_schema(items):
    return {"@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":i+1,"name":lbl,"item":BASE+(href or "")}
        for i,(lbl,href) in enumerate(items)]}

# ---------------- ORG ENTITY ----------------
# Single definition. Google consolidates by @id, so don't redefine per-page;
# reference it with {"@id": BASE+"/#org"}.
ORG = {
  "@type": "ProfessionalService", "@id": BASE+"/#org", "name": "Serpens Studio",
  "url": BASE+"/", "email": EMAIL, "telephone": PHONE_TEL,
  "description": "Local SEO and website builds for home improvement contractors in the Phoenix "
                 "metro — windows and doors, roofing, garage doors, HVAC, painting, flooring, "
                 "shutters and shade, glass and shower doors. Google Business Profile management, "
                 "geo-grid rank tracking, call attribution, and monthly reporting. One contractor "
                 "per trade, per territory.",
  "areaServed": [{"@type":"City","name":c} for c in CITIES],
  # Service-area business: locality only, no street address, no geo.
  # areaServed + hasMap carry the location. SITE_GEO opts back in.
  "address": {"@type":"PostalAddress","addressLocality":"Phoenix","addressRegion":"AZ","addressCountry":"US"},
  # Keep in step with the pricing page.
  "priceRange": "$450–$5,500",
  "image": BASE+"/og.png",
  "logo": BASE+"/logo.png",
  "slogan": "The map decides who quotes the job.",
  "knowsAbout": [
    "Local SEO","Google Business Profile","Geo-grid rank tracking","Call tracking",
    "Citation building","Review management","Window and door contractor marketing",
    "Roofing contractor marketing","Garage door company marketing",
    "HVAC contractor marketing","Painting contractor marketing"],
}

# Optional; omitted when unset.
if SAME_AS:
    ORG["sameAs"] = SAME_AS
if GBP_URL:
    ORG["hasMap"] = GBP_URL

# Opt-in, see address note above.
_geo = env('SITE_GEO', '')
if _geo:
    try:
        _lat, _lng = (float(v) for v in _geo.split(','))
    except ValueError:
        raise SystemExit(f'build.py: SITE_GEO must look like "33.6738,-112.1070", got {_geo!r}')
    ORG["geo"] = {"@type": "GeoCoordinates", "latitude": _lat, "longitude": _lng}
if HOURS:
    ORG["openingHoursSpecification"] = HOURS

# Plans and prices.
ORG["hasOfferCatalog"] = json.loads(subst(open(os.path.join(SRC,'offer-catalog.json')).read()))

if os.path.exists(DIST): shutil.rmtree(DIST)
os.makedirs(os.path.join(DIST,'css')); os.makedirs(os.path.join(DIST,'js'))
os.makedirs(os.path.join(DIST,'img'), exist_ok=True)

# Content-hashed names so assets can be cached immutable for a year.
def hashed(subdir, name, ext, content):
    digest = hashlib.sha256(content.encode()).hexdigest()[:10]
    fname = f"{name}.{digest}{ext}"
    open(os.path.join(DIST, subdir, fname), 'w').write(content)
    return f"/{subdir}/{fname}"

CSS_HREF = hashed('css', 'main', '.css', CSS)
JS_HREF  = hashed('js',  'main', '.js',  JS)

# site-src/img -> dist/img, site-src/static -> dist. Skip docs/dotfiles.
SKIP_ASSETS = shutil.ignore_patterns('*.md', '.*', 'README*')
if os.path.isdir(os.path.join(SRC,'img')):
    shutil.copytree(os.path.join(SRC,'img'), os.path.join(DIST,'img'),
                    dirs_exist_ok=True, ignore=SKIP_ASSETS)
if os.path.isdir(os.path.join(SRC,'static')):
    shutil.copytree(os.path.join(SRC,'static'), DIST,
                    dirs_exist_ok=True, ignore=SKIP_ASSETS)

PAGES = []  # (path, changefreq, priority)
print("chrome ready")

# ---------------- HOME ----------------
# site-src/home.html is the canonical long-form single-page body; every sub-page below
# lifts its sections out of it, so this file is the one source of truth for that copy.
v3 = subst(open(os.path.join(SRC,'home.html')).read())
v3 = v3.replace('action="#"', f'action="{html.escape(FORM_ENDPOINT, quote=True)}"')
home_body = re.search(r'<main id="main">(.*?)</main>', v3, re.S).group(1)
home_body = home_body.replace('src="econ-site.jpg"','src="/img/econ-site.jpg"').replace('src="econ-job.jpg"','src="/img/econ-job.jpg"')
# link trade rows to trade pages
for t in TRADES:
    home_body = home_body.replace(f'<span class="tb-trade" role="cell">{t["name"].replace("&","&amp;")}</span>',
        f'<a class="tb-trade" role="cell" href="/{t["slug"]}/" style="color:inherit">{t["name"].replace("&","&amp;")}</a>')
# repoint anchors to real pages
# In-page anchors, not links to /free-scan/. The home page embeds the same form
# at #scan-embed and the full pricing table at #pricing, so sending a visitor to
# another page put a page load between intent and action. Sub-pages still get
# real links (they extract from v3 and rewrite separately).
home_body = home_body.replace('href="#scan"','href="#scan-embed"')
home_body = home_body.replace('id="scan"','id="scan-embed"')

# --- home-only sections ---
# Unique to the home page; also the hub linking the city pages.

RETAINER_SECTION = '''
<!-- ============ WHAT THE RETAINER BUYS ============ -->
<section class="sec" aria-labelledby="buys-h">
  <div class="wrap">
    <p class="kicker">What The Money Buys</p>
    <h2 class="disp" id="buys-h">A retainer is hours. <em>Here is where they go.</em></h2>
    <p class="sub">Every agency quotes a monthly number. Almost none will tell you what happens during the month. These are the standing line items on a Local Growth plan — the same list your monthly report is written against.</p>
    <div class="tradelinks" style="grid-template-columns:repeat(auto-fit,minmax(min(100%,290px),1fr))">
      <div class="ccard"><h3>Profile</h3><p>Every service category filled, not the two the setup wizard suggests. Hours, service areas, attributes and products kept current. Posts twice a month, questions answered before a competitor answers them for you.</p></div>
      <div class="ccard"><h3>Reviews</h3><p>A request goes out after every completed job, not in a quarterly blast. Responses drafted for you within a day — including the bad ones, which are read more carefully than the good ones.</p></div>
      <div class="ccard"><h3>Pages</h3><p>One new service or city page a month, written for a search someone actually makes, with the schema and internal links already wired. Twelve pages a year that compound instead of twelve blog posts that don't.</p></div>
      <div class="ccard"><h3>Citations</h3><p>The aggregators and trade directories that feed Google, built and then monitored — because the failure mode is not missing listings, it is three listings with three different phone numbers.</p></div>
      <div class="ccard"><h3>Tracking</h3><p>A tracking number on the profile and the site, every call recorded and attributed to the search that produced it. This is how you find out the map is working before the rankings move.</p></div>
      <div class="ccard"><h3>The Report</h3><p>First week of the month, one page: calls with sources, your geo-grid against last month, and the work completed. If you cannot tell what you paid for, that is our failure, and you are month to month.</p></div>
    </div>
    <p class="tb-note" style="margin-top:22px">Plans differ in how much of the above runs each month, not in whether you get a real person. <a href="/pricing/" style="color:var(--orange);font-weight:700">Compare the three plans →</a></p>
  </div>
</section>'''

_city_cards = "\n      ".join(
    f'<a class="tl" href="/{c["slug"]}/"><span>{html.escape(c["city"])}</span>'
    f'<span class="go">→</span></a>' for c in CITY_PAGES)

TERRITORY_SECTION = f'''
<!-- ============ TERRITORIES ============ -->
<section class="sec alt" aria-labelledby="terr-h">
  <div class="wrap">
    <p class="kicker">Where We Work</p>
    <h2 class="disp" id="terr-h">The Valley is not <em>one market.</em></h2>
    <p class="sub">A roof in Sun City and a roof in Gilbert are the same job and completely different searches — different housing stock, different buyers, different competition on the map. We sell the metro in six territories, and take one contractor per trade in each.</p>
    <div class="tradelinks">{_city_cards}</div>
    <p class="tb-note" style="margin-top:20px">Phoenix proper is covered from this page. Territories: {TERRITORIES}. Outside those lines — Cave Creek, Queen Creek, Surprise, Goodyear, Buckeye, Fountain Hills, Anthem, Litchfield Park, Apache Junction — we still scan, we just hold fewer slots. <a href="/free-scan/" style="color:var(--orange);font-weight:700">Ask about your area →</a></p>
  </div>
</section>'''

# Insert before the CTA so the form stays last.
home_body = home_body.replace('<!-- ============ CTA / FORM ============ -->',
                              RETAINER_SECTION + TERRITORY_SECTION +
                              '\n<!-- ============ CTA / FORM ============ -->', 1)
# home-schema.json holds only the page-scoped nodes (WebPage, FAQPage); the
# organisation comes from the shared ORG so all 19 pages agree on it.
_home_nodes = json.loads(subst(open(os.path.join(SRC,'home-schema.json')).read()))['@graph']
home_schema = {"@context":"https://schema.org","@graph":[ORG] + _home_nodes}
v3s = json.dumps(home_schema).replace("https://serpens.studio", BASE)
PAGES.append((page("/", "Local SEO for Phoenix Contractors | Serpens Studio",
  "Google Maps visibility for Phoenix contractors: geo-grid rank tracking, call attribution, public pricing. One contractor per trade, per territory. Free scan.",
  home_body, active="", schema=json.loads(v3s)), "weekly", "1.0"))

# ---------------- TRADE PAGES ----------------
def trade_page(t):
    items = [("Home","/"),("Trades","/#trades"),(t["name"], f'/{t["slug"]}/')]
    tags = "".join(f'<span>{html.escape(s)}</span>' for s in t["searches"])
    avail_cls = "part" if t["taken"] else "open"
    # Sibling links, so trade pages pass equity to each other.
    siblings = "\n      ".join(
        f'<a class="tl" href="/{o["slug"]}/"><span>{html.escape(o["name"])} SEO</span>'
        f'<span class="go">→</span></a>'
        for o in TRADES if o["slug"] != t["slug"])
    body = f'''
<header class="pagehead">
  <div class="wrap">
    {crumbs(items)}
    <h1>{html.escape(t["h1a"])} <em>{html.escape(t["h1b"])}</em></h1>
    <p class="hero-sub">These are the searches deciding who quotes {t["short"]} work in the Phoenix metro right now:</p>
    <div class="searchtags" aria-label="Searches your customers make">{tags}</div>
    <div class="hero-cta">
      <a class="btn big" href="/free-scan/">Get Your Free {html.escape(t["name"])} Scan <span class="ar">→</span></a>
      <a class="btn big outline" href="/pricing/">See Pricing</a>
    </div>
  </div>
</header>
<section class="sec">
  <div class="wrap two-col">
    <div class="prose">
      <p class="kicker">The Problem</p>
      <h2 style="margin-top:0">Why the map decides</h2>
      <p>{html.escape(t["pain"])}</p>
      <p>{html.escape(t["angle"])}</p>
      <h2>What we do about it</h2>
      <p>The same playbook we run for every trade on our list, tuned to {t["short"]} searches: a <b>complete Google Business Profile</b> with every service category filled, <b>review requests after every completed job</b>, <b>service and city pages</b> Google can actually rank, citations cleaned and built, and <b>call tracking</b> so every booked job traces back to the search that produced it.</p>
      <p>Then, every month, you get the geo-grid: your ranking for {t["short"]} searches measured from 49 points across your service area. <a href="/process/" style="color:var(--orange);font-weight:700">Here is the full process.</a></p>
    </div>
    <div>
      <div class="ticket-box">
        <span>Typical job value in this trade</span>
        <b>{html.escape(t["ticket"])}</b>
        <span>One {html.escape(t["jobword"])} from the map covers months of this work</span>
      </div>
      <p class="kicker" style="margin-top:26px">Territory Status</p>
      <span class="avail {avail_cls}"><i></i>{html.escape(t["status"])}</span>
      <p style="color:var(--steel);font-size:15px;max-width:44ch">We take one {t["short"]} company per territory: {TERRITORIES}. When your slot is filled, it is filled until that client leaves.</p>
      <div class="ticket-box" style="border-left-color:var(--ink)">
        <span>Monthly plans</span>
        <b>$450 / $950 / $1,850</b>
        <span>+ $1,000 setup · every price public · <a href="/pricing/" style="color:var(--orange)">full pricing</a></span>
      </div>
    </div>
  </div>
</section>
<section class="sec dark-band">
  <div class="wrap">
    <p class="kicker">Also Available</p>
    <h2 class="disp" style="color:#F5F2EC">Need the website too?</h2>
    <p class="sub">New build or full redesign — service pages, city pages, schema, lead capture, and call tracking wired from day one. $5,500 standalone, $4,000 with any monthly plan. <a href="/websites/" style="color:var(--orange-hot);font-weight:700">Website builds →</a></p>
    <a class="btn" href="/free-scan/">Start With a Free Scan <span class="ar">→</span></a>
  </div>
</section>
<section class="sec alt">
  <div class="wrap">
    <p class="kicker">The Other Trades</p>
    <h2 class="disp">Same playbook, <em>different map.</em></h2>
    <p class="sub">One contractor per trade, per territory — so these are running in parallel, never against you.</p>
    <div class="tradelinks">{siblings}</div>
  </div>
</section>'''
    schema = {"@context":"https://schema.org","@graph":[
      ORG,
      {"@type":"Service","name":f"Local SEO for {t['name']} Contractors","serviceType":"Local search engine optimization",
       "provider":{"@id":BASE+"/#org"},
       "areaServed":[{"@type":"City","name":c} for c in CITIES[:8]],
       "description":f"Google Business Profile management, geo-grid rank tracking, review generation, citation building, and call attribution for {t['short']} contractors in the Phoenix metro. One contractor per territory."},
      breadcrumb_schema(items)]}
    return page(f'/{t["slug"]}/',
      f"{t['name']} SEO Phoenix AZ | Serpens Studio",
      t["desc"],
      body, active="trades", schema=schema)

for t in TRADES:
    PAGES.append((trade_page(t), "monthly", "0.9"))

print("home + trades done")

# ---------------- CITY PAGES ----------------
# Phoenix is intentionally absent: the home page targets it already.
# Copy lives in site-src/cities.json.

def city_page(c):
    items = [("Home","/"),(f'{c["city"]} SEO', f'/{c["slug"]}/')]
    picks = [TRADE_INDEX[s] for s in c["trades"]]
    cards = "\n      ".join(
        f'<a class="tl" href="/{t["slug"]}/"><span>{html.escape(t["name"])}</span>'
        f'<span class="go">→</span></a>' for t in picks)
    hoods = ", ".join(html.escape(n) for n in c["neighborhoods"][:-1]) + \
             " and " + html.escape(c["neighborhoods"][-1])
    faq_html = "\n      ".join(
        f'<details><summary>{html.escape(f["q"])}<span class="x">+</span></summary>'
        f'<p class="a">{html.escape(f["a"])}</p></details>'
        for f in c["faqs"])
    _byslug = {x["slug"]: x for x in CITY_PAGES}
    nearby_html = "\n      ".join(
        f'<a class="tl" href="/{n}/"><span>{html.escape(_byslug[n]["city"])}</span>'
        f'<span class="go">→</span></a>' for n in c["nearby"] if n in _byslug)
    others = [t for t in TRADES if t["slug"] not in c["trades"]]
    other_links = " · ".join(
        f'<a href="/{t["slug"]}/" style="color:var(--orange);font-weight:600">{html.escape(t["name"])}</a>'
        for t in others)
    body = f'''
<header class="pagehead">
  <div class="wrap">
    {crumbs(items)}
    <h1>{html.escape(c["city"])} contractors: <em>{html.escape(c["hook"])}</em></h1>
    <p class="hero-sub">{html.escape(c["sub"])}</p>
    <div class="hero-cta">
      <a class="btn big" href="/free-scan/">Scan My {html.escape(c["city"])} Ranking <span class="ar">→</span></a>
      <a class="btn big outline" href="/pricing/">See Pricing</a>
    </div>
  </div>
</header>
<section class="sec">
  <div class="wrap two-col">
    <div class="prose">
      <p class="kicker">The Market</p>
      <h2 style="margin-top:0">What {html.escape(c["city"])} actually looks like</h2>
      <p>{html.escape(c["market"])}</p>
      <p><b>Where the work is:</b> {hoods}. Naming the areas you actually serve — on your profile and on your pages — is one of the cheapest relevance signals available, and most of your competitors have not bothered.</p>
      <h2>Why the map decides here</h2>
      <p>{html.escape(c["why"])}</p>
      <p>The work itself is the same playbook we run in every territory — a complete Google Business Profile, review requests after every job, service and city pages Google can read, citations cleaned and built, and call tracking so every booked job traces back to the search that produced it. <a href="/process/" style="color:var(--orange);font-weight:700">The full process is published here.</a></p>
    </div>
    <div>
      <p class="kicker">Territory</p>
      <div class="ticket-box">
        <span>This city sits in</span>
        <b>{html.escape(c["territory"])}</b>
        <span>{html.escape(c["note"])}</span>
      </div>
      <p class="kicker" style="margin-top:26px">Trades That Index Hardest Here</p>
      <p style="color:var(--steel);font-size:15px;max-width:44ch">{html.escape(c["trades_why"])}</p>
      <div class="ticket-box" style="border-left-color:var(--ink)">
        <span>Monthly plans</span>
        <b>$450 / $950 / $1,850</b>
        <span>+ $1,000 setup · every price public · <a href="/pricing/" style="color:var(--orange)">full pricing</a></span>
      </div>
    </div>
  </div>
</section>
<section class="sec alt">
  <div class="wrap">
    <p class="kicker">In {html.escape(c["city"])}</p>
    <h2 class="disp">Start with <em>your trade.</em></h2>
    <p class="sub">{html.escape(c["trades_why"])} Every trade below is available in this territory unless the page says otherwise.</p>
    <div class="tradelinks">{cards}</div>
    <p class="tb-note" style="margin-top:18px">Also covered here: {other_links}.</p>
  </div>
</section>
<section class="sec">
  <div class="wrap">
    <p class="kicker">{html.escape(c["city"])} Questions</p>
    <h2 class="disp">Asked and <em>answered.</em></h2>
    <div class="faq">{faq_html}</div>
  </div>
</section>
<section class="sec alt">
  <div class="wrap">
    <p class="kicker">Next Door</p>
    <h2 class="disp">Work the <em>neighbouring territories?</em></h2>
    <p class="sub">Territories are sold separately, so holding one does not stop you quoting across the line — it just means someone else may be doing this work there.</p>
    <div class="tradelinks">{nearby_html}</div>
  </div>
</section>
<section class="sec dark-band">
  <div class="wrap">
    <h2 class="disp" style="color:#F5F2EC">See your {html.escape(c["city"])} map. <em>Free.</em></h2>
    <p class="sub">Forty-nine points across your service area, the three competitors taking your searches, and the two or three things costing you the most visibility. Two business days, no obligation.</p>
    <a class="btn" href="/free-scan/">Get the Free Scan <span class="ar">→</span></a>
  </div>
</section>'''
    schema = {"@context":"https://schema.org","@graph":[
      ORG,
      {"@type":"Service",
       "name":f"Local SEO for {c['city']} Contractors",
       "serviceType":"Local search engine optimization",
       "provider":{"@id":BASE+"/#org"},
       "areaServed":{"@type":"City","name":c["city"],
                     "containedInPlace":{"@type":"AdministrativeArea","name":"Maricopa County, Arizona"}},
       "description":f"Google Business Profile management, geo-grid rank tracking, review generation, "
                     f"citation building and call attribution for home improvement contractors in "
                     f"{c['city']}, Arizona. One contractor per trade, per territory."},
      {"@type":"FAQPage",
       "mainEntity":[{"@type":"Question","name":f["q"],
                      "acceptedAnswer":{"@type":"Answer","text":f["a"]}} for f in c["faqs"]]},
      breadcrumb_schema(items)]}
    return page(f'/{c["slug"]}/',
      f"Contractor SEO {c['city']} AZ | Serpens Studio",
      c["sub"][:158],
      body, active="", schema=schema)

for c in CITY_PAGES:
    PAGES.append((city_page(c), "monthly", "0.8"))
print(f"{len(CITY_PAGES)} city pages done")

# ---------------- PRICING ----------------
pricing_src = re.search(r'(<!-- ============ PRICING ============ -->.*?)</section>', v3, re.S).group(1) + '</section>'
pricing_src = pricing_src.replace('href="#scan"','href="/free-scan/"').replace('id="pricing"','id="plans"')
web_src = re.search(r'(<!-- ============ WEBSITE BUILDS ============ -->.*?)</section>', v3, re.S).group(1) + '</section>'
web_src = web_src.replace('href="#scan"','href="/free-scan/"').replace('id="websites"','id="builds"')
items_p = [("Home","/"),("Pricing","/pricing/")]
pricing_body = f'''
<header class="pagehead"><div class="wrap">
  {crumbs(items_p)}
  <h1>Every price. <em>Public.</em></h1>
  <p class="hero-sub">Six numbers a contractor can hold in his head: $1,000 setup, $450 / $950 / $1,850 monthly, $5,500 website build ($4,000 on any plan). No custom quotes, no discovery-call gauntlet.</p>
</div></header>
{pricing_src}
{web_src}
<section class="sec"><div class="wrap">
  <p class="kicker">One More</p>
  <h2 class="disp">Profile suspended? <em>$1,200 — only if we win.</em></h2>
  <p class="sub">Google Business Profile reinstatement, success-only. You pay if and only if the profile is restored.</p>
  <a class="btn dark" href="/contact/">Talk To Us <span class="ar">→</span></a>
</div></section>
<section class="sec alt"><div class="wrap">
  <p class="kicker">Choosing</p>
  <h2 class="disp">Which number is <em>actually yours?</em></h2>
  <p class="sub">Three plans is enough to be honest and few enough to decide in a minute. The difference is not access to a better person — it is how much runs each month.</p>
  <div class="two-col">
    <div class="prose">
      <h3 style="margin-top:0">Take $450 if</h3>
      <p>Your profile exists, has some reviews, and the phone rings — just not as often as it should. You are protecting and tidying a position you already half-hold. Most single-truck operations start here and never need to move.</p>
      <h3>Take $950 if</h3>
      <p>You have crews to keep busy and a competitor visibly ahead of you on the map. This is the plan with geo-grid tracking and call attribution, which means it is the first plan where you can prove what happened. It is the one most contractors should be on.</p>
      <h3>Take $1,850 if</h3>
      <p>You are contesting a genuinely competitive territory — HVAC in the East Valley, roofing after a storm season — or you are running more than one location. Below that level of competition you would be buying hours you do not need.</p>
    </div>
    <div class="prose">
      <h3 style="margin-top:0">The setup fee, honestly</h3>
      <p>The $1,000 is a real month of work: auditing and rebuilding the profile, cleaning up the citation trail, fixing whatever the last agency left behind, and standing up call tracking. It is charged once, before the monthly work starts, because that first month is the month with the most work in it.</p>
      <h3>What changes the price</h3>
      <p><b>Nothing.</b> Not your revenue, not how badly you need it, not how the discovery call goes. The number on this page is the number on the agreement. If we ever charge for something that is not printed here, you are entitled to ask why — and the answer had better be a signed change to scope.</p>
      <h3>What the price does not include</h3>
      <p>Google Ads budget, which we do not manage. Photography, which you are better placed to take on the job. And any promise about rankings — <a href="/process/" style="color:var(--orange);font-weight:700">we guarantee deliverables, not positions</a>.</p>
    </div>
  </div>
</div></section>
<section class="sec"><div class="wrap">
  <p class="kicker">The Arithmetic</p>
  <h2 class="disp">One job, <em>most of the year.</em></h2>
  <p class="sub">This is the part that makes the numbers above small. The trades we work with all share a shape: a large enough average job that a single booking covers months of the retainer.</p>
  <div class="tradelinks">
    {"".join(f'<a class="tl" href="/{t["slug"]}/"><span>{html.escape(t["name"])}<br><small style="font-family:var(--body);font-weight:500;font-size:13.5px;letter-spacing:0;text-transform:none;color:var(--steel)">{html.escape(t["ticket"])} typical job</small></span><span class="go">→</span></a>' for t in TRADES)}
  </div>
  <p class="tb-note" style="margin-top:20px">At $950 a month, one {html.escape(TRADES[1]["jobword"])} covers roughly a year. We are not going to pretend that makes the decision for you — but it is the reason we publish the prices instead of qualifying you on a call.</p>
</div></section>'''
schema_p = {"@context":"https://schema.org","@graph":[ORG, breadcrumb_schema(items_p)]}
PAGES.append((page("/pricing/","Pricing — Contractor Local SEO Phoenix | Serpens Studio",
  "All prices public: $1,000 setup, plans at $450/$950/$1,850, website builds $5,500 ($4,000 on any plan). Month to month, no contracts.",
  pricing_body, active="pricing", schema=schema_p), "monthly", "0.9"))

# ---------------- WEBSITES ----------------
items_w = [("Home","/"),("Website Builds","/websites/")]
web_body = f'''
<header class="pagehead"><div class="wrap">
  {crumbs(items_w)}
  <h1>Built by the person <em>who has to rank it.</em></h1>
  <p class="hero-sub">Most contractor sites are built by someone who never has to make the phone ring afterward. Ours are the opposite: we build it, then we spend every month ranking it — so the build is engineered for that from day one.</p>
  <div class="hero-cta"><a class="btn big" href="/free-scan/">Start With a Free Scan <span class="ar">→</span></a></div>
</div></header>
{web_src}
<section class="sec"><div class="wrap two-col">
  <div class="prose">
    <p class="kicker">Why It Matters</p>
    <h2 style="margin-top:0">The cheap-build trap</h2>
    <p>The pattern we see over and over: a contractor pays a few grand, the designer disappears, and two years later the site is slow, outdated, or hacked. Our first client came to us with <b>roughly 24,000 spam URLs in Google's index</b> from exactly that story — a compromised site nobody was maintaining, quietly burning the crawl budget his service pages needed. <a href="/results/econ-windows/" style="color:var(--orange);font-weight:700">Read the case study.</a></p>
    <p>A site that ranks isn't a brochure with a phone number. It's service pages for every service you actually sell, city pages for every city you actually serve, structured data on every page, speed on a phone in the sun, and lead capture plus call tracking wired before launch.</p>
  </div>
  <div class="prose">
    <p class="kicker">Straight Terms</p>
    <h2 style="margin-top:0">What you get</h2>
    <p><b>Six weeks, either way.</b> New build or full redesign of what you have.</p>
    <p><b>You own it outright.</b> Domain, hosting account, code, content — yours. If you ever leave, we hand over everything and remove our access.</p>
    <p><b>No fake urgency, no page-count padding.</b> The scope is what ranks: services, cities, proof, contact. Nothing else.</p>
  </div>
</div></section>'''
schema_w = {"@context":"https://schema.org","@graph":[ORG,
  {"@type":"Service","name":"Contractor Website Build","provider":{"@id":BASE+"/#org"},
   "description":"New build or full redesign for Phoenix home improvement contractors: service pages, city pages, structured data, mobile speed, lead capture, call tracking. $5,500 standalone, $4,000 with any monthly plan. Six-week delivery.",
   "offers":[{"@type":"Offer","price":"5500","priceCurrency":"USD","name":"Standalone build"},
             {"@type":"Offer","price":"4000","priceCurrency":"USD","name":"Retainer client build"}]},
  breadcrumb_schema(items_w)]}
PAGES.append((page("/websites/","Contractor Website Design Phoenix | Serpens Studio",
  "Contractor sites built by the people who rank them: service pages, city pages, schema, call tracking. $5,500, or $4,000 on any plan. You own it.",
  web_body, active="websites", schema=schema_w), "monthly", "0.8"))

# ---------------- PROCESS ----------------
items_pr = [("Home","/"),("Process","/process/")]
proc_src = re.search(r'(<section class="sec" aria-labelledby="how-h">.*?)</section>', v3, re.S).group(1) + '</section>'
proc_src = proc_src.replace('href="#scan"','href="/free-scan/"')
grid_src = re.search(r'(<!-- ============ GEO GRID ============ -->.*?)</section>', v3, re.S).group(1) + '</section>'
grid_src = grid_src.replace('href="#scan"','href="/free-scan/"')
honest_src = re.search(r'(<!-- ============ HONESTY ============ -->.*?)</section>', v3, re.S).group(1) + '</section>'
proc_body = f'''
<header class="pagehead"><div class="wrap">
  {crumbs(items_pr)}
  <h1>No mystery. <em>This is the work.</em></h1>
  <p class="hero-sub">Most agencies keep the process vague because vagueness protects the retainer. Ours is published because the process is the pitch: defined deliverables, every month, with a map that shows whether they worked.</p>
</div></header>
{proc_src}
{grid_src}
{honest_src}
<section class="sec alt"><div class="wrap">
  <p class="kicker">The Timeline</p>
  <h2 class="disp">What the first six months <em>actually feel like.</em></h2>
  <p class="sub">Local SEO does not move in a straight line, and anyone who draws you a smooth upward curve is selling you one. Here is the shape it genuinely takes, so you can tell early whether it is working.</p>
  <div class="two-col">
    <div class="prose">
      <h3 style="margin-top:0">Weeks 1–2 — the boring part</h3>
      <p>Profile rebuilt, categories filled, citations audited and corrected, tracking number installed, baseline geo-grid captured. Nothing visible happens to your rankings. This is also where most of the setup fee goes, and where the errors that have been quietly capping you get found.</p>
      <h3>Months 1–2 — movement at the edges</h3>
      <p>The first thing that moves is almost never the centre pin. It is the grid points two or three miles out, where the competition is thinner. Your ranking from your own front door may not change at all yet. Reviews start arriving on a rhythm instead of by accident.</p>
    </div>
    <div class="prose">
      <h3 style="margin-top:0">Months 3–4 — the phone changes first</h3>
      <p>Call volume usually shifts before the map does, and the recordings tell you what kind of call it is. This is the point where attribution earns its place: you can see that the new calls are coming from search rather than from repeat customers or referrals.</p>
      <h3>Months 5–6 — the centre moves</h3>
      <p>Top-three coverage across the grid starts consolidating toward the middle. This is the first month the geo-grid comparison looks dramatic — and, not coincidentally, the first month it would be easy for us to take credit for something seasonal. The report separates the two.</p>
    </div>
  </div>
</div></section>
<section class="sec"><div class="wrap">
  <p class="kicker">Boundaries</p>
  <h2 class="disp">The tactics <em>we refuse.</em></h2>
  <p class="sub">A published process is only useful if it also says what is out of bounds. These are refusals, not upsells — none of them become available at a higher plan.</p>
  <div class="two-col">
    <div class="prose">
      <p><b>No fake reviews, ever.</b> Not written by us, not incentivised, not filtered so only happy customers get asked. It is against Google's policies, it is the fastest route to a suspension, and it is the one thing that would cost you the profile outright.</p>
      <p><b>No keyword-stuffed business name.</b> "Phoenix Roofing Repair Pros AZ" ranks until it is reported by a competitor and then it does not. Your business name in the profile is your business name.</p>
      <p><b>No fake locations.</b> Virtual offices and mailbox addresses to farm extra map pins are the exact tactic the national call centres use, and Google has spent years getting better at removing them.</p>
    </div>
    <div class="prose">
      <p><b>No ranking guarantees.</b> Nobody controls the algorithm. We guarantee the deliverables listed on this page and the report that proves they happened.</p>
      <p><b>No lock-in.</b> Month to month, thirty days' notice. If the work is worth paying for, it should survive you being free to leave.</p>
      <p><b>No hostage-taking.</b> Profile, citations, tracking numbers, site and content are yours. On the way out we hand over credentials and remove our access — which is, notably, the opposite of how most of this industry handles a cancellation.</p>
    </div>
  </div>
</div></section>
<section class="sec alt"><div class="wrap">
  <p class="kicker">Your Side</p>
  <h2 class="disp">What we need <em>from you.</em></h2>
  <p class="sub">Short list, and most of it is once. If a contractor tells you local SEO needs nothing from them, they are not doing local SEO.</p>
  <div class="two-col">
    <div class="prose">
      <h3 style="margin-top:0">In the first week</h3>
      <p><b>Manager access to your Google Business Profile.</b> Not ownership — you stay the owner, and you can remove us in two clicks whenever you like.</p>
      <p><b>Login to your website and domain</b>, or the name of whoever holds them. Half the delays we see are a former web designer who stopped answering emails.</p>
      <p><b>Your service list and real service area</b>, in your words. What you actually sell, and how far you will genuinely drive.</p>
    </div>
    <div class="prose">
      <h3 style="margin-top:0">Every month, about an hour</h3>
      <p><b>Photos from finished jobs.</b> Phone photos are fine. This is the single highest-value thing you can send us and the one we most often have to chase.</p>
      <p><b>Ask for the review.</b> We send the request and draft the responses, but the ask lands better from the person who did the work.</p>
      <p><b>Ten minutes on the report.</b> If something in it does not match what you saw on the ground, say so — the map is evidence, not proof.</p>
    </div>
  </div>
</div></section>
<section class="sec dark-band"><div class="wrap">
  <h2 class="disp" style="color:#F5F2EC">Every month, <em>in writing.</em></h2>
  <p class="sub">The first week of each month you get one page: calls from Google (recorded and attributed), your geo-grid versus last month, and the list of work completed. If a month ever goes by where you can't tell what you paid for, that's on us — and you're month to month, so you can act on it.</p>
  <p class="sub">How much of the above runs each month is the only thing that separates the three plans. <a href="/pricing/" style="color:var(--orange-hot);font-weight:700">Every price is published →</a></p>
  <a class="btn" href="/free-scan/">Start With a Free Scan <span class="ar">→</span></a>
</div></section>'''
PAGES.append((page("/process/","Our Process — Contractor Local SEO | Serpens Studio",
  "The full process, published: free 49-point scan, one-week setup, defined monthly deliverables, and a geo-grid report showing whether it worked.",
  proc_body, active="process", schema={"@context":"https://schema.org","@graph":[ORG, breadcrumb_schema(items_pr)]}), "monthly", "0.7"))

print("pricing/websites/process done")

# ---------------- FREE SCAN (conversion page) ----------------
items_fs = [("Home","/"),("Free Scan","/free-scan/")]
cta_src = re.search(r'(<!-- ============ CTA / FORM ============ -->.*?</section>)', v3, re.S).group(1)
fs_body = f'''
<header class="pagehead"><div class="wrap">
  {crumbs(items_fs)}
  <h1>The free scan, <em>explained.</em></h1>
  <p class="hero-sub">We check your real ranking for the search that matters in your trade from 49 points across your service area. You get the map — green where you're in the top three, red where you're invisible — whether or not you ever hire us.</p>
</div></header>
{cta_src}
<section class="sec"><div class="wrap two-col">
  <div class="prose">
    <p class="kicker">What Happens</p>
    <h2 style="margin-top:0">After you hit send</h2>
    <p><b>Within two business days</b> your scan lands by email: the geo-grid map, the three competitors currently taking your searches, and the two or three things costing you the most visibility.</p>
    <p><b>No follow-up sequence.</b> One email with the map. If it makes you want to talk, the number is on it. If not, keep the map — it's yours.</p>
  </div>
  <div class="prose">
    <p class="kicker">Why Free</p>
    <h2 style="margin-top:0">The map does the selling</h2>
    <p>Because it's the same artifact our clients get every month. If seeing your own map doesn't make the case, nothing we could say on a sales call would either — and we'd rather find that out in ten minutes than an hour.</p>
    <p><b>One contractor per trade, per territory.</b> If your slot is already taken, we'll tell you in the same email.</p>
  </div>
</div></section>'''
PAGES.append((page("/free-scan/","Free Visibility Scan — Phoenix Contractors | Serpens Studio",
  "A free 49-point scan of your Google ranking across your service area: the geo-grid map, your competitors, what's costing you. Two business days.",
  fs_body, active="", schema={"@context":"https://schema.org","@graph":[ORG, breadcrumb_schema(items_fs)]}), "monthly", "0.9"))

# ---------------- CASE STUDY ----------------
items_cs = [("Home","/"),("Results","/results/econ-windows/")]
case_src = re.search(r'(<!-- ============ CASE STUDY ============ -->.*?)</section>', v3, re.S).group(1) + '</section>'
case_src = case_src.replace('href="#scan"','href="/free-scan/"').replace('id="case"','id="econ"')
case_src = case_src.replace('src="econ-site.jpg"','src="/img/econ-site.jpg"').replace('src="econ-job.jpg"','src="/img/econ-job.jpg"')
cs_body = f'''
<header class="pagehead"><div class="wrap">
  {crumbs(items_cs)}
  <h1>Econ Windows: <em>24,000 spam URLs. Gone.</em></h1>
  <p class="hero-sub">A window and door contractor in Phoenix (AZ ROC 327319, 4.9★ across 83 Google reviews) whose previous site was compromised — and quietly burning the crawl budget his service pages needed.</p>
</div></header>
{case_src}
<section class="sec"><div class="wrap two-col">
  <div class="prose">
    <p class="kicker">What Happened</p>
    <h2 style="margin-top:0">The anatomy of a hacked build</h2>
    <p>The site was a single-page build from years earlier that nobody maintained. Somewhere along the way it was compromised, and by the time we scanned it, <b>roughly 24,000 spam URLs</b> sat in Google's index attached to the domain — pharma spam, junk pages, the usual. Google was spending its crawl budget on garbage instead of the pages that win jobs.</p>
    <p>The fix: mass removal of the spam URLs from the index, a full site rebuild with real service and city pages, a rebuilt Business Profile, and call tracking on everything so every booked job traces to its source.</p>
  </div>
  <div class="prose">
    <p class="kicker">Honest Numbers</p>
    <h2 style="margin-top:0">Why this page shows few metrics</h2>
    <p>Because the engagement is young and we don't publish numbers we can't stand behind. The tracking is installed; as verified ranking and call data matures, it publishes here. That's the same standard your monthly report gets.</p>
    <p><b>What's already true:</b> the spam is out of the index, the site is rebuilt, the profile is complete, and every call is recorded and attributed.</p>
  </div>
</div></section>
<section class="sec dark-band"><div class="wrap">
  <h2 class="disp" style="color:#F5F2EC">Got a similar mess? <em>Or just a quiet phone?</em></h2>
  <p class="sub">The scan finds both. Free, 49 points, two business days.</p>
  <a class="btn" href="/free-scan/">Get Your Free Scan <span class="ar">→</span></a>
</div></section>'''
PAGES.append((page("/results/econ-windows/","Case Study: 24,000 Spam URLs Removed | Serpens Studio",
  "A hacked, unmaintained site left a Phoenix window contractor with 24,000 spam URLs. We removed them, rebuilt site and profile, and tracked every call.",
  cs_body, active="results", schema={"@context":"https://schema.org","@graph":[ORG, breadcrumb_schema(items_cs)]}), "monthly", "0.8"))

# ---------------- ABOUT ----------------
items_ab = [("Home","/"),("About","/about/")]
ab_body = f'''
<header class="pagehead"><div class="wrap">
  {crumbs(items_ab)}
  <h1>One person. <em>On purpose.</em></h1>
  <p class="hero-sub">Serpens Studio is a one-person shop in Phoenix, Arizona. That's not a limitation we're apologizing for — it's the product.</p>
</div></header>
<section class="sec"><div class="wrap two-col">
  <div class="prose">
    <p class="kicker">The Model</p>
    <h2 style="margin-top:0">Why one person beats an account team</h2>
    <p>When you call, the person who answers is the person who does the work. No account manager relaying notes to an offshore fulfillment team, no ticket queue, no "let me check with the SEO department." The person reading your geo-grid built your geo-grid.</p>
    <p>It's also why the client list is capped by design: <b>one contractor per trade, per territory</b>, and a hard limit on total accounts. The economics of this business only stay honest if every client gets real hours every month.</p>
  </div>
  <div class="prose">
    <p class="kicker">The Rules</p>
    <h2 style="margin-top:0">What we hold ourselves to</h2>
    <p><b>Prices are always printed.</b> If a number isn't on the site, we don't charge it.</p>
    <p><b>Rankings are never promised.</b> Deliverables are — and they're listed, and reported on, monthly.</p>
    <p><b>You own everything.</b> Profile, citations, phone numbers, website. Leave any time; it all comes with you.</p>
    <p><b>Exclusivity is absolute.</b> Your fee never funds your competitor.</p>
  </div>
</div></section>'''
PAGES.append((page("/about/","About Serpens Studio — One-Person Local SEO Shop in Phoenix, AZ",
  "A one-person local SEO shop in Phoenix: the person who answers does the work. Printed prices, no promised rankings, absolute exclusivity.",
  ab_body, active="", schema={"@context":"https://schema.org","@graph":[ORG, breadcrumb_schema(items_ab)]}), "yearly", "0.5"))

print("scan/case/about done")

# ---------------- CONTACT ----------------
items_ct = [("Home","/"),("Contact","/contact/")]
ct_body = f'''
<header class="pagehead"><div class="wrap">
  {crumbs(items_ct)}
  <h1>Talk to <em>the person.</em></h1>
  <p class="hero-sub">No sales team, no scheduling gauntlet. Call, email, or start with the scan — same human either way.</p>
</div></header>
<section class="sec"><div class="wrap">
  <div class="contact-cards">
    <div class="ccard"><h3>Call</h3><p>Phoenix business hours, Arizona time. If it rings out, we're on a client — leave a message, same-day callback.</p><a class="big-link" href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a></div>
    <div class="ccard"><h3>Email</h3><p>Next-business-day response, usually faster. Attach anything — screenshots of your profile, your current site, whatever's bugging you.</p><a class="big-link" href="mailto:{EMAIL}">{EMAIL}</a></div>
    <div class="ccard"><h3>Or skip ahead</h3><p>The free scan is the best first conversation: you get the map, we both learn whether there's anything worth talking about.</p><a class="btn" href="/free-scan/">Get the Free Scan <span class="ar">→</span></a></div>
  </div>
  <div class="two-col" style="margin-top:clamp(30px,4vw,48px)">
    <div class="prose">
      <p class="kicker">Check Us The Way We'd Check You</p>
      <h2 style="margin-top:0">Our own profile is public</h2>
      <p>It would be a strange thing to sell Google Business Profile work from behind a profile you can't see. Ours is <a href="{GBP_URL}" rel="noopener" style="color:var(--orange);font-weight:700">here on Google Maps</a> — the same categories, posts, and review history we'd build for you, on the business asking you to trust it.</p>
      <p>If you're weighing us up, that profile is the honest place to start. Leaving a review there after we've worked together is also the single most useful thing a client can do for us, which is exactly why we ask yours to do it for you.</p>
    </div>
    <div class="prose">
      <p class="kicker">Straight Answer</p>
      <h2 style="margin-top:0">Where we are</h2>
      <p>Phoenix, Arizona. We're a service-area business — we come to you, across the six territories we cover, rather than running a showroom you'd never visit.</p>
      <p>Business hours are Arizona time, and Arizona doesn't observe daylight saving, so half the year we're on Pacific time and half the year we're on Mountain. If you're calling from out of state, that's the one thing worth checking.</p>
    </div>
  </div>
</div></section>'''
PAGES.append((page("/contact/","Contact Serpens Studio — Phoenix Local SEO for Contractors",
  "Call or email Serpens Studio in Phoenix, Arizona. One person, next-business-day responses, no sales team. Or start with the free 49-point visibility scan.",
  ct_body, active="", schema={"@context":"https://schema.org","@graph":[ORG, breadcrumb_schema(items_ct)]}), "yearly", "0.5"))

# ---------------- PRIVACY & TERMS ----------------
legal_note = ''
pv_body = f'''
<header class="pagehead"><div class="wrap">{crumbs([("Home","/"),("Privacy","/privacy/")])}<h1>Privacy <em>Policy</em></h1></div></header>
<section class="sec"><div class="wrap legal">{legal_note}
  <p>Effective {YEAR}. This site is operated by Serpens Studio, Phoenix, Arizona.</p>
  <h2>What we collect</h2>
  <p>If you request a free scan or contact us, we collect what you submit: business name, your name, phone, trade, and service area. Standard server logs and analytics record page visits and approximate location.</p>
  <h2>Call recording</h2>
  <p>Calls to our tracking numbers may be recorded for quality and attribution. Where recording is active, callers are notified at the start of the call.</p>
  <h2>How we use it</h2>
  <p>To deliver the scan you asked for, respond to inquiries, and operate our services. We do not sell your information. We do not send marketing sequences — if you request a scan, you get the scan.</p>
  <h2>Third parties</h2>
  <p>We use service providers for call tracking, analytics, email delivery, and hosting. Each receives only what it needs to perform its function.</p>
  <h2>Your choices</h2>
  <p>Email <a href="mailto:{EMAIL}" style="color:var(--orange)">{EMAIL}</a> to access or delete information we hold about you.</p>
</div></section>'''
PAGES.append((page("/privacy/","Privacy Policy | Serpens Studio","How Serpens Studio collects and uses information: scan requests, call recording notice, analytics, and your choices.",
  pv_body, schema=None), "yearly", "0.2"))

tm_body = f'''
<header class="pagehead"><div class="wrap">{crumbs([("Home","/"),("Terms","/terms/")])}<h1>Terms of <em>Service</em></h1></div></header>
<section class="sec"><div class="wrap legal">{legal_note}
  <p>Effective {YEAR}. These terms cover use of this website and summarize how engagements work; each engagement is governed by its signed scope of work.</p>
  <h2>Services</h2>
  <p>Monthly plans are month to month with thirty days written notice to cancel. The one-time setup fee is required before monthly work begins. Website builds are quoted at the published price and delivered per the signed scope.</p>
  <h2>Ownership</h2>
  <p>Clients own their Google Business Profile, citations, phone numbers, website, and content. On termination, we transfer all credentials and remove our access.</p>
  <h2>No ranking guarantees</h2>
  <p>We guarantee defined monthly deliverables and transparent reporting. We do not and cannot guarantee specific rankings, traffic, or lead volume.</p>
  <h2>Exclusivity</h2>
  <p>One contractor per trade, per territory, held as long as the client remains active.</p>
  <h2>Liability</h2>
  <p>To the maximum extent permitted by law, our aggregate liability is limited to fees paid in the three months preceding a claim.</p>
</div></section>'''
PAGES.append((page("/terms/","Terms of Service | Serpens Studio","Engagement terms: month-to-month plans, client ownership of all assets, no ranking guarantees, absolute territory exclusivity.",
  tm_body, schema=None), "yearly", "0.2"))

# ---------------- 404 ----------------
nf_body = f'''
<header class="pagehead"><div class="wrap" style="text-align:left">
  <h1>404. <em>Not found —</em> which is ironic, given what we do.</h1>
  <p class="hero-sub">The page moved or never existed. The good stuff is one click away.</p>
  <div class="hero-cta"><a class="btn big" href="/">Home <span class="ar">→</span></a><a class="btn big outline" href="/free-scan/">Free Scan</a></div>
</div></header>'''
# 404 as flat file
doc404_path = page("/404.html","Page Not Found | Serpens Studio","Page not found.", nf_body, schema=None)

# ---------------- robots + sitemap ----------------
open(os.path.join(DIST,'robots.txt'),'w').write(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")

# lastmod tracks real content changes, not build time.
# lastmod.json maps path -> {hash, date}; commit it with content edits.
MANIFEST = os.path.join(SRC, 'lastmod.json')
today = datetime.date.today().isoformat()
try:
    manifest = json.load(open(MANIFEST))
except (OSError, ValueError):
    manifest = {}

changed = 0
for p, _, _ in PAGES:
    out = os.path.join(DIST, p.lstrip('/'), 'index.html') if p.endswith('/') else os.path.join(DIST, p.lstrip('/'))
    body = re.search(r'<main id="main">(.*?)</main>', open(out).read(), re.S)
    digest = hashlib.sha256((body.group(1) if body else '').encode()).hexdigest()[:16]
    prev = manifest.get(p)
    if not prev or prev.get('hash') != digest:
        manifest[p] = {"hash": digest, "date": today}
        changed += 1
manifest = {p: manifest[p] for p, _, _ in PAGES}      # drop entries for deleted pages
json.dump(manifest, open(MANIFEST, 'w'), indent=1, sort_keys=True)
print(f"lastmod: {changed} page(s) changed content this build")

urls = "\n".join(
    f"  <url><loc>{BASE}{p}</loc><lastmod>{manifest[p]['date']}</lastmod>"
    f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
    for p,cf,pr in PAGES if p != "/404.html")
open(os.path.join(DIST,'sitemap.xml'),'w').write(
    f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n')

print("BUILD COMPLETE:", len(PAGES), "pages")
for p,_,_ in PAGES: print(" ", p)
