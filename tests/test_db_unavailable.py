"""A Neo4j that can't serve a query is a 503, and each request logs one line.

After the 2026-10-23 disk-full outage: a panicked database raised
``TransactionStartFailed`` (a ``DatabaseError``), which ``_run_query`` swallowed
as "no rows", so writes were lost without the client retrying. And three log
lines a request, plus every query's Cypher, is what filled the disk.

Needs no Neo4j or server: the driver and DB are mocked.

Run: uv run python -m unittest tests.test_db_unavailable
"""
import asyncio
import json
import logging
import unittest
from unittest import mock

from neo4j.exceptions import (CypherSyntaxError, DatabaseError, DatabaseUnavailable,
                              ServiceUnavailable, SessionExpired)
from starlette.requests import Request
from starlette.responses import Response

from educelab import hercdb
from educelab.hercdb.db.connection import DatabaseUnavailableError, GraphDBConnection

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server


class FailingConnection(GraphDBConnection):
    """A connection whose driver raises `error` on every query."""

    def __init__(self, error):
        self.driver = mock.Mock()
        self.driver.execute_query.side_effect = error
        self.logger = logging.getLogger("test-db-unavailable")
        self.logger.disabled = True


def panicked():
    return DatabaseError._hydrate_neo4j(
        code="Neo.DatabaseError.Transaction.TransactionStartFailed",
        message="The database has encountered a critical error, and needs to be restarted.")


def starting():
    return DatabaseUnavailable._hydrate_neo4j(
        code="Neo.TransientError.General.DatabaseUnavailable", message="Database is starting")


class TestRunQueryErrors(unittest.TestCase):

    def test_server_side_failures_raise_unavailable(self):
        for error in (ServiceUnavailable("down"), SessionExpired("lost"), starting(), panicked()):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(DatabaseUnavailableError):
                    FailingConnection(error)._run_query("RETURN 1")

    def test_panicked_database_is_classified_as_database_error(self):
        # Guards the driver's mapping the fix relies on.
        self.assertIsInstance(panicked(), DatabaseError)

    def test_bad_query_still_reads_as_no_rows(self):
        # Unchanged for now (#34): only server-side failures become 503.
        error = CypherSyntaxError._hydrate_neo4j(
            code="Neo.ClientError.Statement.SyntaxError", message="bad")
        self.assertEqual(FailingConnection(error)._run_query("RETRUN 1"), (None, None, None))

    def test_unavailable_maps_to_503_with_retry_after(self):
        response = asyncio.run(server.database_unavailable_handler(
            make_request("PUT", "/pipelines/p/processes/PGS/status"),
            DatabaseUnavailableError("panicked")))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["retry-after"], "60")
        self.assertIn("retry", json.loads(response.body)["detail"])


def make_request(method, path, query=b""):
    return Request({
        "type": "http", "method": method, "path": path, "query_string": query,
        "headers": [(b"authorization", b"Bearer not-a-token")],
        "client": ("10.0.0.5", 51234),
    })


class TestRequestLogging(unittest.TestCase):

    def test_one_info_line_with_query_status_and_client(self):
        async def call_next(request):
            return Response(status_code=404)

        with self.assertLogs("api-auth", level="INFO") as logs:
            asyncio.run(server.log_requests(
                make_request("GET", "/artifacts", b"pherc=1044&cornice=2"), call_next))
        self.assertEqual(len(logs.output), 1)
        line = logs.output[0]
        for part in ("GET /artifacts?pherc=1044&cornice=2", "-> 404", " ms", "user: unknown", "10.0.0.5"):
            self.assertIn(part, line)

    def test_uvicorn_access_log_is_silenced(self):
        self.assertFalse(logging.getLogger("uvicorn.access").isEnabledFor(logging.INFO))

    def test_read_handlers_log_below_info(self):
        with self.assertNoLogs("api-auth", level="INFO"):
            asyncio.run(server.home(user="t"))

    def test_successful_query_text_logs_below_info(self):
        db = FailingConnection(None)
        db.driver.execute_query.side_effect = None
        db.driver.execute_query.return_value = ([], None, [])
        db.logger.disabled = False
        with self.assertNoLogs(db.logger.name, level="INFO"):
            db._run_query("RETURN 1")


if __name__ == "__main__":
    unittest.main()
