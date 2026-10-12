"""Recognising a job id in text that came from a URL."""

# Job.id is a BigAutoField: a positive 64-bit integer.
MAX_JOB_ID = 2**63 - 1


def parse_job_id(text: str) -> int | None:
    """Read a job id written as plain decimal digits.

    Stricter than ``int()``, which also accepts signs, spaces, underscores and
    non-ASCII digits, and nothing above the column's range is let through to a
    query.

    :param text: A path segment or a cursor position.
    :returns: The id, or ``None`` if the text is not one a job could have.
    """
    if not (text.isascii() and text.isdigit()) or len(text) > len(str(MAX_JOB_ID)):
        return None
    job_id = int(text)
    return job_id if job_id <= MAX_JOB_ID else None
