"""Pure adapters from current shell values to Guide UI semantic models."""

from __future__ import annotations

from guide_ui_model import ActionHint, Fact, MenuItem, ScreenModel, UIError


HOME_PAGE_SIZE = 10


def home_model(pages, choices, selection, battery_percent=None):
    if len(pages) != len(choices) or not pages:
        raise UIError("home pages and choices must be nonempty and parallel")
    if not 0 <= selection < len(pages):
        raise UIError("home selection out of range")
    items = tuple(MenuItem("home:" + page, str(label), "home", index)
                  for index, (page, label) in enumerate(zip(pages, choices)))
    return ScreenModel(
        pattern="standard-menu",
        title="Home",
        battery_percent=battery_percent,
        items=items,
        focus_id=items[selection].identity,
        actions=(ActionHint("+", "Move", "ink"),
                 ActionHint("A", "Open", "green"),
                 ActionHint("B", "Back", "rust")),
    )


def status_model(rows, battery_percent=None, audio_test_label=None):
    bounded = tuple(str(row) for row in rows)
    if not bounded:
        bounded = ("Status unavailable",)
    if len(bounded) > 9:
        bounded = bounded[:9]
    facts = []
    for index, row in enumerate(bounded):
        label, separator, value = row.partition(":")
        facts.append(Fact(label.strip() if separator else "System",
                          value.strip() if separator else label.strip(),
                          "success" if index == 0 else "neutral"))
    return ScreenModel(
        pattern="facts-status",
        title="System Status",
        battery_percent=battery_percent,
        facts=tuple(facts),
        actions=((ActionHint("A", audio_test_label, "green", "status:audio-test", "key", 305),) if audio_test_label else ()) + (ActionHint("B", "Back", "rust", "back", "key", 304),
                 ActionHint("Menu", "Home", "blue", "home", "key", 316)),
    )
