FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

WORKDIR /app

# Optional extra root CAs (corporate proxy / antivirus TLS inspection).
# Drop *.crt files in docker/certs/ (git-ignored); the folder may be empty.
COPY docker/certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates >/dev/null 2>&1 || true
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Dependencies first to benefit from the Docker layer cache
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .

# Run as an unprivileged user (least privilege)
RUN useradd --create-home --uid 1000 ymmo \
    && mkdir -p /app/media /app/reports /app/analytics/models \
    && chown -R ymmo:ymmo /app \
    && chmod +x /app/scripts/entrypoint.sh
USER ymmo

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
