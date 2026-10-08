"""Experimental portable analog-stick timing for the shared Guide keyboard.

The host supplies normalized snapshots: +x points right and +y points down.
This module reads no devices and retains neither entered text nor input history.
Left-stick movement is applied before a new right-stick preview. Moving its
anchor during an existing preview cancels it; neutral confirms a stable preview.
"""

import math
import time

from guide_text_entry import TextOwnershipError


ENGAGE_THRESHOLD = 0.55
RELEASE_THRESHOLD = 0.30
INITIAL_REPEAT_DELAY = 0.350
REPEAT_INTERVAL = 0.125
ANGULAR_HYSTERESIS_DEGREES = 7.5
DIRECTIONS = ((1, 0), (1, 1), (0, 1), (-1, 1),
              (-1, 0), (-1, -1), (0, -1), (1, -1))


def _position(value):
    """Malformed/missing samples disarm that stick until neutral is observed."""
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or not -1 <= v <= 1 for v in value):
        return None
    return value[0], value[1]


def _direction(x, y):
    sector = int(math.floor((math.atan2(y, x) + math.pi / 8) / (math.pi / 4))) % 8
    return DIRECTIONS[sector]


class _Stick:
    def __init__(self):
        self.reset()

    def reset(self):
        self.armed = False
        self.direction = None
        self.next_repeat = None

    def sample(self, position, now):
        position = _position(position)
        if position is None:
            self.reset()
            return None
        x, y = position
        magnitude = math.hypot(x, y)
        if magnitude <= RELEASE_THRESHOLD:
            self.armed = True
            self.direction = None
            self.next_repeat = None
            return None
        if not self.armed:
            return None
        if self.direction is None and magnitude < ENGAGE_THRESHOLD:
            return None
        direction = _direction(x, y)
        if self.direction is not None and direction != self.direction:
            angle = math.atan2(y, x) - math.atan2(self.direction[1], self.direction[0])
            distance = abs(math.atan2(math.sin(angle), math.cos(angle)))
            if distance <= math.pi / 8 + math.radians(ANGULAR_HYSTERESIS_DEGREES):
                # Retain the held sector across small angular noise. Intentional
                # changes beyond this narrow margin still move immediately.
                direction = self.direction
        if direction != self.direction:
            self.direction = direction
            self.next_repeat = now + INITIAL_REPEAT_DELAY
            return direction
        if now >= self.next_repeat:
            # Schedule from this observation, never replay missed repeat ticks.
            self.next_repeat = now + REPEAT_INTERVAL
            return direction
        return None


class StickController:
    """Drive one owned keyboard using radial hysteresis and eight directions.

    ``generation`` is the host's input/focus generation. Change it after dropped
    events, device reattachment, or focus recovery. Each stick must subsequently
    report neutral before it can act. ``None`` disarms only the missing stick.
    The host calls reset() after global controls. A right-stick click can call
    reset_right() to require right-stick neutral without disrupting left holds.

    Call update regularly while visible, including unchanged held snapshots.
    Each update performs at most one left movement and one right activation.
    Cursor edits and key semantics remain the keyboard's responsibility.
    """

    def __init__(self, keyboard, clock=time.monotonic):
        self.keyboard = keyboard
        self.clock = clock
        self._left = _Stick()
        self._right = _Stick()
        self.reset()

    def reset(self):
        self._left.reset()
        self._right.reset()
        self.keyboard.stick_highlight = None
        self._anchor = None
        self._context = None
        self._last_now = None

    def reset_right(self):
        self._right.reset()
        self.keyboard.stick_highlight = None
        self._anchor = None

    def _preview_right(self, value):
        """Track a held sector; only an observed neutral commits its key."""
        before = self.keyboard.stick_highlight
        position = _position(value)
        anchor = (self.keyboard.focus, getattr(self.keyboard, 'page', 0))
        if position is None or (self._anchor is not None and self._anchor != anchor):
            self.reset_right()
            return before is not None, None
        magnitude = math.hypot(*position)
        if magnitude <= RELEASE_THRESHOLD:
            direction = self._right.direction
            self._right.armed = True
            self._right.direction = None
            self.keyboard.stick_highlight = None
            self._anchor = None
            return before is not None, direction if before is not None else None
        if not self._right.armed or (self._right.direction is None and magnitude < ENGAGE_THRESHOLD):
            return False, None
        direction = _direction(*position)
        previous = self._right.direction
        if previous is not None and direction != previous:
            delta = math.atan2(position[1], position[0]) - math.atan2(previous[1], previous[0])
            if abs(math.atan2(math.sin(delta), math.cos(delta))) <= math.pi / 8 + math.radians(ANGULAR_HYSTERESIS_DEGREES):
                direction = previous
        if direction == previous and self._anchor == anchor:
            return False, None
        self._right.direction = direction
        self._anchor = anchor
        self.keyboard.stick_highlight = self.keyboard.neighbors.get(direction)
        return before != self.keyboard.stick_highlight, None

    def _owned_context(self, generation):
        session = self.keyboard.session
        if session.state != 'editing' or self.keyboard.manager.active is not session:
            return None
        return session, session.token, session.request.owner_id, generation

    def update(self, left=None, right=None, generation=0, now=None):
        old_highlight = self.keyboard.stick_highlight
        context = self._owned_context(generation)
        if context is None:
            self.reset()
            return old_highlight is not None
        now = self.clock() if now is None else now
        if (isinstance(now, bool) or not isinstance(now, (int, float))
                or not math.isfinite(now)):
            self.reset()
            return old_highlight is not None
        if context != self._context or (self._last_now is not None and now < self._last_now):
            self.reset()
            self._context = context
        self._last_now = now
        moved = self._left.sample(left, now)
        changed = old_highlight != self.keyboard.stick_highlight
        try:
            if moved is not None:
                changed = bool(self.keyboard.move_selection(*moved)) or changed
            # Recheck ownership between the two independent semantic actions.
            if self._owned_context(generation) != context:
                self.reset()
                return changed
            preview_changed, activated = self._preview_right(right)
            changed = preview_changed or changed
            if activated is not None:
                changed = bool(self.keyboard.activate_neighbor(*activated)) or changed
        except TextOwnershipError:
            self.reset()
            return old_highlight is not None
        if self._owned_context(generation) != context:
            self.reset()
        return changed
