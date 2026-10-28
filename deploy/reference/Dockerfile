# Reference image for one Sentinel agent (M10-L08). Build once, pin by digest, deploy the digest.
# Pin the base image by digest in your registry; the tag below is a placeholder for the course.
FROM python:3.12-slim

# No secrets in the image: no API keys, no cloud credentials, no .env. Credentials live outside the
# container (model gateway and egress proxy), and the image is scanned for them in CI.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
 && useradd --uid 10001 --create-home --shell /usr/sbin/nologin agent

# Run as the unprivileged user. The root filesystem is mounted read-only at runtime (compose.yaml);
# only /tmp and /workspace are writable tmpfs mounts that vanish with the container.
USER 10001:10001
# Your service wrapper: an HTTP handler behind an authenticating gateway that runs one agent session per request.
ENTRYPOINT ["python", "-m", "bayside_aml_service"]
