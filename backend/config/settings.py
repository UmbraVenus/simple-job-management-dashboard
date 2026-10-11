"""Django settings.

Every value comes from an environment variable with a working default, so a
fresh clone runs without a .env file. docker-compose.yml sets the real values.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    """Read a boolean from the environment.

    :param name: Environment variable name.
    :param default: Value used when the variable is not set.
    :returns: True for ``1``, ``true`` or ``yes`` (case-insensitive), else False.
    """
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


def env_list(name: str, default: str) -> list[str]:
    """Read a comma-separated list from the environment.

    :param name: Environment variable name.
    :param default: Comma-separated value used when the variable is not set.
    :returns: The items with surrounding whitespace removed and blanks dropped.
    """
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# TODO: no real secret management. The default key is public; a deployment must
# set DJANGO_SECRET_KEY. Nothing in this app signs data with it yet (no sessions).
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-only-key")
DEBUG = env_bool("DJANGO_DEBUG", False)

# nginx forwards the browser's Host header, so the service name `frontend` must
# be allowed: inside the compose network the E2E browser calls http://frontend.
# Strict by default; docker-compose.yml relaxes it to "*" for local runs.
# TODO: no authentication or authorization. Anyone who can reach the app can
# create, change and delete jobs. Deferred: not in the brief. Fix: DRF
# authentication + permission classes, an owner FK on Job, and ALLOWED_HOSTS
# set to the real hostname(s).
ALLOWED_HOSTS = [
    *env_list("DJANGO_ALLOWED_HOSTS", "localhost,[::1],frontend"),
    # Always allowed: the container healthcheck calls http://127.0.0.1:8000, so
    # restricting the list through the environment must not make it unhealthy.
    "127.0.0.1",
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "jobs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "jobs"),
        "USER": os.environ.get("POSTGRES_USER", "jobs"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "jobs"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        # Reuse connections between requests instead of reconnecting each time.
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# With DEBUG off Django logs nothing to the console by default; containers
# should log to stdout/stderr so `docker compose logs` shows errors.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
