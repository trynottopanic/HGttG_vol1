# SPDX-License-Identifier: AGPL-3.0-or-later
import unittest
import uuid

from deck_event_gate import EventGate, PROTOCOL, sign_event


class EventGateTests(unittest.TestCase):
    secret = b"prototype-shared-secret"
    now = 1_800_000_000

    def event(self, person="dad", age=0):
        return {"protocol": PROTOCOL, "type": "message.received",
                "event_id": str(uuid.uuid4()), "created_unix": self.now - age,
                "person_id": person}

    def test_selected_sender_triggers_once(self):
        gate = EventGate({"phone": self.secret}, "dad")
        event = self.event()
        signature = sign_event(event, self.secret)
        self.assertTrue(gate.accept("phone", event, signature, self.now))
        with self.assertRaisesRegex(ValueError, "already"):
            gate.accept("phone", event, signature, self.now)

    def test_other_sender_is_authenticated_but_does_not_trigger(self):
        gate = EventGate({"phone": self.secret}, "dad")
        event = self.event("friend")
        self.assertFalse(gate.accept("phone", event, sign_event(event, self.secret), self.now))

    def test_bad_signature_and_stale_event_are_rejected(self):
        gate = EventGate({"phone": self.secret}, "dad")
        event = self.event()
        with self.assertRaises(PermissionError):
            gate.accept("phone", event, "0" * 64, self.now)
        stale = self.event(age=121)
        with self.assertRaisesRegex(ValueError, "stale"):
            gate.accept("phone", stale, sign_event(stale, self.secret), self.now)

    def test_sound_is_rate_limited(self):
        gate = EventGate({"phone": self.secret}, "dad", max_sounds=2)
        for offset in range(2):
            event = self.event()
            self.assertTrue(gate.accept("phone", event, sign_event(event, self.secret), self.now + offset))
        event = self.event()
        with self.assertRaisesRegex(ValueError, "rate limit"):
            gate.accept("phone", event, sign_event(event, self.secret), self.now + 2)


if __name__ == "__main__":
    unittest.main()
