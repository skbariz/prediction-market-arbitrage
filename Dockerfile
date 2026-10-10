# Build:  docker build -t prediction-arb .
#         docker build --build-arg EXTRAS=trading -t prediction-arb:trading .   # live trading
# Run:    docker run --rm prediction-arb scan
#         docker run --rm --env-file .env -v "$PWD/data:/app/data" prediction-arb run
FROM python:3.12-slim

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
