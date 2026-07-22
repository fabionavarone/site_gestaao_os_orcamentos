FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/provisao
RUN useradd --system --create-home app
COPY apps/api /srv/provisao/apps/api
COPY alembic.ini /srv/provisao/alembic.ini
COPY migrations /srv/provisao/migrations
RUN pip install --no-cache-dir -e /srv/provisao/apps/api && mkdir -p /var/lib/provisao/uploads && chown -R app:app /srv/provisao /var/lib/provisao
USER app
WORKDIR /srv/provisao/apps/api
