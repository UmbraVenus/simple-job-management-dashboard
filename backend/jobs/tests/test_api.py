"""API tests: the four job endpoints, their status codes and their error bodies.

The services are tested on their own in ``test_services.py``; these tests check
what the HTTP layer adds: validation of the body, the mapping of service errors
to 400 / 404 / 409, pagination, and that nothing is written when a request is
refused.

Every error body carries a stable ``code`` next to its English ``message``. The
tests pin the codes, because the frontend chooses its display text by code.
"""
from base64 import b64encode
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import partial
from typing import Any
from unittest import mock

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from jobs.models import Job, JobStatus, StatusType
from jobs.services import InvalidJobInput, change_status, create_job, delete_job
from jobs.tests.conftest import ThreadRunner
from jobs.tests.helpers import MISSING_JOB_ID, assert_in_sync, status_log

pytestmark = pytest.mark.django_db

JOBS_URL = "/api/jobs/"
PAGE_SIZE = 20
JOB_FIELDS = {"id", "name", "current_status", "created_at", "updated_at"}

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=dt_timezone.utc)
T1 = T0 + timedelta(hours=1)


def job_url(job_id: object) -> str:
    """
    :param job_id: A job id, or any text to put in its place.
    :returns: The URL of that single job.
    """
    return f"{JOBS_URL}{job_id}/"


def cursor(querystring: str) -> str:
    """
    :param querystring: The inside of a cursor, such as ``p=5`` (position) or ``o=1`` (offset).
    :returns: The value encoded the way the API encodes its own ``cursor`` parameter.
    """
    return b64encode(querystring.encode()).decode()


def error_codes(response: Response, key: str) -> list[str]:
    """
    :param response: An error response.
    :param key: The field name the errors are listed under.
    :returns: The ``code`` of each error listed under that key.
    """
    return [error["code"] for error in response.json()[key]]


def make_jobs(count: int) -> list[Job]:
    """
    :param count: How many jobs to create.
    :returns: The jobs, oldest first.
    """
    return [create_job(f"job {number}") for number in range(count)]


def result_ids(response: Response) -> list[int]:
    """
    :param response: A list response.
    :returns: The ids on that page, in the order the API returned them.
    """
    return [result["id"] for result in response.json()["results"]]


def post_raw(client: APIClient, url: str, body: str) -> Response:
    """POST a body exactly as written, for JSON that a Python object cannot express.

    :param client: The test client.
    :param url: The URL to post to.
    :param body: The request body, sent with a JSON content type.
    :returns: The response.
    """
    return client.post(url, data=body, content_type="application/json")


def row_counts() -> tuple[int, int]:
    """
    :returns: The number of ``Job`` rows and of ``JobStatus`` rows.
    """
    return Job.objects.count(), JobStatus.objects.count()


