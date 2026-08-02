# serpens.studio

Static site for Serpens Studio, Phoenix AZ. Python generator, nginx container,
no runtime dependencies.

## Build

```bash
python3 build.py      # -> dist/
python3 verify.py     # link/SEO/schema checks, non-zero on failure
python3 serve.py      # preview on :8080
```

No dependencies beyond python3.

## Layout

```
build.py            generator
verify.py           post-build checks
serve.py            local preview (mirrors nginx)
site-src/
  home.html         home body; sub-pages lift sections from it
  home-schema.json  home JSON-LD (WebPage + FAQPage)
  offer-catalog.json plans and prices
  cities.json       city page copy
  lastmod.json      per-page content hashes for sitemap lastmod
  main.css main.js
  img/ static/      copied into dist/
nginx/site.conf     server config
Dockerfile          build + serve
```

## Deploy

See [DEPLOY.md](DEPLOY.md). Config is via build args — `SITE_BASE_URL`,
`SITE_PHONE_DISPLAY`, `SITE_PHONE_TEL`, `SITE_EMAIL`, `SITE_FORM_ENDPOINT`,
`SITE_SAME_AS`, `SITE_HOURS`, `SITE_GEO`. Defaults in `.env.example`.

```bash
docker compose up --build     # :8080
```
