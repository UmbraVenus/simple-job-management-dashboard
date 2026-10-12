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
# Strict by default; docker-compose.yml relaxes it to "*" so the app can be
# opened by IP on a remote machine. With no login, this check is what stops a
# web page that re-points its DNS at this machine (DNS rebinding) from using
# the API as if it were the app's own page; compose accepts that risk.
# TODO: no authentication or authorization. Anyone who can reach the app can
# create, change and delete jobs. Deferred: not in the brief. Fix: DRF
# authentication + permission classes (which need django.contrib.auth and
# django.contrib.contenttypes back in INSTALLED_APPS, and UNAUTHENTICATED_USER
# removed below), and an owner FK on Job.
ALLOWED_HOSTS = [
    *env_list("DJANGO_ALLOWED_HOSTS", "localhost,[::1],frontend"),
    # Always allowed: the container healthcheck calls http://127.0.0.1:8000, so
    # restricting the list through the environment must not make it unhealthy.
    "127.0.0.1",
]

# No django.contrib.auth: there are no users, so its tables would sit empty.
INSTALLED_APPS = [
    "rest_framework",
    "jobs",
]

REST_FRAMEWORK = {
    # JSON out only: no browsable HTML API.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # JSON in only. A form or text/plain POST is one a browser sends to another
    # origin without asking first (no CORS preflight), so with no login any web
    # page could create jobs here. Such a body now gets a 415.
    # jobs.parsers adds a 400 for JSON nested too deeply to decode.
    "DEFAULT_PARSER_CLASSES": ["jobs.parsers.JSONParser"],
    # No authentication (see the TODO at ALLOWED_HOSTS); stated, not implied.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    # request.user is None; the default (AnonymousUser) needs django.contrib.auth.
    "UNAUTHENTICATED_USER": None,
    # OPTIONS answers 405. DRF's default describes the endpoint from the output
    # serializer, which lists fields a POST cannot set and leaves out `name`.
    "DEFAULT_METADATA_CLASS": None,
    # TODO: no request-size or rate limit of its own. DRF reads the body
    #  straight from the socket, so DATA_UPLOAD_MAX_MEMORY_SIZE does not apply;
    #  the only cap is nginx's default client_max_body_size (1 MB). Deferred:
    #  nothing to key a rate on without users. Fix: client_max_body_size on
    #  /api/ in nginx.conf, and DEFAULT_THROTTLE_CLASSES once auth exists.
    "EXCEPTION_HANDLER": "jobs.exceptions.exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# TODO: no lock_timeout or statement_timeout. A request waiting for a job's row
#  lock (services._lock_job) waits until gunicorn kills its worker after 30 s;
#  three of them occupy every worker. Deferred: every transaction here is
#  short and nothing else writes to the database. Fix: "OPTIONS": {"options":
#  "-c lock_timeout=5s -c statement_timeout=15s"}, and answer 503 on a timeout.
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
