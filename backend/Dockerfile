# Three stages. `base` holds what both images share; `test` adds pytest and is
# built only by `make test-backend`; `runtime` is last so it is the default
# target and never contains test tooling.
FROM python:3.13-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first: this layer is rebuilt only when requirements.txt changes,
# not on every source edit.
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --system --no-create-home app


FROM base AS test

COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

COPY . .
USER app

CMD ["pytest"]


FROM base AS runtime

ENV WEB_CONCURRENCY=3

COPY . .
USER app

EXPOSE 8000

# Inline command (no entrypoint script) so nothing depends on a file's
# executable bit or line endings surviving the clone.
# TODO: migrating on start is only safe with one backend replica; with several,
# run migrations as a separate one-off step before the rollout.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --access-logfile -"]
