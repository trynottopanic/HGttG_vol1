from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

ENGINE_DIRECTORY = Path(__file__).resolve().parents[2] / "semiotic_engine"
sys.path.insert(0, str(ENGINE_DIRECTORY))
DECK_CLIENT_DIRECTORY = Path(__file__).resolve().parents[2] / "apps" / "node_link"
sys.path.insert(0, str(DECK_CLIENT_DIRECTORY))

from guide_se_core import JobManager
from guide_se_service import EngineServer
from guide_node_core import NodeState
from guide_node_server import GuideHTTPServer
from semiotic_provider import SemioticProvider
from guide_node_client import NodeClient, NodeLinkError


class SemioticNodePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.engine_token = "engine-test-token-that-is-long-enough-1234"
        self.manager = JobManager()
        self.engine = EngineServer(("127.0.0.1", 0), self.manager, self.engine_token)
        self.engine_thread = threading.Thread(target=self.engine.serve_forever, daemon=True)
        self.engine_thread.start()
        connection = root / "connection.json"
        connection.write_text(json.dumps({
            "protocol": "guide-se/0",
            "url": f"http://127.0.0.1:{self.engine.server_port}",
            "token": self.engine_token,
        }), encoding="utf-8")
        provider = SemioticProvider(True, connection)
        self.state = NodeState(config_path=root / "node.json", semiotic_provider=provider)
        self.node = GuideHTTPServer(("127.0.0.1", 0), self.state)
        self.node_thread = threading.Thread(target=self.node.serve_forever, daemon=True)
        self.node_thread.start()
        self.base = f"http://127.0.0.1:{self.node.server_port}"

    def tearDown(self) -> None:
        self.node.shutdown()
        self.node.server_close()
        self.node_thread.join(timeout=2)
        self.state.close()
        self.engine.shutdown()
        self.engine.server_close()
        self.manager.close()
        self.engine_thread.join(timeout=2)
        self.temporary.cleanup()

    def call(self, path: str, method: str = "GET", value: dict | None = None,
             token: str = "") -> tuple[int, dict]:
        body = json.dumps(value).encode() if value is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def pair(self, name: str) -> str:
        return self.call("/guide/v1/pair", "POST", {
            "code": self.state.pairing_code,
            "client_name": name,
        })[1]["token"]

    def test_engine_is_separate_and_jobs_are_scoped_to_one_deck(self) -> None:
        first = self.pair("First Deck")
        second = self.pair("Second Deck")
        capabilities = self.call("/guide/v1/capabilities", token=first)[1]["capabilities"]
        semiotic = next(item for item in capabilities if item["id"] == "semiotic.text")
        self.assertTrue(semiotic["available"])

        status, submitted = self.call("/guide/v1/semiotic/jobs", "POST", {
            "text": "The Deck owns authority. The Engine interprets supplied signs. The Node relays bounded requests. No component silently gains permission.",
            "source_label": "Acceptance test",
        }, first)
        self.assertEqual(status, 202)
        path = "/guide/v1/semiotic/jobs/" + submitted["job_id"]
        self.assertEqual(self.call(path, token=second)[0], 404)
        deadline = time.time() + 2
        while time.time() < deadline:
            status, job = self.call(path, token=first)
            if job["state"] not in {"queued", "running"}:
                break
            time.sleep(0.01)
        self.assertEqual(status, 200)
        self.assertEqual(job["state"], "complete")
        self.assertEqual(job["proposed_actions"], [])
        self.assertIn("Deck owns authority", job["result"]["text"])

    def test_deck_client_completes_bounded_summary(self) -> None:
        client = NodeClient({
            "protocol": "guide-node/1", "name": "Test Node",
            "node_id": self.state.node_id, "address": self.base,
        })
        client.token = client.pair(self.state.pairing_code)["token"]
        submitted = client.semiotic_submit(
            "Decks carry the user's interface. Nodes offer explicitly selected services. ")
        deadline = time.time() + 2
        current = submitted
        while current.get("state") in {"queued", "running"} and time.time() < deadline:
            current = client.semiotic_job(str(submitted["job_id"]))
            time.sleep(0.01)
        self.assertEqual(current["state"], "complete")
        self.assertEqual(current["proposed_actions"], [])

    def test_deck_client_rejects_oversized_engine_input(self) -> None:
        client = NodeClient({
            "protocol": "guide-node/1", "name": "Test Node",
            "node_id": self.state.node_id, "address": self.base,
        })
        with self.assertRaises(NodeLinkError):
            client.semiotic_submit("x" * 32_001)


if __name__ == "__main__":
    unittest.main()
