"""Scale guards: the ``seed_jobs`` command and the cost of the job list.

The list must cost the same at any table size: a fixed number of queries per
page, each answered from the primary-key index without scanning or sorting the
table. The seed command is the tool that makes a table large enough to check.
"""
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from jobs.management.commands.seed_jobs import MAX_COUNT, NAME_PREFIX
from jobs.models import Job, JobStatus, StatusType
from jobs.services import change_status, create_job, delete_job
from jobs.tests.helpers import assert_in_sync

pytestmark = pytest.mark.django_db

JOBS_URL = "/api/jobs/"
PAGE_SIZE = 20
# Enough rows that scanning and sorting the table costs more than using the
# index. On a near-empty table the planner rightly picks a sequential scan.
PLAN_TABLE_ROWS = 20_000
PRIMARY_KEY_INDEX = "jobs_job_pkey"


def seed(count: object) -> None:
    """
    :param count: The number of jobs to ask ``seed_jobs`` for, as the command line would pass it.
    """
    call_command("seed_jobs", str(count), verbosity=0)


def list_queries(api_client: APIClient, url: str = JOBS_URL) -> tuple[list[str], dict[str, Any]]:
    """
    :param api_client: The test client.
    :param url: The list URL to request.
    :returns: The SQL statements the request ran, and the decoded page.
    """
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(url)
    assert response.status_code == 200
    return [query["sql"] for query in queries.captured_queries], response.json()


def plan_nodes(sql: str) -> list[dict[str, Any]]:
    """
    :param sql: A SELECT statement with its parameters already filled in.
    :returns: Every node of the plan Postgres chooses for it, outermost first.
    """
    with connection.cursor() as cursor:
        cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}")
        (plan,) = cursor.fetchone()[0]

    nodes: list[dict[str, Any]] = []
    pending = [plan["Plan"]]
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(node.get("Plans", []))
    return nodes


class TestSeedJobs:
    """``python manage.py seed_jobs <count>``: bulk-create jobs with one SQL statement."""

    def test_seed_creates_jobs_that_are_in_sync(self) -> None:
        """Each seeded job is ``PENDING``, has exactly one ``PENDING`` status row and every timestamp set."""
        seed(25)

        jobs = list(Job.objects.all())
        assert len(jobs) == 25
        assert JobStatus.objects.count() == 25
        for job in jobs:
            assert job.current_status == StatusType.PENDING
            assert job.created_at is not None and job.updated_at is not None
            assert job.statuses.get().timestamp is not None
            assert_in_sync(job)

    def test_seeded_job_is_named_after_its_own_id(self) -> None:
        """A seeded job's name is the prefix followed by its id, which is what keeps names unique."""
        seed(3)

        for job in Job.objects.all():
            assert job.name == f"{NAME_PREFIX}{job.pk}"

    def test_seed_twice_adds_to_what_is_there(self, job: Job) -> None:
        """A second run does not collide with the first, and leaves existing jobs alone.

        :param job: A job that exists before seeding.
        """
        seed(5)
        seed(5)

        assert Job.objects.count() == 11
        assert JobStatus.objects.count() == 11
        assert Job.objects.filter(pk=job.pk, name=job.name).exists()

    def test_services_work_on_and_after_seeded_jobs(self) -> None:
        """A seeded job can be changed and deleted, and the next ``create_job`` gets a fresh id."""
        seed(2)
        first, second = Job.objects.order_by("id")

        change_status(first.pk, StatusType.RUNNING)
        delete_job(second.pk)
        created = create_job("made after seeding")

        assert_in_sync(first)
        assert created.pk > second.pk
        assert JobStatus.objects.filter(job_id=second.pk).count() == 0

    def test_seed_skips_a_name_that_is_taken(self) -> None:
        """If a job already has a name the seed would use, that one row is skipped, with no orphan status row."""
        seed(1)
        last_id = Job.objects.get().pk
        # create_job takes last_id + 1, so the next run would use +2, +3, +4.
        create_job(f"{NAME_PREFIX}{last_id + 3}")

        seed(3)

        assert Job.objects.count() == 4
        assert JobStatus.objects.count() == 4
        for job in Job.objects.all():
            assert_in_sync(job)

    @pytest.mark.parametrize("count", [0, -1, MAX_COUNT + 1, "abc", "1.5", ""])
    def test_seed_refuses_a_bad_count(self, count: object) -> None:
        """A count that is not a whole number between 1 and the limit is an error and writes nothing.

        :param count: The rejected count.
        """
        with pytest.raises(CommandError):
            seed(count)

        assert Job.objects.count() == 0
        assert JobStatus.objects.count() == 0


class TestListCost:
    """``GET /api/jobs/`` costs the same whatever the size of the table."""

    def test_list_runs_one_query_for_one_job_and_for_a_full_page(self, api_client: APIClient) -> None:
        """The number of queries does not grow with the number of rows on the page (no N+1).

        :param api_client: The test client.
        """
        seed(1)
        one_job, page = list_queries(api_client)
        assert len(page["results"]) == 1

        seed(PAGE_SIZE)
        full_page, page = list_queries(api_client)
        assert len(page["results"]) == PAGE_SIZE

        assert len(one_job) == len(full_page) == 1

    def test_list_reads_each_page_from_the_primary_key_index(self, api_client: APIClient) -> None:
        """The first page and the page after it are index scans: no ``Seq Scan``, no ``Sort``.

        :param api_client: The test client.
        """
        seed(PLAN_TABLE_ROWS)
        with connection.cursor() as cursor:
            # Refresh the planner's row estimates, as autovacuum would in time.
            cursor.execute("ANALYZE jobs_job")

        (first_page_sql,), first_page = list_queries(api_client)
        (next_page_sql,), _ = list_queries(api_client, first_page["next"])

        for sql in (first_page_sql, next_page_sql):
            nodes = plan_nodes(sql)
            node_types = {node["Node Type"] for node in nodes}
            index_names = {node["Index Name"] for node in nodes if "Index Name" in node}
            assert index_names == {PRIMARY_KEY_INDEX}, sql
            assert not node_types & {"Seq Scan", "Sort", "Incremental Sort", "Bitmap Heap Scan"}, sql
