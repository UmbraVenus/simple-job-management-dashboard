"""Gunicorn settings that do not fit on the command line (loaded with --config)."""
import logging

HEALTH_PATH = "/api/health/"

# Gunicorn's control socket (for its `gunicornc` admin tool) is created under
# the user's home directory. The `app` user has none, so every start logged
# "Control server error: Permission denied". Nothing here uses the socket.
control_socket_disable = True


class DropHealthyHealthChecks(logging.Filter):
    """Keep the container healthcheck, which calls every 2 seconds, out of the access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        :param record: One access-log entry; ``record.args`` holds gunicorn's
            request fields (``U`` is the path, ``s`` the response status).
        :returns: False for a health check answered with 200, so it is not
            written. A failing health check is still logged.
        """
        return not (record.args["U"] == HEALTH_PATH and str(record.args["s"]) == "200")


logging.getLogger("gunicorn.access").addFilter(DropHealthyHealthChecks())
