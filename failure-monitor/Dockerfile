# Built with the repo root as context (see docker-compose.yaml); the source lives in failure-monitor-local/.
FROM python:3.12-slim
WORKDIR /srv

# Optional extra CAs (e.g. corporate TLS inspection), see certs/README.md
COPY failure-monitor/certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY failure-monitor-local/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY failure-monitor-local/app/ app/
COPY failure-monitor-local/rules.yaml .
ENV RULES_PATH=/srv/rules.yaml
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
