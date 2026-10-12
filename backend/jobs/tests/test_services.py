"""Service tests: ``create_job``, ``change_status`` and ``delete_job`` keep a job and its log in sync.

The invariant under test: ``job.current_status`` equals the ``status_type`` of
that job's newest ``JobStatus`` row, where newest means highest ``id``.
"""
from collections.abc import Callable
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import partial
from unittest import mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from pytest_django import DjangoAssertNumQueries

from jobs.models import Job, JobStatus, StatusType
from jobs.services import DuplicateJobName, change_status, create_job, delete_job
from jobs.tests.conftest import ThreadRunner
from jobs.tests.helpers import assert_in_sync

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=dt_timezone.utc)
T1 = T0 + timedelta(hours=1)

# No job is ever given this id: the tests that use it create at most a few rows.
MISSING_JOB_ID = 999_999_999


def status_log(job: Job) -> list[str]:
    """
    :param job: The job whose log to read.
    :returns: The job's ``status_type`` values, oldest first (by ``id``).
    """
    return list(job.statuses.order_by("id").values_list("status_type", flat=True))


class TestCreateJob:
    """``create_job`` with a name nobody else has."""

    def test_create_job_returns_a_saved_pending_job(self) -> None:
        """``create_job`` returns a saved ``Job`` with the given name and ``PENDING`` status."""
        job = create_job("Fluid Dynamics Simulation")

        assert job.pk is not None
        job.refresh_from_db()
        assert job.name == "Fluid Dynamics Simulation"
        assert job.current_status == StatusType.PENDING

    def test_create_job_writes_exactly_one_pending_status(self) -> None:
        """A new job has exactly one ``JobStatus`` row, it is ``PENDING``, and the job is in sync."""
        job = create_job("job")

        assert status_log(job) == [StatusType.PENDING]
        assert_in_sync(job)

    @pytest.mark.parametrize("name", ["", " ", "\t\n  ", "x" * 256, "nul\x00byte", None])
    def test_create_job_with_an_invalid_name_raises_value_error_and_writes_nothing(
        self, name: str | None, django_assert_num_queries: DjangoAssertNumQueries
    ) -> None:
        """An invalid name raises ``ValueError`` before any query runs: no ``Job``, no ``JobStatus``.

        :param name: An empty, whitespace-only, over-255, NUL-containing or missing name.
        :param django_assert_num_queries: pytest-django's query counter.
        """
        with django_assert_num_queries(0), pytest.raises(ValueError):
            create_job(name)

        assert not Job.objects.exists()
        assert not JobStatus.objects.exists()

    @pytest.mark.parametrize(
        ("raw", "stored"),
        [
            ("  job  ", "job"),
            ("x" * 255, "x" * 255),
            ("  " + "x" * 255 + "\n", "x" * 255),
        ],
        ids=["trimmed", "exactly-255", "255-after-trimming"],
    )
    def test_create_job_stores_a_valid_name(self, raw: str, stored: str) -> None:
        """Surrounding whitespace is trimmed, and the 255 limit is inclusive and applies after trimming.

        :param raw: The name as the caller passes it.
        :param stored: The name expected in the database.
        """
        job = create_job(raw)

        job.refresh_from_db()
        assert job.name == stored

    def test_model_level_create_writes_no_status(self) -> None:
        """``Job.objects.create()`` writes no ``JobStatus``; only ``create_job`` does (documents the gap)."""
        job = Job.objects.create(name="job")

        assert not job.statuses.exists()


