# Build:  docker build -t prediction-arb .
#         docker build --build-arg EXTRAS=trading -t prediction-arb:trading .   # live trading
# Run:    docker run --rm prediction-arb scan
#         docker run --rm --env-file .env -v "$PWD/data:/app/data" prediction-arb run
# Variables passed with --env-file are visible to anyone who can run `docker inspect`. For live
# trading, mount the Kalshi key read-only and use KALSHI_PRIVATE_KEY_PATH instead of the inline key:
#         -v "$HOME/.config/prediction-arb/kalshi.pem:/run/secrets/kalshi.pem:ro"
#         -e KALSHI_PRIVATE_KEY_PATH=/run/secrets/kalshi.pem
# Pinned by digest; Dependabot proposes updates.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ARG EXTRAS=""
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOG_FILE=""

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install ".${EXTRAS:+[$EXTRAS]}" \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /app/data \
    && chown app:app /app/data

USER app
VOLUME ["/app/data"]
ENTRYPOINT ["prediction-arb"]
CMD ["scan"]
