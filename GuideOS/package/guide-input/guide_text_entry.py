"""Portable, owner-bound text editing for Guide's system input provider.

This module neither reads devices nor stores text. A renderer turns semantic
input into these editing actions; the shell retains global navigation and power
ownership. Cursor positions and limits count Unicode codepoints, not grapheme
clusters. Text is never normalized, including passwords.

Secret text is excluded from representations and cleared from session references
on completion. Python strings cannot promise secure memory erasure, and callers
remain responsible for the request/result strings they retain.
"""

from dataclasses import dataclass, field, replace
from typing import Optional
import unicodedata
import uuid


class TextValidationError(ValueError):
    """A request or edit violates its declared field contract."""


class TextOwnershipError(PermissionError):
    """An action does not belong to the current owner and focus generation."""


class TextEntryBusy(RuntimeError):
    """The current entry must finish and be consumed before opening another."""


def _nonnegative_int(value, name):
    if type(value) is not int or value < 0:
        raise TextValidationError(name + " must be a nonnegative integer.")


def _content_error(request, value, minimum=False):
    if not isinstance(value, str):
        return "Text must be a string."
    if len(value) > request.max_length:
        return "The character limit has been reached."
    if minimum and len(value) < request.min_length:
        return "Enter at least " + str(request.min_length) + " characters."
    for character in value:
        category = unicodedata.category(character)
        if category == "Cs":
            return "This text contains an unsupported character."
        if category == "Cc" and not (
                request.multiline and character in "\n\t"):
            return "Control characters are not allowed in this field."
        if not request.multiline and category in ("Zl", "Zp"):
            return "This field accepts one line of text."
        if (request.allowed_characters is not None and
                character not in request.allowed_characters):
            return "This character is not allowed in this field."
    if request.max_bytes is not None and len(value.encode("utf-8")) > request.max_bytes:
        return "The UTF-8 byte limit has been reached."
    return None