class TestListJobs:
    """``GET /api/jobs/``: one page of jobs, newest first, with cursor links."""

    def test_list_of_an_empty_table_is_an_empty_page(self, api_client: APIClient) -> None:
        """With no jobs the answer is 200 with no results and no links.

        :param api_client: The test client.
        """
        response = api_client.get(JOBS_URL)

        assert response.status_code == 200
        assert response.json() == {"next": None, "previous": None, "results": []}

    def test_list_returns_exactly_the_job_fields(self, api_client: APIClient, job: Job) -> None:
        """Each result has ``id``, ``name``, ``current_status``, ``created_at``, ``updated_at`` and nothing else.

        :param api_client: The test client.
        :param job: The one job in the table.
        """
        (result,) = api_client.get(JOBS_URL).json()["results"]

        assert result.keys() == JOB_FIELDS
        assert result["id"] == job.pk
        assert result["name"] == job.name
        assert result["current_status"] == StatusType.PENDING

    def test_list_is_newest_first(self, api_client: APIClient) -> None:
        """Jobs come back in reverse order of creation.

        :param api_client: The test client.
        """
        jobs = make_jobs(3)

        response = api_client.get(JOBS_URL)

        assert result_ids(response) == [job.pk for job in reversed(jobs)]

    def test_list_shows_the_status_set_by_change_status(self, api_client: APIClient, job: Job) -> None:
        """``current_status`` in the list is the job's latest status.

        :param api_client: The test client.
        :param job: The job whose status is changed before listing.
        """
        change_status(job.pk, StatusType.FAILED)

        (result,) = api_client.get(JOBS_URL).json()["results"]

        assert result["current_status"] == StatusType.FAILED

    def test_first_page_holds_twenty_jobs_and_links_to_the_next(self, api_client: APIClient) -> None:
        """With 21 jobs the first page has 20, a ``next`` link and no ``previous`` link.

        :param api_client: The test client.
        """
        make_jobs(PAGE_SIZE + 1)

        body = api_client.get(JOBS_URL).json()

        assert len(body["results"]) == PAGE_SIZE
        assert body["next"] is not None
        assert body["previous"] is None

    def test_page_size_cannot_be_changed_by_the_caller(self, api_client: APIClient) -> None:
        """``?page_size=1000`` is ignored: the page still holds 20 jobs.

        :param api_client: The test client.
        """
        make_jobs(PAGE_SIZE + 1)

        response = api_client.get(JOBS_URL, {"page_size": 1000})

        assert len(response.json()["results"]) == PAGE_SIZE

    def test_walking_next_returns_every_job_exactly_once(self, api_client: APIClient) -> None:
        """Following ``next`` from the first page to the last visits all 41 jobs once, newest first.

        :param api_client: The test client.
        """
        jobs = make_jobs(2 * PAGE_SIZE + 1)

        seen: list[int] = []
        url: str | None = JOBS_URL
        while url is not None:
            response = api_client.get(url)
            seen.extend(result_ids(response))
            url = response.json()["next"]

        assert seen == [job.pk for job in reversed(jobs)]

    def test_previous_leads_back_to_the_first_page(self, api_client: APIClient) -> None:
        """``previous`` on the second page returns the same jobs as the first page.

        :param api_client: The test client.
        """
        make_jobs(PAGE_SIZE + 1)
        first = api_client.get(JOBS_URL)
        second = api_client.get(first.json()["next"])

        back = api_client.get(second.json()["previous"])

        assert result_ids(back) == result_ids(first)

    def test_a_job_created_during_a_walk_does_not_shift_the_next_page(self, api_client: APIClient) -> None:
        """A job created after page one was read is not on page two, and page two repeats nothing.

        :param api_client: The test client.
        """
        oldest, *_ = make_jobs(PAGE_SIZE + 1)
        first = api_client.get(JOBS_URL)

        create_job("created mid-walk")
        second = api_client.get(first.json()["next"])

        assert result_ids(second) == [oldest.pk]

    def test_deleting_the_job_a_cursor_points_at_does_not_break_the_next_page(
        self, api_client: APIClient
    ) -> None:
        """The ``next`` link still works after the last job of the page it came from is deleted.

        :param api_client: The test client.
        """
        oldest, *_ = make_jobs(PAGE_SIZE + 1)
        first = api_client.get(JOBS_URL)

        delete_job(result_ids(first)[-1])
        second = api_client.get(first.json()["next"])

        assert second.status_code == 200
        assert result_ids(second) == [oldest.pk]

    @pytest.mark.parametrize(
        "value",
        [
            "not-base64!!",
            cursor("p=abc"),
            cursor("p=-1"),
            cursor(f"p={10**30}"),
            cursor("o=-1"),
            cursor("o=abc&p=5"),
            cursor("r=x&p=5"),
        ],
        ids=[
            "not-base64",
            "position-not-a-number",
            "position-negative",
            "position-beyond-bigint",
            "offset-negative",
            "offset-not-a-number",
            "reverse-not-a-number",
        ],
    )
    def test_a_garbage_cursor_gives_404(self, api_client: APIClient, job: Job, value: str) -> None:
        """A cursor the API could not have issued is refused with 404, never a 500.

        :param api_client: The test client.
        :param job: A job, so a wrongly accepted cursor would have something to return.
        :param value: The ``cursor`` query parameter.
        """
        response = api_client.get(JOBS_URL, {"cursor": value})

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "not_found"


