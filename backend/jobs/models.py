"""Job and its append-only status log.

Rules that must hold for every writer (API, management commands, raw SQL) are
database check constraints, because Django's ``choices`` and ``blank=False``
are only checked by forms and serializers, never by ``save()``.
"""
from django.db import models
from django.utils import timezone


class StatusType(models.TextChoices):
    """The states a job can be in. Shared by ``Job`` and ``JobStatus``."""

    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class Job(models.Model):
    """A computational job."""

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Copy of the newest JobStatus.status_type, so the job list is one indexed
    # query with no join against the status log.
    # TODO: the database does not force this to match the log; a Job can even
    #  exist with no JobStatus rows. Deferred: the only writers are the
    #  functions in services.py, which change both in one transaction.
    #  Fix: a trigger on jobs_jobstatus, or derive the value on read.
    current_status = models.CharField(
        max_length=16, choices=StatusType.choices, default=StatusType.PENDING
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(current_status__in=StatusType.values),
                name="job_current_status_valid",
            ),
            # At least one non-whitespace character.
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"),
                name="job_name_not_blank",
            ),
        ]
        # TODO: no (current_status, -id) index. Deferred: nothing filters by
        #  status yet and every index slows writes. Fix: add it together with
        #  the ?status= filter.

    def __str__(self) -> str:
        """
        :returns: The job id and name, for logs and the Django shell.
        """
        return f"Job {self.pk}: {self.name}"


class JobStatus(models.Model):
    """One entry in a job's status log. Rows are only ever inserted."""

    # CASCADE is carried out by Django (DELETE on this table, then on jobs_job,
    # in one transaction); the foreign key itself has no ON DELETE clause.
    # TODO: a raw SQL delete of a job that has statuses fails with a foreign
    #  key error instead of cascading. Deferred: the ORM is the only writer and
    #  Django 5.2 cannot declare it. Fix: ON DELETE CASCADE on the constraint.
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="statuses")
    status_type = models.CharField(max_length=16, choices=StatusType.choices)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status_type__in=StatusType.values),
                name="jobstatus_status_type_valid",
            ),
        ]
        # TODO: no (job, -timestamp) index. Deferred: no status history view is
        #  specified, and the index Django creates on job_id already serves the
        #  cascade delete. Fix: add it together with the history endpoint.

    def __str__(self) -> str:
        """
        :returns: The status and the id of the job it belongs to.
        """
        return f"{self.status_type} for job {self.job_id}"
