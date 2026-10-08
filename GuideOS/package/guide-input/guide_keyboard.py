"""Reusable controller keyboard; device codes and drawing stay in adapters."""
from dataclasses import dataclass

from guide_text_entry import TextOwnershipError


@dataclass(frozen=True)
class Key:
    label: str
    action: str
    value: str = ''
    enabled: bool = True


class Keyboard:
    """A view of one host-owned text session, preserving the prototype layout."""
    CHARACTERS = (
        ('qwertyuiop', 'asdfghjkl', 'zxcvbnm,./', '1234567890'),
        ('QWERTYUIOP', 'ASDFGHJKL', 'ZXCVBNM,./', '1234567890'),
        ('1234567890', '.,?!:;\'"-_/', '@#$%&*+=\\|~', '()[]{}<>^`'),
    )

    def __init__(self, manager, request):
        self.manager = manager
        self.session = manager.open(request)
        self.page = 0
        self._letter_page = 0
        self.stick_highlight = None
        self.focus = (3, 0) if request.purpose == 'number' else (0, 0)
        self._repair_focus()

    @property
    def rows(self):
        request = self.session.request
        allowed = request.allowed_characters
        rows = [[Key(c, 'insert', c, allowed is None or c in allowed) for c in row]
                for row in self.CHARACTERS[self.page]]
        rows.append([Key('CASE', 'case'), Key('MORE', 'more'),
                     Key('SPACE', 'insert', ' ', allowed is None or ' ' in allowed),
                     Key('DEL', 'backspace'), Key(request.submit_label, 'submit'), Key('CANCEL', 'cancel')])
        rows.append([Key('HOME', 'home'), Key('LEFT', 'left'), Key('RIGHT', 'right'),
                     Key('END', 'end'), Key('DELETE', 'delete'),
                     Key('NEWLINE' if request.multiline else '', 'insert', '\n',
                         request.multiline and (allowed is None or '\n' in allowed))])
        return rows

    def _repair_focus(self):
        row, column = self.focus
        rows = self.rows
        if 0 <= row < len(rows) and 0 <= column < len(rows[row]) and rows[row][column].enabled:
            return
        self.focus = next((r, c) for r, keys in enumerate(rows) for c, key in enumerate(keys) if key.enabled)

    def _destination(self, focus, action):
        row, column = focus
        rows = self.rows
        step = -1 if action in ('up', 'left') else 1
        if action in ('left', 'right'):
            choices = [i for i, key in enumerate(rows[row]) if key.enabled]
            return row, choices[(choices.index(column) + step) % len(choices)]
        else:
            # Preserve the familiar prototype row/column traversal, skipping
            # disabled keys and empty rows for constrained fields.
            for distance in range(1, len(rows) + 1):
                target = (row + step * distance) % len(rows)
                choices = [i for i, key in enumerate(rows[target]) if key.enabled]
                if choices:
                    return target, min(choices, key=lambda i: abs(i - column))
        return focus

    def _move(self, action):
        self.focus = self._destination(self.focus, action)

    def _editing(self):
        if self.session.state != 'editing':
            return False
        if self.manager.active is not self.session:
            raise TextOwnershipError('The keyboard focus is no longer active.')
        return True

    @staticmethod
    def _direction(dx, dy):
        if any(type(value) is not int or value not in (-1, 0, 1) for value in (dx, dy)):
            raise ValueError('Keyboard direction components must be -1, 0 or 1.')
        return bool(dx or dy)

    def move_selection(self, dx, dy):
        """Move primary focus once, using established D-pad traversal.

        Diagonals resolve the vertical destination first, then its horizontal
        neighbor, and publish only the final focus. Hold timing belongs to the
        device-neutral stick adapter, not this keyboard model.
        """
        if not self._editing() or not self._direction(dx, dy):
            return False
        destination = self.focus
        if dy:
            destination = self._destination(destination, 'up' if dy < 0 else 'down')
        if dx:
            destination = self._destination(destination, 'left' if dx < 0 else 'right')
        changed = destination != self.focus
        self.focus = destination
        return changed

    def row_geometry(self, row, length):
        """Shared pitch/column count for drawing and directional selection.

        Short character rows leave empty columns at the right, never stagger.
        Action rows keep their wider controls and their own centered geometry.
        """
        if row < 4:
            return 56, max(map(len, self.CHARACTERS[self.page]))
        return 94, length

    def _key_center(self, row, column, length):
        pitch, columns = self.row_geometry(row, length)
        return (2 * column + 1 - columns) * pitch

    @property
    def neighbors(self):
        """Enabled immediate RS targets, with neither wrapping nor duplicates.

        Character rows use exact grid offsets, including empty edge columns.
        At wider action rows, N/S selects the nearest physical centre; ties go
        left. Disabled or missing immediate targets are omitted, not skipped.
        """
        if self.session.state != 'editing' or self.manager.active is not self.session:
            return {}
        rows = self.rows
        row, column = self.focus
        if not (0 <= row < len(rows) and 0 <= column < len(rows[row])):
            return {}
        center = self._key_center(row, column, len(rows[row]))
        neighbors = {}
        for dy in (-1, 0, 1):
            target_row = row + dy
            if not 0 <= target_row < len(rows):
                continue
            keys = rows[target_row]
            nearest = (column if dy == 0 or (row < 4 and target_row < 4) else min(range(len(keys)), key=lambda index:
                       (abs(self._key_center(target_row, index, len(keys)) - center), index)))
            for dx in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                target_column = nearest + dx
                if 0 <= target_column < len(keys) and keys[target_column].enabled:
                    neighbors[dx, dy] = target_row, target_column
        return neighbors

    def activate_neighbor(self, dx, dy):
        """Activate one marked key without changing primary focus."""
        if not self._editing() or not self._direction(dx, dy):
            return False
        target = self.neighbors.get((dx, dy))
        if target is None:
            return False
        return self._activate_key(self.rows[target[0]][target[1]])

    def _dispatch(self, action, text=None):
        request = self.session.request
        return self.manager.dispatch(request.owner_id, self.session.token, action, text)

    def _toggle_case(self):
        self.page = 0 if self.page == 1 else 1
        self._letter_page = self.page
        self._repair_focus()
        return True

    def _switch_layer(self):
        if self.page == 2:
            self.page = self._letter_page
        else:
            self._letter_page = self.page
            self.page = 2
        self._repair_focus()
        return True

    def _activate_key(self, key):
        if not key.enabled:
            return False
        if key.action == 'case':
            return self._toggle_case()
        if key.action == 'more':
            return self._switch_layer()
        self._dispatch(key.action, key.value if key.action == 'insert' else None)
        return True  # Failed validation still redraws its safe error message.

    def handle(self, action, value=1, text=None):
        """Process a fresh semantic press; release/repeat never types or submits."""
        if value != 1 or not self._editing():
            return False
        if action in ('up', 'down', 'left', 'right'):
            self._move(action)
            return True
        if action == 'case':
            return self._toggle_case()
        if action in ('previous-layer', 'next-layer'):
            return self._switch_layer()
        if action == 'activate':
            key = self.rows[self.focus[0]][self.focus[1]]
            return self._activate_key(key)
        if action in ('cancel', 'backspace', 'delete', 'home', 'end', 'submit'):
            self._dispatch(action)
            return True
        if action in ('space', 'insert'):
            self._dispatch('insert', ' ' if action == 'space' else text)
            return True
        return False

    def take_result(self):
        return self.manager.take_result(self.session.request.owner_id, self.session.token)

    def close(self, reason='owner-exit'):
        # Token check prevents an obsolete view from cancelling its owner's newer field.
        if self.manager.active is self.session:
            self.manager.cancel_owner(self.session.request.owner_id, reason)
        else:
            self.session.teardown()