class TestCreateJob:
    """``POST /api/jobs/``."""

    def test_create_returns_201_and_the_pending_job(self, api_client: APIClient) -> None:
        """A valid name gives 201 with the job fields; the job is ``PENDING`` with one status row.

        :param api_client: The test client.
        """
        response = api_client.post(JOBS_URL, {"name": "Fluid Dynamics Simulation"})

        assert response.status_code == 201
        body = response.json()
        assert body.keys() == JOB_FIELDS
        assert body["name"] == "Fluid Dynamics Simulation"
        assert body["current_status"] == StatusType.PENDING
        job = Job.objects.get(pk=body["id"])
        assert status_log(job) == [StatusType.PENDING]
        assert_in_sync(job)

    @pytest.mark.parametrize(
        ("raw", "stored"),
        [("  job  ", "job"), ("  " + "x" * 255 + "\n", "x" * 255)],
        ids=["trimmed", "255-after-trimming"],
    )
    def test_create_trims_the_name(self, api_client: APIClient, raw: str, stored: str) -> None:
        """Surrounding whitespace is removed before the 255 limit is applied.

        :param api_client: The test client.
        :param raw: The name as sent.
        :param stored: The name expected in the response and the database.
        """
        response = api_client.post(JOBS_URL, {"name": raw})

        assert response.status_code == 201
        assert response.json()["name"] == stored
        assert Job.objects.get().name == stored

    def test_create_turns_a_numeric_name_into_text(self, api_client: APIClient) -> None:
        """``{"name": 123}`` creates a job named ``"123"`` (pins the serializer's coercion).

        :param api_client: The test client.
        """
        response = api_client.post(JOBS_URL, {"name": 123})

        assert response.status_code == 201
        assert response.json()["name"] == "123"

    @pytest.mark.parametrize(
        ("body", "code"),
        [
            ('{"name": ""}', "blank"),
            ('{"name": "   "}', "blank"),
            ("{}", "required"),
            ('{"name": null}', "null"),
            ('{"name": "' + "x" * 256 + '"}', "max_length"),
            ('{"name": "nul\\u0000byte"}', "null_characters_not_allowed"),
            ('{"name": "lone\\ud800surrogate"}', "surrogate_characters_not_allowed"),
            ('{"name": ["job"]}', "invalid"),
            ('{"name": {"a": 1}}', "invalid"),
            ('{"name": true}', "invalid"),
        ],
        ids=[
            "empty", "whitespace", "missing", "null", "256-chars",
            "nul-character", "lone-surrogate", "list", "object", "boolean",
        ],
    )  # fmt: skip
    def test_create_with_an_invalid_name_gives_400_and_writes_nothing(
        self, api_client: APIClient, body: str, code: str
    ) -> None:
        """An invalid name gives 400 with one error under ``name`` and creates no rows.

        :param api_client: The test client.
        :param body: The raw JSON request body.
        :param code: The error code expected under ``name``.
        """
        response = post_raw(api_client, JOBS_URL, body)

        assert response.status_code == 400
        assert error_codes(response, "name") == [code]
        assert row_counts() == (0, 0)

    def test_create_ignores_fields_the_caller_may_not_set(self, api_client: APIClient) -> None:
        """``current_status``, ``id`` and ``created_at`` in the body are ignored.

        :param api_client: The test client.
        """
        body = {
            "name": "job",
            "current_status": "COMPLETED",
            "id": MISSING_JOB_ID,
            "created_at": "2000-01-01T00:00:00Z",
        }

        response = api_client.post(JOBS_URL, body)

        assert response.status_code == 201
        job = Job.objects.get()
        assert job.pk != MISSING_JOB_ID
        assert job.created_at.year != 2000
        assert job.current_status == StatusType.PENDING
        assert_in_sync(job)

    @pytest.mark.parametrize("name", ["job", "  job  "], ids=["same", "differs-by-whitespace"])
    def test_create_with_an_existing_name_gives_409_and_writes_nothing(
        self, api_client: APIClient, job: Job, name: str
    ) -> None:
        """A name that is already taken gives 409 with a ``duplicate`` error under ``name``.

        :param api_client: The test client.
        :param job: The job that already holds the name ``"job"``.
        :param name: The name sent in the second create.
        """
        response = api_client.post(JOBS_URL, {"name": name})

        assert response.status_code == 409
        assert error_codes(response, "name") == ["duplicate"]
        assert row_counts() == (1, 1)

    def test_create_can_reuse_the_name_of_a_deleted_job(self, api_client: APIClient, job: Job) -> None:
        """Once a job is deleted its name creates a new job.

        :param api_client: The test client.
        :param job: The job that holds the name, then is deleted.
        """
        api_client.delete(job_url(job.pk))

        response = api_client.post(JOBS_URL, {"name": job.name})

        assert response.status_code == 201
        assert response.json()["id"] != job.pk

    @pytest.mark.parametrize(
        ("body", "code"),
        [('["job"]', "invalid"), ('"job"', "invalid"), ("123", "invalid"), ("null", "null")],
        ids=["list", "string", "number", "null"],
    )
    def test_create_with_a_body_that_is_not_an_object_gives_400(
        self, api_client: APIClient, body: str, code: str
    ) -> None:
        """Valid JSON that is not an object gives 400 and creates no rows.

        :param api_client: The test client.
        :param body: The raw JSON request body.
        :param code: The error code expected under ``non_field_errors``.
        """
        response = post_raw(api_client, JOBS_URL, body)

        assert response.status_code == 400
        assert error_codes(response, "non_field_errors") == [code]
        assert row_counts() == (0, 0)

    def test_create_with_malformed_json_gives_400(self, api_client: APIClient) -> None:
        """A body that is not JSON gives 400 with a ``parse_error`` and creates no rows.

        :param api_client: The test client.
        """
        response = post_raw(api_client, JOBS_URL, '{"name": "job"')

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "parse_error"
        assert row_counts() == (0, 0)

    def test_create_with_json_nested_too_deeply_gives_400(self, api_client: APIClient) -> None:
        """JSON nested deeper than the parser can follow gives 400 with a ``parse_error``,
        not a 500, and creates no rows.

        :param api_client: The test client.
        """
        depth = 200_000
        response = post_raw(api_client, JOBS_URL, "[" * depth + "]" * depth)

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "parse_error"
        assert row_counts() == (0, 0)

    @pytest.mark.parametrize("content_type", ["application/x-www-form-urlencoded", "text/plain"])
    def test_create_with_a_body_that_is_not_json_gives_415(
        self, api_client: APIClient, content_type: str
    ) -> None:
        """Only JSON is accepted: a body a browser can send cross-site without a preflight
        (a form or plain text) gives 415 and creates no rows.

        :param api_client: The test client.
        :param content_type: The content type of the request.
        """
        response = api_client.post(JOBS_URL, data="name=job", content_type=content_type)

        assert response.status_code == 415
        assert response.json()["detail"]["code"] == "unsupported_media_type"
        assert row_counts() == (0, 0)

    def test_create_answers_400_when_the_service_refuses_the_name(self, api_client: APIClient) -> None:
        """An ``InvalidJobInput`` from ``create_job`` that the serializer did not catch is a 400, not a 500.

        :param api_client: The test client.
        """
        with mock.patch("jobs.views.create_job", side_effect=InvalidJobInput("Refused.")):
            response = api_client.post(JOBS_URL, {"name": "job"})

        assert response.status_code == 400
        assert response.json() == {"non_field_errors": [{"message": "Refused.", "code": "invalid"}]}

    def test_create_does_not_report_a_bug_in_the_service_as_a_client_error(self) -> None:
        """A plain ``ValueError`` from ``create_job`` is a bug, not bad input: 500, not 400."""
        client = APIClient(raise_request_exception=False)

        with mock.patch("jobs.views.create_job", side_effect=ValueError("A bug.")):
            response = client.post(JOBS_URL, {"name": "job"})

        assert response.status_code == 500

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_creates_with_one_name_give_one_201_and_409_for_the_rest(
        self, run_in_threads: ThreadRunner
    ) -> None:
        """Several requests create the same name at once: one gets 201, the others 409, and
        exactly one job with one status row exists.

        :param run_in_threads: Runs the calls in threads released together.
        """
        threads = 6

        results = run_in_threads([partial(APIClient().post, JOBS_URL, {"name": "job"})] * threads)

        statuses = sorted(getattr(result, "status_code", result) for result in results)
        assert statuses == [201, *[409] * (threads - 1)]
        assert row_counts() == (1, 1)


