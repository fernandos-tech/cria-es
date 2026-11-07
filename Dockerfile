# syntax=docker/dockerfile:1
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STUDIO_DATA_DIR=/data \
    PORT=10000
WORKDIR /app

# A development proxy CA can be mounted without being retained in the image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update && \
      apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates; \
    else \
      apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates; \
    fi && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --uid 10001 --create-home studio && \
    install -d -o studio -g studio /data

COPY --chown=studio:studio studio ./studio
USER studio
EXPOSE 10000
CMD ["sh", "-c", "exec python3 -m studio.server --host 0.0.0.0 --port \"${PORT:-10000}\""]
