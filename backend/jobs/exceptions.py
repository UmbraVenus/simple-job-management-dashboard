"""Error responses: every error carries a stable ``code`` next to its message.

The frontend picks its display text by ``code``; the English ``message`` is for
logs and for people calling the API by hand, and can change without breaking a
client. Shapes::

    {"name": [{"message": "...", "code": "blank"}]}            # a field
    {"detail": {"message": "Not found.", "code": "not_found"}}  # the request
"""
from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# TODO: an exception that is not an APIException (a bug, the database going
#  away) still gets Django's HTML 500, and a URL that matches no route gets its
#  HTML 404. Deferred: the frontend has to cope with non-JSON bodies anyway
#  (nginx answers 502 when the backend is down). Fix: return a JSON 500 / 503
#  here, and set handler404 in config/urls.py.


class Conflict(APIException):
    """The request is valid but collides with what is already stored."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with existing data."
    default_code = "conflict"


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Render an API error with codes; DRF's own handler renders messages only.

    :param exc: The exception a view raised.
    :param context: The view, request and URL arguments, as DRF passes them.
    :returns: The error response, or ``None`` for an exception that is not an
        API error, which Django then turns into a 500.
    """
    if isinstance(exc, Http404):
        exc = NotFound()
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, APIException):
        details = exc.get_full_details()
        response.data = details if isinstance(exc.detail, (list, dict)) else {"detail": details}
    return response
