# syntax=docker/dockerfile:1
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STUDIO_DATA_DIR=/data \
    STUDIO_MODEL_DIR=/data/models \
    AUTO_TRANSCRIBE=1 \
    PORT=10000
WORKDIR /app

# A development proxy CA can be mounted without being retained in the image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update && \
      apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates libgomp1; \
    else \
      apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates libgomp1; \
    fi && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --uid 10001 --create-home studio && \
    install -d -o studio -g studio /data

COPY requirements.txt ./requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      PIP_CERT=/run/secrets/proxy_ca python -m pip install --no-cache-dir -r requirements.txt; \
    else python -m pip install --no-cache-dir -r requirements.txt; fi
COPY --chown=studio:studio studio ./studio
USER studio
EXPOSE 10000
CMD ["sh", "-c", "exec python3 -m studio.server --host 0.0.0.0 --port \"${PORT:-10000}\""]