class TestChangeStatus:
    """``PATCH /api/jobs/<id>/``."""

    @pytest.mark.parametrize("status", ["PENDING", "RUNNING", "COMPLETED", "FAILED"])
    def test_patch_appends_a_row_and_returns_the_updated_job(
        self, api_client: APIClient, job: Job, status: str
    ) -> None:
        """Any status gives 200 with the job showing it, and appends one row, the current one included.

        :param api_client: The test client.
        :param job: The job to change; it starts as ``PENDING``.
        :param status: The status sent.
        """
        response = api_client.patch(job_url(job.pk), {"status_type": status})

        assert response.status_code == 200
        body = response.json()
        assert body.keys() == JOB_FIELDS
        assert body["id"] == job.pk
        assert body["current_status"] == status
        assert status_log(job) == [StatusType.PENDING, status]
        assert_in_sync(job)

    def test_patch_moves_updated_at_and_keeps_created_at(self, api_client: APIClient) -> None:
        """The response carries the new ``updated_at`` and the original ``created_at``.

        :param api_client: The test client.
        """
        with mock.patch("django.utils.timezone.now", return_value=T0):
            job = create_job("job")

        with mock.patch("django.utils.timezone.now", return_value=T1):
            response = api_client.patch(job_url(job.pk), {"status_type": "RUNNING"})

        body = response.json()
        assert body["created_at"] == "2026-01-01T12:00:00Z"
        assert body["updated_at"] == "2026-01-01T13:00:00Z"

    @pytest.mark.parametrize(
        ("body", "code"),
        [
            ({}, "required"),
            ({"status_type": "BOGUS"}, "invalid_choice"),
            ({"status_type": "running"}, "invalid_choice"),
            ({"status_type": ""}, "invalid_choice"),
            ({"status_type": None}, "null"),
            ({"status_type": ["RUNNING"]}, "invalid_choice"),
            ({"status_type": 1}, "invalid_choice"),
            ({"current_status": "RUNNING"}, "required"),
        ],
        ids=["missing", "unknown", "wrong-case", "empty", "null", "list", "number", "current_status-only"],
    )
    def test_patch_with_an_invalid_status_gives_400_and_writes_nothing(
        self, api_client: APIClient, job: Job, body: dict[str, Any], code: str
    ) -> None:
        """An invalid or missing ``status_type`` gives 400 with one error under ``status_type``;
        no row is appended and the job is unchanged.

        :param api_client: The test client.
        :param job: The job the request targets.
        :param body: The request body.
        :param code: The error code expected under ``status_type``.
        """
        updated_at_before = job.updated_at

        response = api_client.patch(job_url(job.pk), body)

        assert response.status_code == 400
        assert error_codes(response, "status_type") == [code]
        job.refresh_from_db()
        assert job.current_status == StatusType.PENDING
        assert job.updated_at == updated_at_before
        assert status_log(job) == [StatusType.PENDING]

    def test_patch_ignores_fields_the_caller_may_not_set(self, api_client: APIClient, job: Job) -> None:
        """``current_status`` and ``name`` in the body are ignored; only ``status_type`` is applied.

        :param api_client: The test client.
        :param job: The job to change.
        """
        body = {"status_type": "RUNNING", "current_status": "COMPLETED", "name": "renamed"}

        response = api_client.patch(job_url(job.pk), body)

        assert response.status_code == 200
        job.refresh_from_db()
        assert job.name == "job"
        assert job.current_status == StatusType.RUNNING
        assert_in_sync(job)

    def test_patch_on_an_unknown_id_gives_404_and_writes_nothing(self, api_client: APIClient, job: Job) -> None:
        """An id no job has gives 404 and appends no row anywhere.

        :param api_client: The test client.
        :param job: An unrelated job that must not change.
        """
        response = api_client.patch(job_url(MISSING_JOB_ID), {"status_type": "RUNNING"})

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "not_found"
        assert row_counts() == (1, 1)

    def test_patch_checks_the_body_before_the_id(self, api_client: APIClient) -> None:
        """An invalid status on an unknown id gives 400, not 404 (same order as the service).

        :param api_client: The test client.
        """
        response = api_client.patch(job_url(MISSING_JOB_ID), {"status_type": "BOGUS"})

        assert response.status_code == 400

    def test_patch_leaves_other_jobs_alone(self, api_client: APIClient, job: Job, other_job: Job) -> None:
        """Changing one job leaves another job's status and log untouched.

        :param api_client: The test client.
        :param job: The job to change.
        :param other_job: The job that must not change.
        """
        api_client.patch(job_url(job.pk), {"status_type": "FAILED"})

        other_job.refresh_from_db()
        assert other_job.current_status == StatusType.PENDING
        assert status_log(other_job) == [StatusType.PENDING]

    def test_patch_answers_400_when_the_service_refuses_the_status(self, api_client: APIClient, job: Job) -> None:
        """An ``InvalidJobInput`` from ``change_status`` that the serializer did not catch is a 400, not a 500.

        :param api_client: The test client.
        :param job: The job the request targets.
        """
        with mock.patch("jobs.views.change_status", side_effect=InvalidJobInput("Refused.")):
            response = api_client.patch(job_url(job.pk), {"status_type": "RUNNING"})

        assert response.status_code == 400
        assert error_codes(response, "non_field_errors") == ["invalid"]

    def test_patch_does_not_report_a_bug_in_the_service_as_a_client_error(self, job: Job) -> None:
        """A plain ``ValueError`` from ``change_status`` is a bug, not bad input: 500, not 400.

        :param job: The job the request targets.
        """
        client = APIClient(raise_request_exception=False)

        with mock.patch("jobs.views.change_status", side_effect=ValueError("A bug.")):
            response = client.patch(job_url(job.pk), {"status_type": "RUNNING"})

        assert response.status_code == 500


