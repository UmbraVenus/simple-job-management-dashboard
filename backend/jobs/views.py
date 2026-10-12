"""The job endpoints. Views validate the body and call ``services.py``; they
never write a model themselves."""
from collections.abc import Iterator
from contextlib import contextmanager

from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.settings import api_settings

from jobs.exceptions import Conflict
from jobs.ids import parse_job_id
from jobs.models import Job
from jobs.pagination import JobCursorPagination
from jobs.serializers import JobCreateSerializer, JobSerializer, StatusChangeSerializer
from jobs.services import DuplicateJobName, InvalidJobInput, change_status, create_job, delete_job


class JobViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List, create, change the status of, and delete jobs.

    There is no ``retrieve`` and no ``update`` method, so GET and PUT on a
    single job answer 405.
    """

    queryset = Job.objects.all()
    serializer_class = JobSerializer
    pagination_class = JobCursorPagination

    def create(self, request: Request) -> Response:
        """Create a job; it starts as ``PENDING``.

        :param request: Body ``{"name": "<text>"}``.
        :returns: 201 with the job.
        :raises ValidationError: 400 if the name is missing or invalid.
        :raises Conflict: 409 if another job has this name.
        """
        body = JobCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with service_errors():
            job = create_job(body.validated_data["name"])
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk: str) -> Response:
        """Set a job's status. Every call appends to its log, the current status included.

        :param request: Body ``{"status_type": "<STATUS>"}``.
        :param pk: The job id from the URL.
        :returns: 200 with the job.
        :raises ValidationError: 400 if the status is missing or not a known one.
        :raises NotFound: 404 if no job has this id.
        """
        body = StatusChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with service_errors():
            job = change_status(_job_id(pk), body.validated_data["status_type"])
        return Response(JobSerializer(job).data)

    def destroy(self, request: Request, pk: str) -> Response:
        """Delete a job and its status log.

        :param request: The request; its body is not used.
        :param pk: The job id from the URL.
        :returns: 204 with no body.
        :raises NotFound: 404 if no job has this id.
        """
        with service_errors():
            delete_job(_job_id(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


@contextmanager
def service_errors() -> Iterator[None]:
    """Turn the errors a service raises into API errors.

    Only the errors the services raise on purpose are caught. Any other
    exception, a plain ``ValueError`` included, is a bug and stays a 500
    instead of being reported as the client's mistake.

    :raises ValidationError: 400, for an ``InvalidJobInput``.
    :raises NotFound: 404, for ``Job.DoesNotExist``.
    :raises Conflict: 409, for ``DuplicateJobName``.
    """
    try:
        yield
    except InvalidJobInput as exc:
        # Reached only if a serializer and its service disagree on a rule.
        raise ValidationError({api_settings.NON_FIELD_ERRORS_KEY: [str(exc)]}) from exc
    except Job.DoesNotExist as exc:
        raise NotFound() from exc
    except DuplicateJobName as exc:
        raise Conflict({"name": ["A job with this name already exists."]}, code="duplicate") from exc


def _job_id(pk: str) -> int:
    """
    :param pk: The id segment of the URL, which the router accepts as any text.
    :returns: The job id.
    :raises NotFound: If the text is not an id a job could have.
    """
    job_id = parse_job_id(pk)
    if job_id is None:
        raise NotFound()
    return job_id
