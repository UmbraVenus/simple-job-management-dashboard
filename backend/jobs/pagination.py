"""Cursor (keyset) pagination for the job list."""
from rest_framework.exceptions import NotFound
from rest_framework.pagination import Cursor, CursorPagination
from rest_framework.request import Request

from jobs.ids import parse_job_id


class JobCursorPagination(CursorPagination):
    """Pages of 20 jobs, newest first.

    Each page is ``WHERE id < <last id seen> ORDER BY id DESC LIMIT 21``: the
    same cost on the first page and the fifty-thousandth, and never a
    ``COUNT(*)``. The page size is fixed; the caller cannot raise it.
    """

    page_size = 20
    # Unique, as cursor pagination needs, and already indexed (primary key).
    ordering = "-id"

    def decode_cursor(self, request: Request) -> Cursor | None:
        """Refuse a cursor whose position is not a job id.

        DRF checks the offset and the direction but passes the position to the
        query as it came, where text such as ``abc`` raises ``ValueError``: a
        500 from a URL anyone can type.

        :param request: The list request.
        :returns: The decoded cursor, or ``None`` when the request has none.
        :raises NotFound: If the cursor cannot be decoded or its position is
            not a job id.
        """
        cursor = super().decode_cursor(request)
        if cursor is not None and cursor.position is not None and parse_job_id(cursor.position) is None:
            raise NotFound(self.invalid_cursor_message)
        return cursor