class TestDeleteJob:
    """``DELETE /api/jobs/<id>/``."""

    def test_delete_gives_204_and_removes_the_job_and_its_statuses_only(
        self, api_client: APIClient, job: Job, other_job: Job
    ) -> None:
        """A delete gives 204 with an empty body; the job and its log are gone, other jobs are intact.

        :param api_client: The test client.
        :param job: The job to delete.
        :param other_job: The job that must survive.
        """
        change_status(job.pk, StatusType.RUNNING)

        response = api_client.delete(job_url(job.pk))

        assert response.status_code == 204
        assert response.content == b""
        assert list(Job.objects.all()) == [other_job]
        assert list(JobStatus.objects.values_list("job_id", flat=True)) == [other_job.pk]

    def test_second_delete_gives_404(self, api_client: APIClient, job: Job) -> None:
        """Deleting a job that is already gone gives 404.

        :param api_client: The test client.
        :param job: The job to delete twice.
        """
        api_client.delete(job_url(job.pk))

        response = api_client.delete(job_url(job.pk))

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "not_found"

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_delete_and_patch_never_give_500_or_leave_an_orphan(
        self, job: Job, run_in_threads: ThreadRunner
    ) -> None:
        """A delete racing status changes: the delete gets 204, each change 200 or 404, and no
        row of the job is left.

        :param job: The job being deleted and changed at once.
        :param run_in_threads: Runs the calls in threads released together.
        """
        url = job_url(job.pk)
        changes = [partial(APIClient().patch, url, {"status_type": "RUNNING"})] * 5

        results = run_in_threads([partial(APIClient().delete, url), *changes])

        deleted, *changed = [getattr(result, "status_code", result) for result in results]
        assert deleted == 204
        assert set(changed) <= {200, 404}, changed
        assert row_counts() == (0, 0)


