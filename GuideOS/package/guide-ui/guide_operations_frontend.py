"""Thin page/input adapter for the consolidated Home frontend."""
from dataclasses import replace

from guide_files_panel import FilesPanel
from guide_updates_panel import UpdatesPanel
from guide_transfers_panel import TransfersPanel


class OperationsPages:
    def __init__(self, updates=None, transfers=None, files=None):
        self.pages = {
            'updates': updates or UpdatesPanel(),
            'transfers': transfers or TransfersPanel(),
            'files': files or FilesPanel(),
        }
        self.current = None
        self.focus = {}

    def open(self, page):
        if page not in self.pages:
            raise ValueError('Unknown operations page')
        self.current = page
        panel = self.pages[page]
        if hasattr(panel, 'next_poll'):
            panel.next_poll = 0
        if page == 'files':
            panel.open()

    def copy(self, entry, name):
        if not entry or not name:
            raise ValueError('A current opaque file identity is required')
        self.open('transfers')
        self.pages['transfers'].offer_copy(entry, name)

    def poll(self):
        # Complete update jobs even after leaving Updates. A completed future
        # must not linger as a supposed display owner on another page.
        changed=self.pages['updates'].poll()
        if self.current and self.current!='updates':
            changed=self.pages[self.current].poll() or changed
        return changed

    @property
    def animating(self):
        return bool(self.current and getattr(self.pages[self.current],'animating',False))

    def details(self, identity=None):
        if self.current != 'files':return False
        identity=identity or self.model().focus_id
        return self.pages['files'].show_details(self.pages['files'].entry(identity))

    def model(self):
        model = self.pages[self.current].model()
        ids = [item.identity for item in model.items if item.enabled]
        focus = self.focus.get(self.current)
        if focus not in ids:
            focus = ids[0] if ids else None
        self.focus[self.current] = focus
        return replace(model, focus_id=focus)

    def move(self, delta):
        model = self.model()
        ids = [item.identity for item in model.items if item.enabled]
        if ids:
            self.focus[self.current] = ids[(ids.index(model.focus_id) + delta) % len(ids)]

    def activate(self, identity=None):
        model = self.model()
        identity = identity or model.focus_id
        item = next((row for row in model.items if row.identity == identity), None)
        if not item or not item.enabled:
            return self.current
        if self.current == 'files' and item.action == 'open-transfers':
            self.open('transfers')
        elif self.current == 'files' and item.action == 'copy':
            self.copy(item.value['entry'], item.value['name'])
        elif item.action != 'noop':
            before=getattr(self.pages[self.current],'view',None)
            self.pages[self.current].act(item.action, item.value)
            if self.current=='files' and before=='details' and self.pages['files'].view=='folder':
                self.focus['files']=(self.pages['files'].selected or {}).get('id')
            elif self.current=='files' and before=='details-more' and self.pages['files'].view=='details':
                self.focus['files']='more-details'
        return self.current

    def back(self):
        panel = self.pages[self.current]
        at_root = ((self.current == 'updates' and panel.view == 'overview') or
                   (self.current == 'transfers' and panel.view == 'jobs') or
                   (self.current == 'files' and panel.at_root))
        if at_root:
            self.current = None
            return 'home'
        before=getattr(panel,'view',None)
        panel.act('back')
        if self.current=='files' and before=='details' and panel.view=='folder':
            self.focus['files']=(panel.selected or {}).get('id')
        elif self.current=='files' and before=='details-more' and panel.view=='details':
            self.focus['files']='more-details'
        return self.current

    def close(self):
        for panel in self.pages.values():
            panel.close()
