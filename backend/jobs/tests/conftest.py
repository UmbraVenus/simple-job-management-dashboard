"""Fixtures shared by the backend tests."""
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection

from jobs.models import Job
from jobs.services import create_job

# A callable with its arguments already bound, and what one run of it produced:
# its return value, or the exception it raised.
Call = Callable[[], Any]
ThreadRunner = Callable[[list[Call]], list[Any]]

BARRIER_TIMEOUT_SECONDS = 10


@pytest.fixture
def job(db: None) -> Job:
    """
    :param db: pytest-django's database access.
    :returns: A job made by ``create_job``, so it has its initial ``PENDING`` row.
    """
    return create_job("job")


@pytest.fixture
def other_job(db: None) -> Job:
    """
    :param db: pytest-django's database access.
    :returns: A second job, for checking that a write to one job leaves another alone.
    """
    return create_job("other job")


@pytest.fixture
def run_in_threads() -> ThreadRunner:
    """
    :returns: A function that runs every given call in its own thread, all released at the
        same moment, and returns each call's result (or the exception it raised) in order.
    """

    def run(calls: list[Call]) -> list[Any]:
        barrier = threading.Barrier(len(calls))

        def worker(call: Call) -> Any:
            try:
                barrier.wait(timeout=BARRIER_TIMEOUT_SECONDS)
                return call()
            except Exception as exc:  # returned, so the test can assert on it
                return exc
            finally:
                # Each thread gets its own database connection; Django does not
                # close it when the thread ends.
                connection.close()

        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            return list(pool.map(worker, calls))

    return run