@dataclass(frozen=True)
class TextRequest:
    owner_id: str
    field_id: str
    label: str
    initial: str = field(default="", repr=False)
    purpose: str = "text"
    multiline: bool = False
    secret: bool = False
    min_length: int = 0
    max_length: int = 4096
    max_bytes: Optional[int] = None
    allowed_characters: Optional[str] = field(default=None, repr=False)
    submit_label: str = "Done"

    def __post_init__(self):
        for name in ("owner_id", "field_id", "label", "purpose", "submit_label"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise TextValidationError(name + " must be a nonempty string.")
            if any(unicodedata.category(c) in ("Cc", "Cs") for c in value):
                raise TextValidationError(name + " must not contain controls.")
        if type(self.multiline) is not bool or type(self.secret) is not bool:
            raise TextValidationError("Multiline and secret must be boolean.")
        _nonnegative_int(self.min_length, "Minimum length")
        _nonnegative_int(self.max_length, "Maximum length")
        if self.min_length > self.max_length:
            raise TextValidationError("Minimum length exceeds maximum length.")
        if self.max_bytes is not None:
            _nonnegative_int(self.max_bytes, "Maximum bytes")
        if self.allowed_characters is not None and not isinstance(self.allowed_characters, str):
            raise TextValidationError("Allowed characters must be a string or None.")
        error = _content_error(self, self.initial)
        if error:
            raise TextValidationError(error)


@dataclass(frozen=True)
class TextResult:
    owner_id: str
    field_id: str
    token: str
    state: str
    text: Optional[str] = field(repr=False)
    reason: Optional[str] = None
    cursor: Optional[int] = None


class TextSession:
    """One field and one focus generation, with a one-shot terminal result.

    Direct editing methods are for the trusted input provider. Application/input
    routing must use TextEntryManager's owner/token checks rather than sharing a
    session reference with another owner.
    """

    def __init__(self, request, token=None):
        if not isinstance(request, TextRequest):
            raise TextValidationError("A TextRequest is required.")
        if token is not None and (not isinstance(token, str) or not token):
            raise TextValidationError("The focus token must be a nonempty string.")
        self.request = replace(request, initial="")
        self.token = token if token is not None else uuid.uuid4().hex
        self._text = request.initial
        self._cursor = len(self._text)
        self._state = "editing"
        self._error = None
        self._pending = None

    def __repr__(self):
        return ("TextSession(owner_id={!r}, field_id={!r}, state={!r}, "
                "secret={!r}, length={})").format(
                    self.request.owner_id, self.request.field_id, self.state,
                    self.request.secret, len(self.text))

    @property
    def text(self):
        return self._text

    @property
    def cursor(self):
        return self._cursor

    @property
    def state(self):
        return self._state

    @property
    def error(self):
        return self._error

    def display_text(self):
        return "\u2022" * len(self.text) if self.request.secret else self.text

    def insert(self, text):
        if self.state != "editing":
            return False
        if not isinstance(text, str):
            self._error = "Text must be a string."
            return False
        candidate = self.text[:self.cursor] + text + self.text[self.cursor:]
        self._error = _content_error(self.request, candidate)
        if self.error:
            return False
        self._text = candidate
        self._cursor += len(text)
        return bool(text)

    def backspace(self):
        if self.state != "editing":
            return False
        self._error = None
        if self.cursor == 0:
            return False
        self._text = self.text[:self.cursor - 1] + self.text[self.cursor:]
        self._cursor -= 1
        return True

    def delete(self):
        if self.state != "editing":
            return False
        self._error = None
        if self.cursor == len(self.text):
            return False
        self._text = self.text[:self.cursor] + self.text[self.cursor + 1:]
        return True

    def move(self, offset):
        if type(offset) is not int:
            raise TextValidationError("Cursor movement must be an integer.")
        if self.state != "editing":
            return False
        self._error = None
        previous = self.cursor
        self._cursor = min(len(self.text), max(0, self.cursor + offset))
        return self.cursor != previous

    def home(self):
        return self.move(-self.cursor)

    def end(self):
        return self.move(len(self.text) - self.cursor)

    def _clear_text(self):
        self._text = ""
        self._cursor = 0
        self._error = None

    def submit(self):
        if self.state != "editing":
            return False
        self._error = _content_error(self.request, self.text, minimum=True)
        if self.error:
            return False
        self._state = "submitted"
        self._pending = TextResult(self.request.owner_id, self.request.field_id,
                                   self.token, self.state, self.text,cursor=self.cursor)
        self._clear_text()
        return True

    def cancel(self, reason="cancelled"):
        if not isinstance(reason, str) or not reason:
            raise TextValidationError("Cancellation needs a reason.")
        if self.state != "editing":
            return False
        self._state = "cancelled"
        self._pending = TextResult(self.request.owner_id, self.request.field_id,
                                   self.token, self.state, None, reason)
        self._clear_text()
        return True

    def _check_owner(self, owner_id, token):
        if owner_id != self.request.owner_id or token != self.token:
            raise TextOwnershipError("The text-entry owner or focus token is stale.")

    def take_result(self, owner_id, token):
        self._check_owner(owner_id, token)
        result = self._pending
        self._pending = None
        return result

    def teardown(self):
        """Discard an undelivered result and all text held by this session."""
        self._state = "cancelled"
        self._pending = None
        self._clear_text()


class TextEntryManager:
    """System-owned focus boundary for one portable text-entry session."""

    def __init__(self):
        self._active = None

    @property
    def active(self):
        return self._active

    def open(self, request):
        if self.active is not None:
            raise TextEntryBusy("Finish the current text entry before opening another.")
        self._active = TextSession(request)
        return self.active

    def _owned(self, owner_id, token):
        if self.active is None:
            raise TextOwnershipError("There is no active text-entry session.")
        self.active._check_owner(owner_id, token)
        return self.active

    def dispatch(self, owner_id, token, action, text=None):
        session = self._owned(owner_id, token)
        if action == "insert":
            return session.insert(text)
        if action == "left":
            return session.move(-1)
        if action == "right":
            return session.move(1)
        methods = {
            "backspace": session.backspace, "delete": session.delete,
            "home": session.home, "end": session.end,
            "submit": session.submit, "cancel": session.cancel,
        }
        if action not in methods:
            raise TextValidationError("Unknown text-entry action.")
        return methods[action]()

    def take_result(self, owner_id, token):
        session = self._owned(owner_id, token)
        result = session.take_result(owner_id, token)
        if session.state != "editing":
            self._active = None
        return result

    def cancel_owner(self, owner_id, reason="owner-exit"):
        """Release focus and return a cancellation without any draft text.

        Lifecycle cancellation also revokes a submitted but undelivered result.
        This prevents delivery into an owner that exited or lost its field.
        """
        session = self.active
        if session is None or session.request.owner_id != owner_id:
            return None
        session.teardown()
        self._active = None
        return TextResult(owner_id, session.request.field_id, session.token,
                          "cancelled", None, reason)

    def focus_lost(self, owner_id):
        return self.cancel_owner(owner_id, reason="focus-lost")

    def teardown(self):
        if self.active is not None:
            self.active.teardown()
            self._active = None
