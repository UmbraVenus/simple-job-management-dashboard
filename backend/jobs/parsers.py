"""Reading a request body."""
from collections.abc import Mapping
from typing import IO, Any

from rest_framework import parsers
from rest_framework.exceptions import ParseError


class JSONParser(parsers.JSONParser):
    """DRF's JSON parser, plus a 400 for JSON nested too deeply to read.

    Python's decoder follows nesting by recursion and raises ``RecursionError``
    on a body such as 200,000 ``[`` in a row. DRF turns only ``ValueError``
    into a 400, so that body was a 500 with a traceback in the log.
    """

    def parse(
        self,
        stream: IO[bytes],
        media_type: str | None = None,
        parser_context: Mapping[str, Any] | None = None,
    ) -> Any:
        """
        :param stream: The request body.
        :param media_type: The content type of the request.
        :param parser_context: The view, request and URL arguments, as DRF passes them.
        :returns: The decoded body.
        :raises ParseError: 400 if the body is not JSON, or is nested too deeply.
        """
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError as exc:
            raise ParseError("JSON parse error - nested too deeply.") from exc