class TestRouting:
    """Ids that are not ids, and methods the brief does not ask for."""

    @pytest.mark.parametrize("method", ["patch", "delete"])
    @pytest.mark.parametrize("job_id", ["abc", "-1", "0", "1abc", "1_0", str(2**63), str(10**30)])
    def test_an_id_no_job_can_have_gives_404(
        self, api_client: APIClient, job: Job, method: str, job_id: str
    ) -> None:
        """A non-numeric, zero, negative or beyond-bigint id gives 404, never a 500, and writes nothing.

        :param api_client: The test client.
        :param job: An unrelated job that must not change.
        :param method: The HTTP method used.
        :param job_id: The text sent in place of the id.
        """
        response = getattr(api_client, method)(job_url(job_id), {"status_type": "RUNNING"})

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "not_found"
        assert row_counts() == (1, 1)
        assert_in_sync(job)

    @pytest.mark.parametrize("method", ["get", "put", "post", "options"])
    def test_other_methods_on_a_job_give_405(self, api_client: APIClient, job: Job, method: str) -> None:
        """Reading or replacing a single job is not offered: 405, and the job is unchanged.

        :param api_client: The test client.
        :param job: The job the request targets.
        :param method: The HTTP method used.
        """
        response = getattr(api_client, method)(job_url(job.pk), {"name": "renamed", "status_type": "RUNNING"})

        assert response.status_code == 405
        assert response.json()["detail"]["code"] == "method_not_allowed"
        assert status_log(job) == [StatusType.PENDING]
        assert Job.objects.get().name == "job"

    @pytest.mark.parametrize("method", ["put", "patch", "delete", "options"])
    def test_other_methods_on_the_collection_give_405(self, api_client: APIClient, job: Job, method: str) -> None:
        """The collection only lists and creates: anything else gives 405 and deletes nothing.

        :param api_client: The test client.
        :param job: A job that must survive.
        :param method: The HTTP method used.
        """
        response = getattr(api_client, method)(JOBS_URL, {"status_type": "RUNNING"})

        assert response.status_code == 405
        assert row_counts() == (1, 1)

    @pytest.mark.parametrize(
        ("host", "status_code"),
        [
            ("localhost:8080", 200),
            ("127.0.0.1:8080", 200),
            ("[::1]:8080", 200),
            ("frontend", 200),
            ("evil.example:8080", 400),
        ],
    )
    def test_host_header_is_checked(self, api_client: APIClient, db: None, host: str, status_code: int) -> None:
        """Only the local names and the compose service name are accepted as ``Host``.

        A page on another site whose DNS is re-pointed at this machine (DNS
        rebinding) is same-origin with the app as far as the browser can tell;
        the ``Host`` it sends is the one thing that gives it away.

        :param api_client: The test client.
        :param db: pytest-django's database access.
        :param host: The ``Host`` header sent.
        :param status_code: The expected status: 200 for an allowed host, 400 otherwise.
        """
        response = api_client.get(JOBS_URL, HTTP_HOST=host)

        assert response.status_code == status_code