class TestCreateJobDuplicateName:
    """Job names are unique, so a retried create cannot make a second job."""

    def test_create_job_with_an_existing_name_raises_and_writes_nothing(self, job: Job) -> None:
        """A second ``create_job`` with the same name raises ``DuplicateJobName``: still one job, one status row.

        :param job: The job that already holds the name.
        """
        with pytest.raises(DuplicateJobName):
            create_job(job.name)

        assert Job.objects.count() == 1
        assert JobStatus.objects.count() == 1

    def test_create_job_compares_names_after_trimming(self, job: Job) -> None:
        """A name that differs only by surrounding whitespace is a duplicate.

        :param job: The job that already holds the name.
        """
        with pytest.raises(DuplicateJobName):
            create_job(f"  {job.name}  ")

        assert Job.objects.count() == 1

    def test_create_job_treats_a_different_case_as_a_different_name(self) -> None:
        """``"Job"`` and ``"job"`` are two jobs: matching is exact (pins the deferred TODO)."""
        create_job("Job")
        create_job("job")

        assert Job.objects.count() == 2

    def test_create_job_can_reuse_the_name_of_a_deleted_job(self, job: Job) -> None:
        """A name is released when its job is deleted: the same name then creates a fresh job.

        :param job: The job that holds the name, then is deleted.
        """
        delete_job(job.pk)

        new_job = create_job(job.name)

        assert new_job.pk != job.pk
        assert_in_sync(new_job)


class TestChangeStatus:
    """``change_status`` on an existing job with a valid status."""

    @pytest.mark.parametrize("status", ["PENDING", "RUNNING", "COMPLETED", "FAILED"])
    def test_change_status_appends_a_row_and_updates_the_job(self, job: Job, status: str) -> None:
        """Any state is reachable: one row is appended, ``current_status`` matches it, job is in sync.

        :param job: The job to change.
        :param status: The target state.
        """
        change_status(job.pk, status)

        assert status_log(job) == [StatusType.PENDING, status]
        job.refresh_from_db()
        assert job.current_status == status
        assert_in_sync(job)

    def test_change_status_sequence_keeps_the_full_log_in_order(self, job: Job) -> None:
        """After N changes the log has 1 + N rows in call order, and the job is in sync after each step.

        :param job: The job to change.
        """
        sequence = [StatusType.RUNNING, StatusType.FAILED, StatusType.RUNNING, StatusType.COMPLETED]

        for step, status in enumerate(sequence, start=1):
            change_status(job.pk, status)

            assert status_log(job) == [StatusType.PENDING, *sequence[:step]]
            assert_in_sync(job)

    def test_change_status_to_the_current_status_still_appends(self, job: Job) -> None:
        """Setting the status a job already has appends another row (not idempotent, by design).

        :param job: A job that is already ``PENDING``.
        """
        change_status(job.pk, StatusType.PENDING)

        assert status_log(job) == [StatusType.PENDING, StatusType.PENDING]
        assert_in_sync(job)

    def test_change_status_returns_the_updated_job(self, job: Job) -> None:
        """The returned ``Job`` carries the new ``current_status`` and the new ``updated_at``.

        :param job: The job to change.
        """
        with mock.patch("django.utils.timezone.now", return_value=T1):
            returned = change_status(job.pk, StatusType.RUNNING)

        assert returned.pk == job.pk
        assert returned.current_status == StatusType.RUNNING
        assert returned.updated_at == T1

    def test_change_status_moves_updated_at_and_keeps_created_at(self) -> None:
        """``updated_at`` advances and ``created_at`` does not (``auto_now`` is skipped by
        ``save(update_fields=...)`` unless the field is listed)."""
        with mock.patch("django.utils.timezone.now", return_value=T0):
            job = create_job("job")

        with mock.patch("django.utils.timezone.now", return_value=T1):
            change_status(job.pk, StatusType.RUNNING)

        job.refresh_from_db()
        assert job.created_at == T0
        assert job.updated_at == T1

    def test_change_status_never_takes_a_timestamp_from_the_caller(self, job: Job) -> None:
        """The new row's ``timestamp`` is the time of the call, so id order and timestamp order agree.

        :param job: The job to change.
        """
        before = timezone.now()
        change_status(job.pk, StatusType.RUNNING)
        change_status(job.pk, StatusType.COMPLETED)
        after = timezone.now()

        initial, first, second = job.statuses.order_by("id").values_list("timestamp", flat=True)
        assert initial <= before <= first <= second <= after

    def test_change_status_leaves_other_jobs_alone(self, job: Job, other_job: Job) -> None:
        """Changing one job leaves another job's ``current_status``, ``updated_at`` and log untouched.

        :param job: The job to change.
        :param other_job: The job that must not change.
        """
        updated_at_before = other_job.updated_at

        change_status(job.pk, StatusType.FAILED)

        other_job.refresh_from_db()
        assert other_job.current_status == StatusType.PENDING
        assert other_job.updated_at == updated_at_before
        assert status_log(other_job) == [StatusType.PENDING]


