from dataclasses import replace
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from at_field import ATField, FieldMode
from guide_node_core import NodeState
from guide_node_server import DISCOVERY_REQUEST, DiscoveryResponder


class FieldPolicyTests(unittest.TestCase):
    def test_modes_and_exceptions(self):
        closed = ATField(FieldMode.CLOSED)
        familiar = ATField(FieldMode.FAMILIAR)
        opened = ATField(FieldMode.OPEN)
        self.assertEqual(closed.connection(known=True), "decline")
        self.assertEqual(familiar.connection(), "ask")
        self.assertEqual(familiar.connection(known=True), "allow")
        self.assertEqual(familiar.connection(accepted=True), "allow")
        self.assertEqual(opened.connection(), "allow")
        for field in (closed, familiar, opened):
            self.assertEqual(field.connection(initiated_here=True), "allow")
        self.assertEqual(replace(closed, exceptions=(("peer", True),)).connection("peer"), "allow")
        self.assertEqual(replace(opened, exceptions=(("peer", False),)).connection("peer"), "decline")

    def test_invalid_and_round_trip(self):
        field = ATField(FieldMode.FAMILIAR, (("peer", False),))
        self.assertEqual(ATField.from_dict(field.to_dict()), field)
        for value in ({"version": 1, "mode": "typo"},
                      {"version": 1, "mode": "open", "exceptions": {"peer": "false"}}):
            with self.assertRaises(ValueError):
                ATField.from_dict(value)


class FieldNodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Path(self.temp.name) / "node.json"
        self.state = NodeState(config_path=self.config)
        self.peer = "ab" * 16

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def pair(self):
        return self.state.pair("127.0.0.1", self.state.pairing_code, "Deck", self.peer)

    def test_changes_preserve_sessions_permissions_and_saved_setting(self):
        result = self.pair()
        capabilities = self.state.capabilities()
        preview = self.state.preview_at_field("closed")
        self.assertIn("1 active", preview)
        self.assertEqual(self.state.at_field.mode, FieldMode.OPEN)
        self.state.set_at_field("closed")
        self.assertTrue(self.state.authenticate(result.token))
        self.assertEqual(self.state.capabilities(), capabilities)
        self.assertFalse(self.pair().ok)
        restarted = NodeState(config_path=self.config)
        try:
            self.assertEqual(restarted.at_field.mode, FieldMode.CLOSED)
        finally:
            restarted.close()

    def test_familiar_reconnect_and_closed_exception_still_require_credentials(self):
        paired = self.pair()
        self.state.arm_trust(True)
        _, secret = self.state.trust_session(paired.token)
        self.state.set_at_field("familiar")
        self.assertTrue(self.state.reconnect(self.peer, secret, "Deck").ok)
        self.assertFalse(self.state.pair("127.0.0.1", "wrong", "Stranger").ok)
        self.state.set_at_field("closed")
        self.assertFalse(self.state.reconnect(self.peer, secret, "Deck").ok)
        self.state.set_at_field_exception(self.peer, True)
        self.assertTrue(self.state.reconnect(self.peer, secret, "Deck").ok)
        self.assertFalse(self.state.reconnect(self.peer, "wrong", "Deck").ok)
        self.state.set_at_field("open")
        self.state.set_at_field_exception(self.peer, False)
        self.assertFalse(self.state.reconnect(self.peer, secret, "Deck").ok)
        self.state.set_at_field_exception(self.peer, None)
        self.assertTrue(self.state.reconnect(self.peer, secret, "Deck").ok)

    def test_save_failure_keeps_effective_setting_and_unrelated_config(self):
        self.config.write_text(json.dumps({"unrelated": "retained"}))
        self.state.set_at_field("familiar")
        self.assertEqual(json.loads(self.config.read_text())["unrelated"], "retained")
        with patch.object(self.state, "_save_trust", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.state.set_at_field("open")
        self.assertEqual(self.state.at_field.mode, FieldMode.FAMILIAR)

    def test_discovery_respects_live_changes_over_real_udp(self):
        responder = DiscoveryResponder(self.state, "127.0.0.1", 4365, 0)
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(0.2)
        try:
            responder.start()
            port = responder._socket.getsockname()[1]
            for mode in ("open", "familiar", "closed", "open"):
                self.state.set_at_field(mode)
                client.sendto(DISCOVERY_REQUEST, ("127.0.0.1", port))
                if mode == "open":
                    self.assertEqual(json.loads(client.recvfrom(4096)[0])["protocol"], "guide-node/1")
                else:
                    with self.assertRaises(socket.timeout):
                        client.recvfrom(4096)
        finally:
            client.close()
            responder.stop()


if __name__ == "__main__":
    unittest.main()
