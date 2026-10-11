import logging

from django.db import Error as DatabaseError
from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Report whether this process can reach the database.

    Used by the container healthcheck, so it must stay cheap.

    :param request: The incoming GET request; its content is not used.
    :returns: 200 ``{"status": "ok"}`` when ``SELECT 1`` succeeds, otherwise
        503 ``{"status": "unavailable"}``.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.exception("Health check failed: database unreachable")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
