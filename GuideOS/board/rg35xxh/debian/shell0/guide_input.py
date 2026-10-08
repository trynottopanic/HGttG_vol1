"""Debian/working-tree import adapter for the shared Guide text-input library."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
candidates = [HERE.parent / 'input']
if len(HERE.parents) > 3:
    candidates.append(HERE.parents[3] / 'package' / 'guide-input')
for candidate in candidates:
    if (candidate / 'guide_text_entry.py').is_file():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

from guide_text_entry import TextEntryManager, TextRequest
from guide_keyboard import Keyboard
from guide_stick_input import StickController
from guide_pointer_input import PointerController

# RG35XX H ordinary controls, verified board profile. No Start, Power or Reset.
KEYBOARD_ACTIONS = {544:'up', 545:'down', 546:'left', 547:'right',
                    305:'activate', 304:'cancel', 307:'space', 308:'backspace',
                    317:'case', 318:'activate', 310:'previous-layer', 311:'next-layer'}


def renderer():
    from guide_keyboard_view import KeyboardRenderer
    return KeyboardRenderer()


def draw_menu_pointer(image, pointer, fonts, hover=None):
    from guide_pointer_view import draw_pointer
    draw_pointer(image, pointer, fonts, hover=hover)
