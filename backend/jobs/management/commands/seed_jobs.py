"""``python manage.py seed_jobs <count>``: fill the database with jobs.

A development tool for checking the app against a large table. It is the one
writer besides ``services.py``, and it keeps the same invariant: every job it
makes is ``PENDING`` and has exactly one ``PENDING`` row in its status log.
"""
import time
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from jobs.models import StatusType

# TODO: nothing stops this command being run against a database that matters;
#  it ships in the runtime image and asks no confirmation. Deferred: the only
#  database here is the demo one, and rows are only ever added. Fix: refuse
#  unless settings.DEBUG or an explicit --force flag.
NAME_PREFIX = "Seeded job "
# One run is one statement and one transaction; the limit keeps a typo from
# filling the disk. Run the command again for more.
MAX_COUNT = 10_000_000

# One statement, so it is atomic: jobs and their status rows appear together
# or not at all. The rows are generated inside Postgres (generate_series), so
# a million jobs is one round trip, not a million INSERTs from Python.
#
# Every column is supplied: Django applies default, auto_now_add and auto_now
# in Python, so the columns have no default in the database.
#
# The id is taken from the table's own sequence first, so the name can be
# built from it. That keeps names unique within a run and across runs, and the
# sequence stays ahead of every id used, so create_job keeps working.
# MATERIALIZED makes Postgres draw each id once, before it is used twice.
#
# A name that is already taken (someone created "Seeded job 7" by hand) is
# skipped. Only the jobs RETURNING reports get a status row.
_SEED_SQL = """
    WITH numbered AS MATERIALIZED (
        SELECT nextval(pg_get_serial_sequence('jobs_job', 'id')) AS id
        FROM generate_series(1, %(count)s)
    ),
    new_jobs AS (
        INSERT INTO jobs_job (id, name, current_status, created_at, updated_at)
        SELECT id, %(prefix)s || id, %(status)s, now(), now()
        FROM numbered
        ON CONFLICT (name) DO NOTHING
        RETURNING id
    )
    INSERT INTO jobs_jobstatus (job_id, status_type, timestamp)
    SELECT id, %(status)s, now()
    FROM new_jobs
"""


class Command(BaseCommand):
    """Create many jobs at once, each with its initial ``PENDING`` status row."""

    help = "Create COUNT jobs, each PENDING with one status row, in a single SQL statement."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        :param parser: The command's argument parser.
        """
        parser.add_argument("count", type=int, help=f"Number of jobs to create (1 to {MAX_COUNT}).")

    def handle(self, *args: Any, **options: Any) -> None:
        """
        :param args: Unused.
        :param options: The parsed arguments; ``count`` is the number of jobs to create.
        :raises CommandError: If ``count`` is below 1 or above ``MAX_COUNT``.
        """
        count: int = options["count"]
        if not 1 <= count <= MAX_COUNT:
            raise CommandError(f"count must be between 1 and {MAX_COUNT}, got {count}.")

        started = time.monotonic()
        created = seed_jobs(count)
        seconds = time.monotonic() - started

        if options["verbosity"] >= 1:
            self.stdout.write(self.style.SUCCESS(f"Created {created} jobs in {seconds:.1f}s."))
        if created < count:
            self.stdout.write(self.style.WARNING(f"Skipped {count - created}: their names were already taken."))


def seed_jobs(count: int) -> int:
    """Insert jobs named after their own ids, each with one ``PENDING`` status row.

    :param count: The number of jobs to create.
    :returns: The number of jobs created; lower than ``count`` if some names were taken.
    """
    with connection.cursor() as cursor:
        cursor.execute(_SEED_SQL, {"count": count, "prefix": NAME_PREFIX, "status": StatusType.PENDING.value})
        # The outer INSERT writes one status row per job created.
        return cursor.rowcount