class TestChangeStatusRefusals:
    """``change_status`` with input it must refuse."""

    @pytest.mark.parametrize("status", ["BOGUS", "running", "", None])
    def test_change_status_with_an_invalid_status_writes_nothing(
        self, job: Job, status: str | None, django_assert_num_queries: DjangoAssertNumQueries
    ) -> None:
        """An invalid status raises ``ValueError`` before any query runs: no row appended, and
        ``current_status`` and ``updated_at`` stay as they were.

        :param job: The job the call targets.
        :param status: An unknown, wrong-case, empty or missing status value.
        :param django_assert_num_queries: pytest-django's query counter.
        """
        updated_at_before = job.updated_at

        with django_assert_num_queries(0), pytest.raises(ValueError):
            change_status(job.pk, status)

        job.refresh_from_db()
        assert job.current_status == StatusType.PENDING
        assert job.updated_at == updated_at_before
        assert status_log(job) == [StatusType.PENDING]

    def test_change_status_on_a_missing_job_raises_and_writes_nothing(self) -> None:
        """An id that never existed raises ``Job.DoesNotExist`` and creates no ``JobStatus`` row."""
        with pytest.raises(Job.DoesNotExist):
            change_status(MISSING_JOB_ID, StatusType.RUNNING)

        assert not JobStatus.objects.exists()

    def test_change_status_checks_the_status_before_looking_up_the_job(self) -> None:
        """An invalid status on a missing job raises ``ValueError``, not ``Job.DoesNotExist``
        (pins the order of the checks, so the API answers 400 rather than 404)."""
        with pytest.raises(ValueError):
            change_status(MISSING_JOB_ID, "BOGUS")

    def test_change_status_on_a_deleted_job_raises_and_writes_nothing(self, job: Job) -> None:
        """An id whose job was just deleted raises ``Job.DoesNotExist`` and creates no orphan row.

        :param job: The job that is deleted before the call.
        """
        delete_job(job.pk)

        with pytest.raises(Job.DoesNotExist):
            change_status(job.pk, StatusType.RUNNING)

        assert not JobStatus.objects.exists()


