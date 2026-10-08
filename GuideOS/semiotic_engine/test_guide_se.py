from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import secrets
import threading
from unittest import mock

from guide_se_core import DeterministicBackend, JobManager, RequestProblem, summarize, validate_request
from guide_se_controller import EngineController
from guide_se_service import EngineServer, load_or_create_connection


def request_value(text: str = "One fact. Another fact. A final fact. Extra fact.") -> dict:
    return {
        "protocol": "guide-se/0",
        "request_id": secrets.token_hex(16),
        "task": {"kind": "text.summarize", "instruction": "Summarize supplied text.",
                 "output_format": "guide-summary/0"},
        "context": [{"id": "selected-text", "media_type": "text/plain", "content": text,
                     "source": {"label": "User selection"}}],
        "limits": {"deadline_ms": 5000, "max_output_chars": 200, "retention": "none"},
        "policy": {"tools": False, "network": False, "additional_context": False},
    }


class CoreTests(unittest.TestCase):
    def test_valid_request_and_bounded_summary(self) -> None:
        self.assertEqual(validate_request(request_value())["protocol"], "guide-se/0")
        self.assertEqual(summarize("One. Two. Three. Four.", 100), "One. Two. Three.")
        self.assertLessEqual(len(summarize("word " * 100, 25)), 25)

    def test_rejects_authority_and_unknown_fields(self) -> None:
        value = request_value()
        value["policy"]["network"] = True
        with self.assertRaises(RequestProblem):
            validate_request(value)
        value = request_value()
        value["surprise"] = "field"
        with self.assertRaises(RequestProblem):
            validate_request(value)

    def test_job_discards_context_after_completion(self) -> None:
        manager = JobManager()
        try:
            job = manager.submit(request_value("Private supplied paragraph."))
            deadline = time.time() + 2
            while job.state in {"queued", "running"} and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(job.state, "complete")
            self.assertIsNone(job.request)
            self.assertEqual(job.response["proposed_actions"], [])
        finally:
            manager.close()

    def test_connection_record_reuses_secret_without_printing_it(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "connection.json"
            first = load_or_create_connection(path, 4370)
            second = load_or_create_connection(path, 4371)
            self.assertEqual(first["token"], second["token"])
            self.assertEqual(second["url"], "http://127.0.0.1:4371")


class ControllerTests(unittest.TestCase):
    def test_background_start_and_clean_stop(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime, model = root / "runtime.exe", root / "model.gguf"
            runtime.touch()
            model.write_bytes(b"model")
            controller = EngineController(
                port=0, runtime=runtime, model=model,
                backend_factory=lambda _runtime, _model: DeterministicBackend())
            with mock.patch("guide_se_controller.default_connection_path",
                            return_value=root / "connection.json"):
                self.assertTrue(controller.start())
                deadline = time.time() + 2
                while controller.status()["state"] == "starting" and time.time() < deadline:
                    time.sleep(0.01)
                self.assertEqual(controller.status()["state"], "ready")
                self.assertTrue(controller.stop())
                deadline = time.time() + 3
                while controller.status()["state"] == "stopping" and time.time() < deadline:
                    time.sleep(0.01)
                self.assertEqual(controller.status()["state"], "stopped")


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.token = secrets.token_urlsafe(32)
        self.manager = JobManager()
        self.server = EngineServer(("127.0.0.1", 0), self.manager, self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.manager.close()
        self.thread.join(timeout=2)

    def call(self, method: str, path: str, value: dict | None = None, token: str | None = None):
        body = json.dumps(value).encode() if value is not None else None
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_about_public_but_jobs_require_secret(self) -> None:
        self.assertEqual(self.call("GET", "/semiotic/v0/about")[0], 200)
        self.assertEqual(self.call("POST", "/semiotic/v0/jobs", request_value())[0], 401)

    def test_submit_and_read_completed_job(self) -> None:
        status, submitted = self.call("POST", "/semiotic/v0/jobs", request_value(), self.token)
        self.assertEqual(status, 202)
        deadline = time.time() + 2
        while time.time() < deadline:
            status, current = self.call("GET", "/semiotic/v0/jobs/" + submitted["job_id"], token=self.token)
            if current["state"] not in {"queued", "running"}:
                break
            time.sleep(0.01)
        self.assertEqual(current["state"], "complete")
        self.assertEqual(current["result"]["format"], "guide-summary/0")

    def test_authenticated_shutdown_releases_server(self) -> None:
        self.assertEqual(self.call("POST", "/semiotic/v0/shutdown", {}, "wrong")[0], 401)
        self.assertEqual(self.call("POST", "/semiotic/v0/shutdown", {}, self.token)[0], 202)


if __name__ == "__main__":
    unittest.main()
