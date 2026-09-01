FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY docker-entrypoint.sh /usr/local/bin/loose-thread-entrypoint
RUN chmod +x /usr/local/bin/loose-thread-entrypoint

EXPOSE 8000
ENTRYPOINT ["loose-thread-entrypoint"]
