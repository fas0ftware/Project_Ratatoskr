"""Ratatoskr Web: job validation and limits, dry runs, scheduling and cancelling, the HTTP guards.

No browser is opened: dry runs print only, and real sends use a fake runner."""
import datetime as dt
import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import web
from web_base import HttpError


def wait_done(courier, job_id, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = next(j for j in courier.view()["jobs"] if j["id"] == job_id)
        if job["state"] not in ("queued", "scheduled", "running"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


class CourierTests(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp()) / "web.json"
        self.calls = []

        def fake_send(args):
            self.calls.append(args)
            for contact in args.contacts:
                print(f"  sent to {contact}")
            return 0
        self.courier = web.Courier(self.state, runner=fake_send)

    def test_dry_run_uses_the_real_flow_and_opens_no_browser(self):
        courier = web.Courier(self.state)  # the real main.run: dry runs only print
        job = courier.create(["Alice", "Alice", " Bob "], "line 1\nline 2 🙂", 2, 1.5, "", True)
        self.assertEqual(job["contacts"], ["Alice", "Bob"])
        done = wait_done(courier, job["id"])
        self.assertEqual(done["state"], "dry-run")
        self.assertIn("would send to 'Alice', 2x:", done["log"])
        self.assertIn("  | line 2 🙂", done["log"])
        self.assertEqual(courier.recent(), [], "dry runs are not remembered")

    def test_real_send_is_remembered_and_logged(self):
        job = self.courier.create(["Mom"], "hi", 1, 1.0, "", False)
        done = wait_done(self.courier, job["id"])
        self.assertEqual((done["state"], done["sent"]), ("sent", 1))
        self.assertFalse(self.calls[0].dry_run)
        self.assertEqual(self.courier.recent(), ["Mom"])

    def test_limits_match_the_command_line(self):
        bad = [([], "x", 1, 1.0, ""), (["A"], "  ", 1, 1.0, ""), (["A"], "x" * 4001, 1, 1.0, ""),
               (["A", "B"], "x", 11, 1.0, ""), (["A"], "x", 0, 1.0, ""), (["A"], "x", 1, 0.5, ""),
               (["A"], "x", 1, 1.0, "25:99"), (["A\nB"], "x", 1, 1.0, ""), (["A" * 81], "x", 1, 1.0, "")]
        for contacts, text, repeat, delay, at in bad:
            with self.subTest(contacts=contacts, repeat=repeat, at=at), self.assertRaises(HttpError):
                self.courier.create(contacts, text, repeat, delay, at, False)
        self.assertEqual(self.calls, [])

    def test_scheduled_job_waits_and_can_be_cancelled(self):
        later = (dt.datetime.now() + dt.timedelta(hours=1)).strftime("%H:%M")
        job = self.courier.create(["Mom"], "later", 1, 1.0, later, False)
        self.assertEqual(job["state"], "scheduled")
        self.courier.cancel(job["id"])
        time.sleep(1.2)
        self.assertEqual(self.courier.view()["jobs"][0]["state"], "cancelled")
        self.assertEqual(self.calls, [])
        with self.assertRaises(HttpError):
            self.courier.cancel(job["id"])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        cls.port = sock.getsockname()[1]
        sock.close()
        cls.courier = web.Courier(Path(tempfile.mkdtemp()) / "web.json", runner=lambda args: 0)
        app = web.build_app(cls.courier)
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), app.handler(cls.port))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, method, path, body=None, **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": f"127.0.0.1:{self.port}"}
        if body is not None:
            h |= {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}
        h |= headers
        conn.request(method, path, json.dumps(body) if body is not None else None, h)
        r = conn.getresponse()
        return r.status, r.read()

    def test_job_over_http_and_types(self):
        status, data = self.call("POST", "/api/jobs", {"contacts": ["Alice"], "text": "hi"})
        self.assertEqual(status, 200, data)
        self.assertTrue(json.loads(data)["jobs"][0]["dry_run"], "dry run is the default")
        for body in ({"contacts": "Alice", "text": "hi"}, {"contacts": [1], "text": "hi"},
                     {"contacts": ["A"] * 21, "text": "hi"}, {"contacts": ["A"], "text": "hi", "dry_run": "no"},
                     {"contacts": ["A"], "text": "hi", "repeat": "2"}):
            self.assertEqual(self.call("POST", "/api/jobs", body)[0], 400, body)

    def test_guards(self):
        self.assertEqual(self.call("GET", "/api/state", Host="evil.example")[0], 403)
        self.assertEqual(self.call("POST", "/api/jobs", {"contacts": ["A"], "text": "x", "dry_run": False},
                                   Origin="http://evil.example")[0], 403)
        self.assertEqual(self.call("GET", "/static/../main.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
