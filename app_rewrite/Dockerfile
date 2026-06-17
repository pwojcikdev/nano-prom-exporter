# Image for nano-prom-exporter.
# Build from inside app_rewrite/:
#   docker build -t nano-prom-exporter .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Unprivileged runtime user, created early so the layer stays cached.
RUN useradd --create-home --uid 10001 app

WORKDIR /app

# pyproject reads README.md at build time, so it must be present.
COPY pyproject.toml README.md ./
COPY nano_prom ./nano_prom

# prometheus-client, requests, and psutil all ship glibc wheels, so the slim
# (Debian) base needs no compiler toolchain.
RUN pip install .

USER app

ENTRYPOINT ["nano-prom"]
# Flags are passed at runtime and replace this default, e.g.:
#   docker run --rm nano-prom-exporter \
#     --host host.docker.internal --port 7076 --push_gateway http://pushgateway:9091
CMD ["--help"]
