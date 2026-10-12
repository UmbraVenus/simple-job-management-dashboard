"""Assertions shared by the backend tests."""
from jobs.models import Job, JobStatus


def assert_in_sync(job: Job) -> None:
    """Assert the invariant for one job, reading both tables fresh from the database.

    The invariant: ``current_status`` equals the ``status_type`` of the job's
    newest ``JobStatus`` row, where newest means highest ``id``.

    :param job: The job to check; its in-memory field values are ignored.
    :raises AssertionError: If the job has no status rows, or ``current_status``
        differs from the ``status_type`` of the row with the highest ``id``.
    """
    newest = JobStatus.objects.filter(job_id=job.pk).order_by("-id").first()
    assert newest is not None, f"job {job.pk} has no status rows"

    current_status = Job.objects.values_list("current_status", flat=True).get(pk=job.pk)
    assert current_status == newest.status_type
