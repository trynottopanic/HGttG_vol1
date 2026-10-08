"""Executed unprivileged in an isolated systemd service before activation."""
import ast
from pathlib import Path
import sys

root = Path(sys.argv[1])
for path in root.rglob('*.py'):
    ast.parse(path.read_bytes(), filename=path.name)
sys.path.insert(0, str(root / 'shell0'))
import guide_shell
from guide_input import Keyboard, TextEntryManager, TextRequest, renderer

class Sink:
    def show(self, image):
        assert image.size == (640, 480)

state = guide_shell.ShellState()
guide_shell.Screen(Sink()).draw(state)
editor = Keyboard(TextEntryManager(), TextRequest('deployment-probe', 'text', 'Check'))
assert renderer().render(editor).size == (640, 480)
editor.close()
state.text_entries.teardown()
