"""Portable experimental stick pointer and adaptive context menu.

The host owns hit testing, application actions, rendering, and physical buttons.
This model accepts normalized snapshots and returns only the chosen action ID.
It performs no device, filesystem, network, or logging operations.
"""

from dataclasses import dataclass
import math
import time


POINTER_DEADZONE = 0.12
POINTER_ENGAGE = 0.14
ACCEL_SMOOTHING_SECONDS = 0.010
CRUISE_SMOOTHING_SECONDS = 0.018
MAX_SPEED = 800.0
MAX_TIME_STEP = 1.0 / 60.0
MAX_ELAPSED = 0.20
CONTEXT_RADIUS = 84.0
CONTEXT_MARGIN = CONTEXT_RADIUS + 2.0
CONTEXT_INNER_RADIUS = 25.0
CONTEXT_ENGAGE = 0.55
CONTEXT_RELEASE = 0.30
ANGULAR_HYSTERESIS_DEGREES = 7.5
CARDINALS = ('right', 'down', 'left', 'up')
_UNSET = object()


def _finite_number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))


def _stick(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    if any(not _finite_number(v) or not -1 <= v <= 1 for v in value):
        return None
    return value[0], value[1]


@dataclass
class ContextMenu:
    center: tuple
    options: dict
    highlight: str = None
    radius: float = CONTEXT_RADIUS
    inner_radius: float = CONTEXT_INNER_RADIUS
    items: tuple = ()
    page: int = 0
    page_count: int = 1
    keyboard_choice: bool = False

    def sectors(self):
        if self.items:
            count = len(self.options)
            return {key: (-math.pi / 2 + index * math.tau / count, math.pi / count)
                    for index, key in enumerate(self.options)}
        return {key: (CARDINALS.index(key) * math.pi / 2, math.pi / 4)
                for key in self.options}


class PointerController:
    """Continuous left-stick cursor and right-stick release-to-confirm menu.

    Valid left-stick motion resumes immediately after reset/recovery. A context
    menu has no timer: the right stick highlights while held, and a return to
    neutral confirms once. Missing input or a held right-stick click discards
    the pending highlight rather than treating it as a confirming release.
    """

    def __init__(self, width=640, height=480, clock=time.monotonic):
        if type(width) is not int or type(height) is not int or width < 1 or height < 1:
            raise ValueError('Pointer dimensions must be positive integers.')
        self.width, self.height, self.clock = width, height, clock
        self.position = (min(width / 2, width - 1), min(height / 2, height - 1))
        self.visible = False
        self.context = None
        self.reset()

    def _reset_right(self):
        changed = self.context is not None and self.context.highlight is not None
        self._right_armed = False
        self._right_sector = None
        if self.context is not None:
            self.context.highlight = None
            self.context.keyboard_choice = False
        return changed

    def reset(self):
        """Discard temporal input state, preserving pointer position/visibility."""
        self._moving = False
        self._velocity = (0.0, 0.0)
        changed = self._reset_right()
        self._generation = _UNSET
        self._last_now = None
        return changed

    def move_to(self, x, y):
        if not _finite_number(x) or not _finite_number(y):
            raise ValueError('Pointer coordinates must be finite numbers.')
        position = (max(0.0, min(float(x), self.width - 1)),
                    max(0.0, min(float(y), self.height - 1)))
        changed = position != self.position or not self.visible
        self.position = position
        self.visible = True
        return changed

    def open_context(self, options, center=None):
        adaptive = isinstance(options, (list, tuple))
        if not adaptive and (not isinstance(options, dict) or len(options) > 4 or any(k not in CARDINALS for k in options)):
            raise ValueError('Context options must use up to four cardinal directions.')
        copied = {}
        for direction, option in (enumerate(options) if adaptive else options.items()):
            if (not isinstance(option, dict) or
                    any(not isinstance(option.get(key), str) or not option[key] for key in ('id', 'label')) or
                    option['id'].startswith('$page:')):
                raise ValueError('Each context option needs an action ID and label.')
            copied[direction] = dict(id=option['id'], label=option['label'])
        center = self.position if center is None else center
        if (not isinstance(center, (tuple, list)) or len(center) != 2
                or any(not _finite_number(v) for v in center)):
            raise ValueError('The context center must contain two finite numbers.')
        # Keep the menu and its outline inside the normal viewport.
        # Smaller future viewports can render the explicitly reduced radius.
        margin = min(CONTEXT_MARGIN, (self.width - 1) / 2, (self.height - 1) / 2)
        position = (max(margin, min(float(center[0]), self.width - 1 - margin)),
                    max(margin, min(float(center[1]), self.height - 1 - margin)))
        radius = max(0.0, margin - 2)
        self.context = ContextMenu(position, copied, radius=radius,
                                   inner_radius=min(CONTEXT_INNER_RADIUS, radius / 3))
        if adaptive and copied:
            self.context.items = tuple(copied.values())
            self.context.inner_radius = min(14, radius / 3)
            self.context.page_count = math.ceil(len(copied) / 6) if len(copied) > 8 else 1
            self._set_page(0)
        self.visible = True
        self._reset_right()
        return self.context

    def _set_page(self, page):
        context = self.context
        context.page = page % context.page_count
        items = context.items
        if context.page_count > 1:
            items = items[context.page * 6:context.page * 6 + 6] + (
                dict(id='$page:previous', label='Previous'), dict(id='$page:next', label='More'))
        context.options = {f'choice:{index}': item for index, item in enumerate(items)}
        self._reset_right()

    def step_choice(self, delta):
        if self.context is None or not self.context.options:
            return False
        keys = list(self.context.options)
        selected = self.context.highlight
        index = keys.index(selected) if selected in keys else (-1 if delta > 0 else 0)
        self._reset_right()
        self.context.highlight = keys[(index + delta) % len(keys)]
        self.context.keyboard_choice = True
        return True

    def _direction(self, angle):
        for key, (center, half_width) in self.context.sectors().items():
            delta = abs(math.atan2(math.sin(angle - center), math.cos(angle - center)))
            if delta <= half_width + 1e-9:
                return key
        return None

    def close_context(self):
        changed = self.context is not None
        self.context = None
        self._reset_right()
        return changed

    def direction_at(self, x, y):
        """Return a present wedge under the pointer, excluding center/outside."""
        if self.context is None or not _finite_number(x) or not _finite_number(y):
            return None
        dx, dy = x - self.context.center[0], y - self.context.center[1]
        distance = math.hypot(dx, dy)
        if distance <= self.context.inner_radius or distance > self.context.radius:
            return None
        return self._direction(math.atan2(dy, dx))

    def choose(self, direction):
        if self.context is None or direction not in self.context.options:
            return None
        action = self.context.options[direction]['id']
        if action.startswith('$page:'):
            self._set_page(self.context.page + (1 if action == '$page:next' else -1))
            return None
        self.close_context()
        return action

    def _move(self, value, dt):
        position = _stick(value)
        if position is None:
            self._moving = False
            self._velocity = (0.0, 0.0)
            return False
        x, y = position
        magnitude = math.hypot(x, y)
        if magnitude <= POINTER_DEADZONE:
            self._moving = False
            self._velocity = (0.0, 0.0)
            return False
        if dt <= 0 or (not self._moving and magnitude < POINTER_ENGAGE):
            return False
        self._moving = True
        # A nearly linear response keeps the middle of the physical stick useful;
        # the radial deadzone still protects against resting drift.
        response = (min(magnitude, 1.0) - POINTER_DEADZONE) / (1.0 - POINTER_DEADZONE)
        speed = MAX_SPEED * (0.08 + 0.92 * response)
        target = (x / magnitude * speed, y / magnitude * speed)
        previous = self._velocity
        reversing = sum(old * new for old, new in zip(previous, target)) < 0
        accelerating = math.hypot(*target) > math.hypot(*previous) + 1.0
        smoothing = (ACCEL_SMOOTHING_SECONDS if reversing or accelerating
                     else CRUISE_SMOOTHING_SECONDS)
        blend = 1.0 - math.exp(-dt / smoothing)
        self._velocity = tuple(old + (new - old) * blend for old, new in zip(previous, target))
        delta = tuple(new * dt + (old - new) * smoothing * blend for old, new in zip(previous, target))
        before = tuple(round(v) for v in self.position), self.visible
        self.move_to(self.position[0] + delta[0], self.position[1] + delta[1])
        # Accumulate subpixel movement without rebuilding an identical frame.
        return before != (tuple(round(v) for v in self.position), self.visible)

    @property
    def moving(self):
        return self._moving

    def _context_input(self, value, right_click):
        if right_click:
            return self._reset_right(), None
        position = _stick(value)
        if position is None:
            return self._reset_right(), None
        x, y = position
        magnitude = math.hypot(x, y)
        if magnitude <= CONTEXT_RELEASE:
            pending = self.context.highlight if self._right_sector is not None else None
            self._right_armed = True
            self._right_sector = None
            if pending is not None:
                return True, self.choose(pending)
            return False, None
        if not self._right_armed:
            return False, None
        if self._right_sector is None and magnitude < CONTEXT_ENGAGE:
            return False, None
        angle = math.atan2(y, x)
        sector = self._direction(angle)
        if self._right_sector is not None and sector != self._right_sector:
            center, half_width = self.context.sectors()[self._right_sector]
            delta = angle - center
            distance = abs(math.atan2(math.sin(delta), math.cos(delta)))
            if distance <= half_width + math.radians(ANGULAR_HYSTERESIS_DEGREES):
                sector = self._right_sector
        self._right_sector = sector
        highlight = sector
        changed = highlight != self.context.highlight
        self.context.highlight = highlight
        self.context.keyboard_choice = False
        return changed, None

    def update(self, left=None, right=None, generation=0, right_click=False, now=None):
        now = self.clock() if now is None else now
        if not _finite_number(now):
            return self.reset(), None
        changed = False
        if generation != self._generation or (self._last_now is not None and now < self._last_now):
            changed = self.reset()
            self._generation = generation
        elapsed = min(MAX_ELAPSED, max(0.0, now - self._last_now)) if self._last_now is not None else 0.0
        self._last_now = now
        # Slow frames must not silently discard held-stick time. Integrate in
        # bounded frame-sized steps so smoothing remains sample-rate independent,
        # while MAX_ELAPSED prevents a long suspend from causing a cursor jump.
        moved = False
        while elapsed > 0:
            dt = min(MAX_TIME_STEP, elapsed)
            moved = self._move(left, dt) or moved
            elapsed -= dt
        if elapsed == 0 and self._last_now == now and self._last_now is not None and not moved:
            # Preserve arming/reset behavior even when the first timestamp has no
            # elapsed interval.
            moved = self._move(left, 0.0)
        changed = moved or changed
        if moved and self.context is not None and self.context.keyboard_choice:
            self.context.keyboard_choice = False
            self.context.highlight = None
        if self.context is not None:
            # Pointer motion leaves the menu's opening center fixed. The host can
            # hit-test it for primary clicks independently of the right-stick cue.
            menu_changed, action = self._context_input(right, right_click)
            return changed or menu_changed, action
        self._reset_right()
        return changed, None
