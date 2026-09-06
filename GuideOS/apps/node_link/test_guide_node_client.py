from __future__ import annotations

import sys
from pathlib import Path
import threading
import tempfile
import unittest

DESKTOP_NODE = Path(__file__).resolve().parents[2] / "node" / "desktop"
sys.path.insert(0, str(DESKTOP_NODE))

from guide_node_core import NodeState
from guide_node_server import GuideHTTPServer
from guide_node_client import NodeClient, NodeLinkError, validate_node_description


def description(address: str = "http://127.0.0.1:4365") -> dict:
    return {
        "protocol": "guide-node/1",
        "node_id": "0123456789abcdef0123456789abcdef",
        "name": "Test Node",
        "address": address,
        "pairing_required": True,
        "transport_security": "development-local-http",
    }


class DescriptionTests(unittest.TestCase):
    def test_accepts_local_node(self) -> None:
        self.assertEqual(validate_node_description(description())["name"], "Test Node")

    def test_rejects_public_or_credentialed_address(self) -> None:
        with self.assertRaises(NodeLinkError):
            validate_node_description(description("http://8.8.8.8:4365"))
        with self.assertRaises(NodeLinkError):
            validate_node_description(description("http://user:pass@127.0.0.1:4365"))

    def test_rejects_wrong_protocol(self) -> None:
        value = description()
        value["protocol"] = "guide-node/999"
        with self.assertRaises(NodeLinkError):
            validate_node_description(value)


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state = NodeState("Test Node", Path(self.temp.name) / "config.json")
        self.server = GuideHTTPServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = NodeClient(description(
            f"http://127.0.0.1:{self.server.server_port}"
        ))

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_pair_and_read_status(self) -> None:
        self.client.pair(self.state.pairing_code)
        self.assertTrue(self.client.status()["ready"])
        self.assertIn("capabilities", self.client.capabilities())
        self.assertFalse(self.client.android_status()["available"])

    def test_pair_requires_six_numbers(self) -> None:
        with self.assertRaises(NodeLinkError):
            self.client.pair("hello")

    def test_unpair_revokes_session(self) -> None:
        self.client.pair(self.state.pairing_code)
        token = self.client.token
        self.client.unpair()
        self.assertFalse(self.state.authenticate(token))

    def test_reciprocal_trust_reconnects_without_pairing_code(self) -> None:
        client_id = "cd" * 16
        self.client.pair(self.state.pairing_code, client_id=client_id)
        self.state.arm_trust(True)
        trusted = self.client.trust()
        second = NodeClient(self.client.description)
        second.reconnect(client_id, trusted["secret"])
        self.assertTrue(second.status()["ready"])


if __name__ == "__main__":
    unittest.main()
