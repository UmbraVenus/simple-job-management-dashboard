"""The only application code that writes jobs.

(The ``seed_jobs`` management command, a development tool, bulk-inserts with
SQL and keeps the same invariant.)

Every write keeps one invariant: ``Job.current_status`` equals the
``status_type`` of that job's newest ``JobStatus`` row. Each function validates
its own input, so it is safe to call without a serializer in front of it, and
runs in one transaction, so a failure half way leaves nothing behind.
"""
from django.db import IntegrityError, transaction

from jobs.models import JOB_NAME_UNIQUE_CONSTRAINT, Job, JobStatus, StatusType

# TODO: nothing here is logged; the gunicorn access log only shows the request.
#  Deferred: the access log is enough for the brief. Fix: logger.info on a
#  refused duplicate name and on each status change.

_NAME_MAX_LENGTH: int = Job._meta.get_field("name").max_length


class InvalidJobInput(ValueError):
    """A name or status the caller passed is not acceptable.

    A ``ValueError``, so callers may catch either; the API catches only this
    class, so a ``ValueError`` raised by a bug is not reported as bad input.
    """


class DuplicateJobName(Exception):
    """A job with this name already exists."""


def create_job(name: str) -> Job:
    """Create a job together with its initial ``PENDING`` status row.

    :param name: The job's name; surrounding whitespace is removed.
    :returns: The saved job.
    :raises InvalidJobInput: If the name is not a string, is blank, contains a NUL
        character or a lone surrogate, or is longer than the column allows.
    :raises DuplicateJobName: If another job already has this name.
    """
    name = _clean_name(name)
    try:
        # No "does this name exist?" query first: two concurrent calls would
        # both see "no". The unique constraint decides, and this atomic block
        # is the savepoint that undoes the failed insert.
        with transaction.atomic():
            job = Job.objects.create(name=name)
            JobStatus.objects.create(job=job, status_type=job.current_status)
    except IntegrityError as exc:
        if _violated_constraint(exc) == JOB_NAME_UNIQUE_CONSTRAINT:
            raise DuplicateJobName(name) from exc
        raise
    return job


def change_status(job_id: int, status: str) -> Job:
    """Append a status row to a job's log and copy the status onto the job.

    Any state may follow any state, including the current one; every call
    appends a row.

    :param job_id: The id of the job to change.
    :param status: One of the ``StatusType`` values.
    :returns: The job, carrying the new ``current_status`` and ``updated_at``.
    :raises InvalidJobInput: If the status is not one of the ``StatusType`` values.
    :raises Job.DoesNotExist: If no job has this id.
    """
    new_status = _clean_status(status)
    with transaction.atomic():
        job = _lock_job(job_id)
        JobStatus.objects.create(job=job, status_type=new_status)
        job.current_status = new_status
        # updated_at must be listed: with update_fields, an auto_now field
        # that is not named is left out of the UPDATE.
        job.save(update_fields=["current_status", "updated_at"])
    return job


def delete_job(job_id: int) -> None:
    """Delete a job and its whole status log.

    :param job_id: The id of the job to delete.
    :raises Job.DoesNotExist: If no job has this id.
    """
    with transaction.atomic():
        # Django's cascade is two statements: delete the statuses, then the
        # job. Without the lock, a status change committing between them makes
        # the second one fail on the foreign key.
        _lock_job(job_id).delete()


def _lock_job(job_id: int) -> Job:
    """Read a job and hold its row lock until the surrounding transaction ends.

    Writers to the same job queue up here, so they run one after another.
    The wait has no time limit (see the TODO at ``DATABASES`` in settings.py).

    :param job_id: The id of the job to lock.
    :returns: The job as it is once the lock is held.
    :raises Job.DoesNotExist: If no job has this id.
    """
    return Job.objects.select_for_update().get(pk=job_id)


def _clean_name(name: str) -> str:
    """
    :param name: The name as the caller passed it.
    :returns: The name without surrounding whitespace.
    :raises InvalidJobInput: If the name is not a string, is blank, contains a NUL
        character or a lone surrogate, or is longer than the column allows.
    """
    if not isinstance(name, str):
        raise InvalidJobInput("Job name must be a string.")
    if "\x00" in name:
        raise InvalidJobInput("Job name must not contain a NUL character.")
    try:
        name.encode()
    except UnicodeEncodeError:
        # Half of a surrogate pair: Python holds it, the database cannot.
        raise InvalidJobInput("Job name must be valid Unicode text.") from None
    # TODO: characters that draw nothing (zero-width space, direction marks)
    #  count as text, and names are not Unicode-normalised, so a name can look
    #  blank and two names can look the same. Deferred: the brief asks only for
    #  a non-empty string. Fix: unicodedata.normalize("NFC", name) and refuse
    #  the "Cf" and "Cc" categories, here and in JobCreateSerializer.
    name = name.strip()
    if not name:
        raise InvalidJobInput("Job name must not be blank.")
    if len(name) > _NAME_MAX_LENGTH:
        raise InvalidJobInput(f"Job name must be at most {_NAME_MAX_LENGTH} characters.")
    return name


def _clean_status(status: str) -> StatusType:
    """
    :param status: The status as the caller passed it.
    :returns: The matching ``StatusType`` member.
    :raises InvalidJobInput: If the status is not one of the ``StatusType`` values.
    """
    try:
        return StatusType(status)
    except ValueError:
        raise InvalidJobInput(f"Status must be one of: {', '.join(StatusType.values)}.") from None


def _violated_constraint(exc: IntegrityError) -> str | None:
    """
    :param exc: The error Django raised for a failed write.
    :returns: The name of the database constraint that was violated, as reported
        by the driver, or ``None`` if the driver did not report one.
    """
    diagnostics = getattr(exc.__cause__, "diag", None)
    return getattr(diagnostics, "constraint_name", None)
