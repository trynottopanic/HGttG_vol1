from __future__ import annotations

import json
import socket
import threading
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from guide_node_core import MAX_PAIR_FAILURES, NodeState, is_local_address
from guide_node_server import DISCOVERY_REQUEST, DiscoveryResponder, GuideHTTPServer


class NodeStateTests(unittest.TestCase):
    def test_local_network_filter(self) -> None:
        self.assertTrue(is_local_address("127.0.0.1"))
        self.assertTrue(is_local_address("192.168.1.4"))
        self.assertFalse(is_local_address("8.8.8.8"))
        self.assertFalse(is_local_address("not-an-address"))

    def test_pair_and_revoke(self) -> None:
        state = NodeState()
        result = state.pair("127.0.0.1", state.pairing_code, "Test Deck")
        self.assertTrue(result.ok)
        self.assertTrue(state.authenticate(result.token or ""))
        self.assertTrue(state.unpair(result.token or ""))
        self.assertFalse(state.authenticate(result.token or ""))

    def test_pairing_rate_limit(self) -> None:
        state = NodeState()
        for _ in range(MAX_PAIR_FAILURES):
            self.assertFalse(state.pair("192.168.1.8", "wrong", "Deck").ok)
        locked = state.pair("192.168.1.8", state.pairing_code, "Deck")
        self.assertEqual(locked.reason, "pairing temporarily locked")

    def test_android_provider_is_not_enabled_by_detection(self) -> None:
        state = NodeState()
        status = state.android.status()
        self.assertFalse(status["available"])
        self.assertIn(status["state"], {"not-installed", "detected-not-enabled"})

    def test_trust_requires_node_approval_and_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            client_id = "ab" * 16
            state = NodeState(config_path=config)
            paired = state.pair("127.0.0.1", state.pairing_code, "My Deck", client_id)
            self.assertIsNone(state.trust_session(paired.token or ""))
            state.arm_trust(True)
            trusted = state.trust_session(paired.token or "")
            self.assertIsNotNone(trusted)
            secret = trusted[1] if trusted else ""
            restarted = NodeState(config_path=config)
            self.assertEqual(restarted.node_id, state.node_id)
            self.assertTrue(restarted.reconnect(client_id, secret, "My Deck").ok)
            self.assertFalse(restarted.reconnect(client_id, "wrong", "My Deck").ok)


class DiscoveryTests(unittest.TestCase):
    def test_exact_local_request_receives_bounded_description(self) -> None:
        reservation = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
        reservation.close()
        responder = DiscoveryResponder(NodeState("Test Node"), "127.0.0.1", 4365, port)
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(2)
        try:
            responder.start()
            client.sendto(DISCOVERY_REQUEST, ("127.0.0.1", port))
            data, _ = client.recvfrom(4096)
            description = json.loads(data)
            self.assertEqual(description["protocol"], "guide-node/1")
            self.assertEqual(description["name"], "Test Node")
            self.assertEqual(description["address"], "http://127.0.0.1:4365")
        finally:
            client.close()
            responder.stop()


class NodeHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = NodeState(config_path=Path(self.temporary.name) / "node.json")
        self.server = GuideHTTPServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.state.close()
        self.temporary.cleanup()

    def call(self, path: str, method: str = "GET", data: dict | None = None,
             token: str = "") -> tuple[int, dict]:
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_status_requires_pairing(self) -> None:
        self.assertEqual(self.call("/guide/v1/status")[0], 401)

    def test_pair_then_read_capabilities(self) -> None:
        status, paired = self.call(
            "/guide/v1/pair", "POST",
            {"code": self.state.pairing_code, "client_name": "Test Deck"},
        )
        self.assertEqual(status, 200)
        status, payload = self.call("/guide/v1/capabilities", token=paired["token"])
        self.assertEqual(status, 200)
        self.assertTrue(payload["capabilities"][0]["available"])

    def test_no_arbitrary_command_route(self) -> None:
        paired = self.call(
            "/guide/v1/pair", "POST",
            {"code": self.state.pairing_code, "client_name": "Test Deck"},
        )[1]
        self.assertEqual(self.call("/guide/v1/command", "POST", {"command": "whoami"},
                                   paired["token"])[0], 404)

    def test_android_status_is_read_only_and_authenticated(self) -> None:
        self.assertEqual(self.call("/guide/v1/android/status")[0], 401)
        paired = self.call(
            "/guide/v1/pair", "POST",
            {"code": self.state.pairing_code, "client_name": "Test Deck"},
        )[1]
        status, payload = self.call("/guide/v1/android/status", token=paired["token"])
        self.assertEqual(status, 200)
        self.assertFalse(payload["available"])

    def test_application_request_waits_for_local_approval(self) -> None:
        executable = Path(self.temporary.name) / "example.exe"
        executable.write_bytes(b"MZ test fixture")
        profile = self.state.applications.add(executable, "Example", "Example Window")
        paired = self.call(
            "/guide/v1/pair", "POST",
            {"code": self.state.pairing_code, "client_name": "Test Deck",
             "client_id": "a" * 32},
        )[1]
        status, listing = self.call("/guide/v1/applications", token=paired["token"])
        self.assertEqual(status, 200)
        self.assertNotIn("executable", str(listing))
        status, session = self.call(
            f"/guide/v1/applications/{profile['id']}/sessions", "POST", {}, paired["token"])
        self.assertEqual(status, 202)
        self.assertEqual(session["state"], "pending")
        self.assertNotIn("stream_path", session)
        self.assertEqual(
            self.call(f"/guide/v1/application-sessions/{session['id']}/input",
                      "POST", {"button": "A"}, paired["token"])[0], 501)


if __name__ == "__main__":
    unittest.main()
