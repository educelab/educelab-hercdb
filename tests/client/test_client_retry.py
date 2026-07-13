"""Unit tests for HercClient's automatic retry + timeout behavior.

Unlike the other files in this directory (which are live-server integration
scripts), this is a self-contained ``unittest`` module: it spins up a scripted
local HTTP server so the real requests/urllib3 retry path is exercised, with
``backoff_factor=0`` so retries are instant.

Run: uv run python -m unittest tests.client.test_client_retry
"""
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

import requests

from educelab.hercdb.client import HercClient


class _ScriptedHandler(BaseHTTPRequestHandler):
    """Returns a scripted sequence of status codes, counting every request.

    ``statuses`` is consumed one entry per request; once exhausted the last
    entry repeats. ``body`` is the response payload for non-error responses.
    Both, plus the ``calls`` counter, are set on the class per test.
    """

    statuses = [200]
    body = b"{}"
    calls = 0

    def log_message(self, *args):  # silence per-request stderr logging
        pass

    def _serve(self):
        cls = type(self)
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)  # drain request body so the socket is clean
        idx = min(cls.calls, len(cls.statuses) - 1)
        status = cls.statuses[idx]
        cls.calls += 1
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(cls.body)

    do_GET = _serve
    do_POST = _serve
    do_PUT = _serve
    do_DELETE = _serve


class RetryBehaviorTest(unittest.TestCase):
    def setUp(self):
        _ScriptedHandler.calls = 0
        _ScriptedHandler.statuses = [200]
        _ScriptedHandler.body = b"{}"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _ScriptedHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        port = self.server.server_address[1]
        # backoff_factor=0 -> instant retries; small timeout keeps the test snappy.
        self.client = HercClient(
            host="127.0.0.1", port=port, token="tok",
            timeout=2, retries=5, backoff_factor=0,
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    # -- retry rides over transient 503s -----------------------------------

    def test_get_retries_on_503_then_succeeds(self):
        _ScriptedHandler.statuses = [503, 503, 200]
        _ScriptedHandler.body = b'{"ok": true}'
        result = self.client.check_token()  # GET via _request
        self.assertEqual(result, {"ok": True})
        self.assertEqual(_ScriptedHandler.calls, 3)  # 2 failures + 1 success

    def test_post_is_retried(self):
        # Proves allowed_methods=None: by default urllib3 does NOT retry POST.
        _ScriptedHandler.statuses = [503, 200]
        _ScriptedHandler.body = b'{"pipeline_id": "p1"}'
        result = self.client.initialize_pipeline("p1", "uuid-1", "2026-01-01T00:00:00")
        self.assertEqual(result, {"pipeline_id": "p1"})
        self.assertEqual(_ScriptedHandler.calls, 2)

    def test_bypass_method_now_retries(self):
        # get_datasets_for_educelabid used to call requests.get directly, bypassing
        # any Session-level retry. It must now retry too.
        _ScriptedHandler.statuses = [503, 503, 200]
        _ScriptedHandler.body = b'[{"type": "PGSRaw"}]'
        result = self.client.get_datasets_for_educelabid("uuid-1")
        self.assertEqual(result, [{"type": "PGSRaw"}])
        self.assertEqual(_ScriptedHandler.calls, 3)

    # -- non-transient errors are NOT retried ------------------------------

    def test_genuine_404_not_retried(self):
        _ScriptedHandler.statuses = [404]
        with self.assertRaises(requests.HTTPError):
            self.client.check_token()
        self.assertEqual(_ScriptedHandler.calls, 1)  # no retries on 404

    def test_500_not_retried(self):
        # 500 is not in the retryable status_forcelist (502/503/504).
        _ScriptedHandler.statuses = [500]
        with self.assertRaises(requests.HTTPError):
            self.client.check_token()
        self.assertEqual(_ScriptedHandler.calls, 1)

    # -- tolerate_404: bypass methods return empty, without retrying -------

    def test_tolerated_404_returns_empty_educelabid(self):
        _ScriptedHandler.statuses = [404]
        result = self.client.get_datasets_for_educelabid("missing")
        self.assertEqual(result, [])
        self.assertEqual(_ScriptedHandler.calls, 1)  # 404 tolerated, not retried

    def test_tolerated_404_returns_empty_pherc(self):
        _ScriptedHandler.statuses = [404]
        result = self.client.get_all_datasets_for_pherc("missing")
        self.assertEqual(result, {"pherc": "missing", "artifacts": []})
        self.assertEqual(_ScriptedHandler.calls, 1)


class TimeoutWiringTest(unittest.TestCase):
    """Every request must carry the configured timeout."""

    def test_timeout_passed_to_session(self):
        client = HercClient(host="h", port=8000, token="tok", timeout=7)
        fake = MagicMock(status_code=200)
        fake.json.return_value = {"ok": True}
        with patch.object(client._session, "request", return_value=fake) as m:
            client.check_token()
        self.assertEqual(m.call_args.kwargs.get("timeout"), 7)


if __name__ == "__main__":
    unittest.main()
