FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GENFIN_DEBUG=False \
    USE_SQLITE=False \
    PORT=8000

WORKDIR /app

COPY requirements.lock.txt requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt \
    && useradd --create-home --uid 10001 genfin

COPY --chown=genfin:genfin . .
USER genfin

EXPOSE 8000
CMD ["sh", "scripts/entrypoint.sh"]
