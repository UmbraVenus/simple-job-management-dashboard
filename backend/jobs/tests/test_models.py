"""Model tests: what the database itself guarantees for Job and JobStatus.

They run against real Postgres with the real migration applied, so a passing
test means the constraint exists in the schema, not only in Python.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

import pytest
from django.core.management import call_command
from django.db import DataError, IntegrityError, transaction
from django.utils import timezone

from jobs.models import Job, JobStatus, StatusType

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=dt_timezone.utc)
T1 = T0 + timedelta(hours=1)


def test_status_type_has_the_four_states() -> None:
    """The enum offers exactly the four states, in display order."""
    assert StatusType.values == ["PENDING", "RUNNING", "COMPLETED", "FAILED"]


def test_create_sets_both_timestamps() -> None:
    """Creating a job stamps ``created_at`` and ``updated_at`` with the current time."""
    with mock.patch("django.utils.timezone.now", return_value=T0):
        job = Job.objects.create(name="Fluid Dynamics Simulation")

    job.refresh_from_db()
    assert job.created_at == T0
    assert job.updated_at == T0


def test_save_moves_updated_at_and_keeps_created_at() -> None:
    """Saving an existing job advances ``updated_at`` and leaves ``created_at`` alone."""
    with mock.patch("django.utils.timezone.now", return_value=T0):
        job = Job.objects.create(name="ML Model Training")

    with mock.patch("django.utils.timezone.now", return_value=T1):
        job.save()

    job.refresh_from_db()
    assert job.created_at == T0
    assert job.updated_at == T1


def test_new_job_defaults_to_pending() -> None:
    """A job created without a status starts as ``PENDING``."""
    job = Job.objects.create(name="job")

    job.refresh_from_db()
    assert job.current_status == StatusType.PENDING


@pytest.mark.parametrize("status", ["BOGUS", "pending", ""])
def test_database_rejects_invalid_job_current_status(status: str) -> None:
    """The check constraint on ``Job.current_status`` refuses anything outside the enum.

    :param status: An unknown, wrong-case or empty status value.
    """
    # atomic() gives the failing INSERT its own savepoint, so the error does
    # not poison the transaction the test itself runs in.
    with pytest.raises(IntegrityError), transaction.atomic():
        Job.objects.create(name="job", current_status=status)

    assert not Job.objects.exists()


@pytest.mark.parametrize("status", ["BOGUS", "pending", ""])
def test_database_rejects_invalid_jobstatus_status_type(status: str) -> None:
    """The check constraint on ``JobStatus.status_type`` refuses anything outside the enum.

    :param status: An unknown, wrong-case or empty status value.
    """
    job = Job.objects.create(name="job")

    with pytest.raises(IntegrityError), transaction.atomic():
        JobStatus.objects.create(job=job, status_type=status)

    assert not JobStatus.objects.exists()


@pytest.mark.parametrize("name", ["", " ", "\t\n  "])
def test_database_rejects_blank_job_name(name: str) -> None:
    """The check constraint on ``Job.name`` refuses names with no visible character.

    :param name: An empty or whitespace-only name.
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        Job.objects.create(name=name)

    assert not Job.objects.exists()


def test_job_name_accepts_255_characters_and_rejects_256() -> None:
    """The column holds a 255-character name and errors, rather than truncates, at 256."""
    Job.objects.create(name="x" * 255)

    with pytest.raises(DataError), transaction.atomic():
        Job.objects.create(name="x" * 256)

    assert Job.objects.count() == 1


def test_jobstatus_timestamp_defaults_to_now() -> None:
    """A status created without a ``timestamp`` records the time of the insert."""
    job = Job.objects.create(name="job")

    before = timezone.now()
    status = JobStatus.objects.create(job=job, status_type=StatusType.PENDING)
    after = timezone.now()

    status.refresh_from_db()
    assert before <= status.timestamp <= after


def test_deleting_a_job_deletes_only_its_own_statuses() -> None:
    """Deleting a job removes its status rows and leaves other jobs and their rows intact."""
    doomed = Job.objects.create(name="doomed")
    kept = Job.objects.create(name="kept")
    JobStatus.objects.create(job=doomed, status_type=StatusType.PENDING)
    JobStatus.objects.create(job=doomed, status_type=StatusType.RUNNING)
    kept_status = JobStatus.objects.create(job=kept, status_type=StatusType.PENDING)

    doomed.delete()

    assert list(Job.objects.all()) == [kept]
    assert list(JobStatus.objects.all()) == [kept_status]


def test_migrations_match_the_models() -> None:
    """Every model change has a migration: ``makemigrations`` finds nothing left to generate."""
    # --check exits non-zero (SystemExit) when a model change has no migration.
    call_command("makemigrations", "--check", "--dry-run")
