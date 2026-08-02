# ---------- stage 1: generate the static site ----------
FROM python:3.12-alpine AS build

WORKDIR /src

# Deploy-time configuration. Override these as Build Args in Dokploy
# (Application -> Build -> Build Args) — they are baked into the HTML.
ARG SITE_BASE_URL="https://serpens.studio"
ARG SITE_PHONE_DISPLAY="(602) 000-0000"
ARG SITE_PHONE_TEL="+16020000000"
ARG SITE_EMAIL="hello@serpens.studio"
ARG SITE_FORM_ENDPOINT="#"
ARG SITE_YEAR=""

ENV SITE_BASE_URL="$SITE_BASE_URL" \
    SITE_PHONE_DISPLAY="$SITE_PHONE_DISPLAY" \
    SITE_PHONE_TEL="$SITE_PHONE_TEL" \
    SITE_EMAIL="$SITE_EMAIL" \
    SITE_FORM_ENDPOINT="$SITE_FORM_ENDPOINT" \
    SITE_YEAR="$SITE_YEAR"

COPY build.py verify.py ./
COPY site-src ./site-src

# Build, then gate the deploy on the checks: verify.py exits non-zero on dead
# links, missing/duplicate titles or canonicals, invalid JSON-LD, leaked author
# notes, or sitemap entries that don't resolve. A bad build fails here instead of
# shipping. Warnings (placeholder phone, missing case-study photos) don't block.
RUN python3 build.py && python3 verify.py

# ---------- stage 2: serve ----------
FROM nginx:1.29-alpine

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx/site.conf /etc/nginx/conf.d/site.conf
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1