class TestAtomicity:
    """A service call that fails half way leaves nothing behind."""

    def test_create_job_rolls_back_the_job_when_the_status_insert_fails(self) -> None:
        """If the ``JobStatus`` insert raises, the ``Job`` insert is rolled back: no job without a log."""
        with (
            mock.patch.object(JobStatus.objects, "create", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            create_job("job")

        assert not Job.objects.exists()

    def test_change_status_rolls_back_the_status_row_when_the_job_save_fails(self, job: Job) -> None:
        """If saving the ``Job`` raises after the ``JobStatus`` insert, the new row is gone and
        ``current_status`` is unchanged.

        :param job: The job to change.
        """
        with (
            mock.patch.object(Job, "save", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            change_status(job.pk, StatusType.RUNNING)

        assert status_log(job) == [StatusType.PENDING]
        assert_in_sync(job)


class TestConcurrency:
    """Writers racing on one job, or on one name."""

    @pytest.mark.parametrize(
        "write",
        [partial(change_status, status=StatusType.RUNNING), delete_job],
        ids=["change_status", "delete_job"],
    )
    def test_writes_to_an_existing_job_lock_its_row(
        self, job: Job, write: Callable[[int], object]
    ) -> None:
        """The job is read with ``SELECT ... FOR UPDATE`` (deterministic proof the lock is taken).

        :param job: The job to write to.
        :param write: The service call under test, taking the job id.
        """
        with CaptureQueriesContext(connection) as queries:
            write(job.pk)

        assert any("FOR UPDATE" in query["sql"] for query in queries)

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_change_status_calls_all_land_and_stay_in_sync(
        self, job: Job, run_in_threads: ThreadRunner
    ) -> None:
        """Several threads change one job to different states: the log has 1 + threads rows and
        ``current_status`` equals the row with the highest ``id``.

        :param job: The job every thread changes.
        :param run_in_threads: Runs the calls in threads released together.
        """
        statuses = [StatusType.RUNNING, StatusType.COMPLETED, StatusType.FAILED] * 2

        results = run_in_threads([partial(change_status, job.pk, status) for status in statuses])

        assert all(isinstance(result, Job) for result in results), results
        assert job.statuses.count() == 1 + len(statuses)
        assert_in_sync(job)

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_create_job_calls_with_one_name_make_one_job(
        self, run_in_threads: ThreadRunner
    ) -> None:
        """Several threads create the same name: exactly one ``Job`` and one ``JobStatus`` exist,
        and every other call raised ``DuplicateJobName``.

        :param run_in_threads: Runs the calls in threads released together.
        """
        threads = 6

        results = run_in_threads([partial(create_job, "job")] * threads)

        created = [result for result in results if isinstance(result, Job)]
        refused = [result for result in results if isinstance(result, DuplicateJobName)]
        assert len(created) == 1, results
        assert len(refused) == threads - 1, results
        assert Job.objects.count() == 1
        assert JobStatus.objects.count() == 1

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_delete_and_change_status_never_fail_with_a_foreign_key_error(
        self, job: Job, run_in_threads: ThreadRunner
    ) -> None:
        """A delete racing a status change ends with the job fully gone or a clean not-found,
        never an ``IntegrityError`` and never an orphan ``JobStatus``.

        :param job: The job being deleted and changed at once.
        :param run_in_threads: Runs the calls in threads released together.
        """
        changes = [partial(change_status, job.pk, StatusType.RUNNING)] * 5

        deleted, *changed = run_in_threads([partial(delete_job, job.pk), *changes])

        assert deleted is None
        assert all(isinstance(result, (Job, Job.DoesNotExist)) for result in changed), changed
        assert not Job.objects.exists()
        assert not JobStatus.objects.exists()


class TestDeleteJob:
    """``delete_job`` removes a job together with its log."""

    def test_delete_job_removes_the_job_and_its_statuses_only(self, job: Job, other_job: Job) -> None:
        """``delete_job`` removes the job and its log and leaves other jobs and their rows intact.

        :param job: The job to delete.
        :param other_job: The job that must survive.
        """
        change_status(job.pk, StatusType.RUNNING)

        delete_job(job.pk)

        assert list(Job.objects.all()) == [other_job]
        assert list(JobStatus.objects.values_list("job_id", flat=True)) == [other_job.pk]

    def test_delete_job_on_a_missing_job_raises_and_deletes_nothing(self, other_job: Job) -> None:
        """An unknown id raises ``Job.DoesNotExist`` and no row of any job is removed.

        :param other_job: An unrelated job that must survive.
        """
        with pytest.raises(Job.DoesNotExist):
            delete_job(MISSING_JOB_ID)

        assert list(Job.objects.all()) == [other_job]
        assert JobStatus.objects.count() == 1

    def test_delete_job_twice_raises_on_the_second_call(self, job: Job) -> None:
        """Deleting an already-deleted job raises ``Job.DoesNotExist`` (the API's second DELETE is a 404).

        :param job: The job to delete twice.
        """
        delete_job(job.pk)

        with pytest.raises(Job.DoesNotExist):
            delete_job(job.pk)
