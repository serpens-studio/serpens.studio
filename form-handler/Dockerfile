FROM python:3.12-alpine

WORKDIR /app
COPY handler.py .

# no root, no shell for the service account
RUN adduser -D -H -s /sbin/nologin scan
USER scan

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null 2>&1 || exit 1

CMD ["python3", "-u", "handler.py"]
