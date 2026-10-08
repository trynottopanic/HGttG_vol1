"""Menu hit targets and shell-owned pointer/context actions.

Targets use stable identities, so a Wi-Fi refresh cannot redirect an already
opened context menu to a different network. Keyboard input bypasses this adapter.
"""
from dataclasses import dataclass
import time

from guide_input import PointerController
from guide_pointer_input import CONTEXT_MARGIN

UP, DOWN, LEFT, RIGHT, A, B, SELECT, MENU = 544, 545, 546, 547, 305, 304, 314, 316
SELECT_KEYS = (SELECT, 315, MENU)
DIRECTIONS = {UP: 'up', DOWN: 'down', LEFT: 'left', RIGHT: 'right'}


@dataclass(frozen=True)
class Target:
    identity: str
    label: str
    rect: tuple
    action: str
    value: object = None


class MenuInput:
    def __init__(self, state):
        self.state = state
        self.pointer = PointerController()
        self.context_target = None
        self.context_scope = None
        self.context_options = None
        self.focus_anchor = None
        self.pointer_active = False
        self.sync_focus()

    def scope(self):
        panel = self.state.wifi_panel
        audio = getattr(self.state, 'audio_panel', None)
        if self.state.page == 'nodes':
            return (self.state.page, self.state.nodes_panel.view)
        if self.state.page in ('media','audio') and audio:
            return (self.state.page, audio.view)
        operations = getattr(self.state, 'operations', None)
        if operations and self.state.page in operations.pages:
            panel = operations.pages[self.state.page]
            return (self.state.page, getattr(panel, 'view', None),
                    getattr(panel, 'folder', None))
        return (self.state.page,
                panel.view if self.state.page == 'wifi' and panel else None,
                panel.target if self.state.page == 'wifi' and panel else None)

    def targets(self):
        state = self.state
        provider = getattr(state,'schema_target_provider',None)
        if provider is not None:
            regions=provider()
            if regions is not None:
                return [Target(r.identity,r.label,r.rect.tuple(),r.action,r.value) for r in regions]
        if state.page == 'home':
            step, height = (55, 46) if len(state.pages) > 4 else (65, 52)
            return [Target('home:' + page, label, (20, 124+i*step, 620, 124+i*step+height),
                           'home', i)
                    for i, (page, label) in enumerate(zip(state.pages, state.choices))]
        if state.page == 'status' and getattr(state, 'audio_panel', None):
            return [Target('status:audio-test', 'Audio test', (395,413,620,449), 'key', A),
                    Target('back', 'Back', (544,87,620,118), 'key', B)]
        if state.page == 'power':
            return [Target('power:confirm', 'Confirm', (20, 288, 300, 341), 'key', A),
                    Target('power:cancel', 'Cancel', (320, 288, 620, 341), 'key', B)]
        if state.page in ('media','audio') and getattr(state, 'audio_panel', None):
            panel = state.audio_panel
            rows = panel.rows()
            start = max(0, min(panel.cursor - 2, len(rows) - 5))
            return [Target('audio:' + identity, label, (20, 155+(i-start)*44, 620, 194+(i-start)*44),
                           'audio-row', identity) for i, (identity, label) in enumerate(rows) if start <= i < start+5] + [
                           Target('back', 'Back', (544, 87, 620, 118), 'key', B)]
        if state.page == 'wifi':
            panel = state.wifi_panel
            if not panel:
                return [Target('wifi:scan', 'Rescan', (20, 408, 220, 442), 'key', A),
                        Target('back', 'Back', (544, 87, 620, 118), 'key', B)]
            if panel.editor is not None:
                return []
            if panel.view == 'list':
                rows = panel.rows()
                start = max(0, min(panel.cursor - 2, len(rows) - 5))
                result = [Target('wifi:row:' + identity, 'Open', (20, 155+(i-start)*44, 620, 194+(i-start)*44),
                                 'wifi-row', identity)
                          for i, (identity, _label) in enumerate(rows)
                          if start <= i < start + 5]
                return result + [Target('back', 'Back', (544, 87, 620, 118), 'key', B)]
            if panel.view == 'detail':
                row = panel.selected()
                result = []
                if row:
                    result.append(Target(('wifi:disconnect:' if row['active'] else 'wifi:connect:') + panel.target,
                                         'Disconnect' if row['active'] else 'Connect',
                                         (20, 258, 620, 297), 'wifi-detail', 0))
                    if row['saved']:
                        result.append(Target('wifi:forget:' + panel.target, 'Forget',
                                             (20, 304, 620, 343), 'wifi-detail', 1))
                return result + [Target('back', 'Back', (544, 87, 620, 118), 'key', B)]
            if panel.view == 'forget':
                return [Target('wifi:confirm-forget:' + str(panel.target), 'Forget',
                               (20, 355, 300, 398), 'key', A),
                        Target('back', 'Cancel', (320, 355, 620, 398), 'key', B)]
            if panel.view == 'working':
                label = 'Cancel' if panel.status.get('busy') or panel.pending_token else 'Back'
                return [Target('back', label, (544, 87, 620, 118), 'key', B)]
        return [Target('back', 'Back', (544, 87, 620, 118), 'key', B)]

    def hovered(self):
        x, y = self.pointer.position
        return next((target for target in self.targets()
                     if target.rect[0] <= x <= target.rect[2] and
                     target.rect[1] <= y <= target.rect[3]), None)

    def focus_target(self):
        state = self.state
        candidates = self.targets()
        if not candidates:
            return None
        if state.page == 'status' and getattr(state, 'audio_panel', None):
            return candidates[state.status_selection % len(candidates)]
        if state.page == 'home':
            home = state.v3_home
            identity = ('v3-world' if home.world_active else 'v3-tray:' + 'ABCD'[home.tray_focus] if home.tray_extended and home.tray_active
                        else 'v3-wheel:' + home.visible[home.wheel_focus])
        elif state.page == 'settings':
            from guide_v3_ui import SETTINGS
            identity = 'settings:' + SETTINGS[state.settings_selection % len(SETTINGS)][0]
        elif state.page == 'power':
            identity = ('power:confirm', 'power:cancel')[state.power_selection]
        elif state.page == 'installer' and getattr(state,'installer_panel',None):
            identity='installer:'+str(state.installer_panel.cursor)
        elif state.page == 'application' and getattr(state,'application_panel',None):
            identity='application:'+str(state.application_panel.cursor)
        elif state.page == 'find':
            identity=state.quick_find.model().focus_id
        elif state.page in ('media','audio') and getattr(state, 'audio_panel', None):
            panel = state.audio_panel
            identity = 'audio:' + panel.rows()[panel.cursor][0]
        elif state.page == 'nodes':
            identity = state.nodes_panel.model().focus_id
            # A stale or disabled row must not turn into the header's Back action.
            return next((target for target in candidates if target.identity == identity), None)
        elif state.page == 'nearby':
            identity = state.nearby_panel.model().focus_id
        elif state.operations and state.page in state.operations.pages:
            identity = state.operations.model().focus_id
            if identity is None:
                return candidates[0]
        elif state.page == 'wifi' and state.wifi_panel:
            panel = state.wifi_panel
            if panel.view == 'list':
                identity = 'wifi:row:' + panel.rows()[min(panel.cursor, len(panel.rows())-1)][0]
            elif panel.view == 'detail':
                row = panel.selected()
                prefix = ('wifi:forget:' if panel.detail_cursor else
                          'wifi:disconnect:' if row and row['active'] else 'wifi:connect:')
                identity = prefix + str(panel.target)
            else:
                return candidates[0]
        else:
            return candidates[0]
        return next((target for target in candidates if target.identity == identity), candidates[0])

    def turn_home_page(self, code):
        from guide_shell_schema_adapter import HOME_PAGE_SIZE
        state = self.state
        page, slot = divmod(state.selection, HOME_PAGE_SIZE)
        last = (len(state.pages)-1)//HOME_PAGE_SIZE
        destination = max(0, min(last, page + (-1 if code == 312 else 1)))
        if destination == page:
            return False
        if state.home_slide_enabled:
            state.home_slide = (state.selection, -1 if code == 312 else 1, time.monotonic())
            state.home_slide_progress = 0.0
        state.selection = min(destination*HOME_PAGE_SIZE+slot, len(state.pages)-1)
        self.sync_focus()
        return True

    def move_spatial(self, code):
        """Use the same displayed regions as pointer hit testing; do not wrap."""
        current = self.focus_target()
        if current is None:
            return False
        horizontal = code in (LEFT, RIGHT)
        axis, cross = (0, 1) if horizontal else (1, 0)
        sign = 1 if code in (RIGHT, DOWN) else -1
        center = lambda t: ((t.rect[0]+t.rect[2])/2, (t.rect[1]+t.rect[3])/2)
        origin = center(current)
        options = []
        for target in self.targets():
            point = center(target)
            forward = (point[axis]-origin[axis])*sign
            if forward <= 0:
                continue
            # Keep movement in the displayed row/column; blank cells do not wrap.
            overlap = (min(current.rect[cross+2], target.rect[cross+2]) >
                       max(current.rect[cross], target.rect[cross]))
            if overlap:
                options.append(((forward, abs(point[cross]-origin[cross])), target))
        if not options:
            return False
        target = min(options, key=lambda item: item[0])[1]
        if self.state.page == 'home':
            self.state.selection = self.state.pages.index(target.identity[5:])
        elif self.state.page == 'settings':
            from guide_v3_ui import SETTINGS
            self.state.settings_selection = [row[0] for row in SETTINGS].index(target.value)
        else:
            state=self.state
            if state.page == 'power':state.power_selection = int(target.identity == 'power:cancel')
            elif state.operations and state.page in state.operations.pages:
                state.operations.focus[state.page]=target.identity
            elif state.page == 'installer' and getattr(state,'installer_panel',None):
                state.installer_panel.cursor=int(target.value)
            elif state.page == 'application' and getattr(state,'application_panel',None):
                state.application_panel.cursor=int(target.value)
            elif state.page == 'find':
                state.quick_find.cursor=next(i for i,row in enumerate(state.quick_find.rows()) if row.identity==target.identity)
            elif state.page in ('media','audio') and getattr(state,'audio_panel',None):
                rows=state.audio_panel.rows();state.audio_panel.cursor=next(i for i,row in enumerate(rows) if row[0]==target.value)
            elif state.page == 'nodes' and target.action == 'nodes-row':
                state.nodes_panel.cursor=next(i for i,row in enumerate(state.nodes_panel.model().items) if row.identity==target.identity)
            elif state.page == 'nearby' and target.action == 'nearby-row':
                state.nearby_panel.cursor=next(i for i,row in enumerate(state.nearby_panel.rows()) if row[0]==target.value)
            elif state.page == 'wifi' and state.wifi_panel and target.identity.startswith('wifi:row:'):
                rows=state.wifi_panel.rows();state.wifi_panel.cursor=next(i for i,row in enumerate(rows) if row[0]==target.value)
            elif state.page == 'status':
                state.status_selection=self.targets().index(target)
            else:return False
        self.sync_focus()
        return True

    def grid_layout(self):
        """Recognize the rendered two-column card layout from its hit regions."""
        if (self.state.page=='media' and getattr(self.state,'audio_panel',None) and
                self.state.audio_panel.view in ('library','music','video')):return False
        targets=self.targets()
        for index,first in enumerate(targets):
            for second in targets[index+1:]:
                vertical=min(first.rect[3],second.rect[3])-max(first.rect[1],second.rect[1])
                separated=first.rect[2] <= second.rect[0] or second.rect[2] <= first.rect[0]
                if vertical>0 and separated:return True
        return False

    def sync_focus(self, allow_cancel=False):
        """Synchronize action focus without relocating the independent cursor."""
        self.pointer.close_context()
        self.pointer.reset()
        self.context_target = None
        self.context_scope = None
        self.focus_anchor = None
        self.pointer_active = False

    def refresh_targets(self):
        """Follow stable D-pad focus, but never drag a freely moved mouse."""
        if self.pointer.context is not None:
            available = {target.identity for target in self.targets()}
            if (self.context_scope != self.scope() or
                    (self.context_target is not None and self.context_target not in available) or
                    self.context_options != self.options_for(self.context_target)):
                self.pointer.close_context()
                self.context_target = self.context_scope = None
                return True
            return False
        return False

    def activate(self, identity):
        target = next((row for row in self.targets() if row.identity == identity), None)
        if target is None:
            return False
        state = self.state
        if target.action == 'nearby-row':
            changed=state.nearby_panel.activate(target.value)
        elif target.action == 'key':
            changed = (state.key(target.value, 1) if target.value in (B, MENU)
                       else state._key(target.value, 1))
        elif state.operations and state.page in state.operations.pages:
            state.operations.focus[state.page] = target.identity
            if target.action == 'play-media':
                if not callable(getattr(state.audio_panel,'open_path',None)):
                    changed=state.show_unavailable('Media playback is not installed in this build.')
                else:
                    changed=state.audio_panel.open_path(target.value)
                    if changed:
                        panel=state.operations.pages['files']
                        if panel.view=='details':
                            panel.act('back')
                            state.operations.focus['files']=(panel.selected or {}).get('id')
                        state.enter_page('media')
            else:
                state.page = state.operations.activate(target.identity) or 'home'
                changed = True
            state.revision += 1
        elif target.action == 'installer-action':
            state.installer_panel.cursor=target.value
            changed=state.installer_panel.action(target.value);state.revision+=1
        elif target.action == 'application-action':
            state.application_panel.cursor=target.value
            changed=state.application_panel.action(target.value);state.revision+=1
        elif target.action == 'find-action':
            state.quick_find.cursor=next(i for i,row in enumerate(state.quick_find.rows()) if row.identity==target.identity)
            state.quick_find.activate(target.value);state.revision+=1;changed=True
        elif target.action == 'home':
            state.selection = target.value
            if state.pages[state.selection] == 'power':
                state.power_selection = 0
            changed = state._key(A, 1)
        elif target.action == 'v3-destination':
            changed = state.open_v3_destination(target.value)
        elif target.action == 'v3-setting':
            changed = state.open_v3_setting(target.value)
        elif target.action == 'v3-shortcut':
            from guide_v3_ui import TRAY_DESTINATIONS
            state.v3_home.tray_focus = int(target.value)
            changed = state.open_v3_destination(TRAY_DESTINATIONS[state.v3_home.tray_focus])
        elif target.action == 'audio-row':
            changed = state.audio_panel.activate(target.value)
            state.revision += 1
        elif target.action == 'nodes-row':
            if self.state.nodes_panel.pending is not None:return False
            self.state.nodes_panel.cursor=next((i for i,row in enumerate(self.state.nodes_panel.model().items) if row.identity==target.identity),0)
            self.state.nodes_panel.action(target.value)
            self.state.revision+=1;changed=True
        elif target.action == 'wifi-row':
            rows = state.wifi_panel.rows()
            cursor = next((i for i, row in enumerate(rows) if row[0] == target.value),None)
            if cursor is None:
                self.sync_focus();state.revision+=1
                return False
            state.wifi_panel.cursor = cursor
            changed = state._key(A, 1)
        elif target.action == 'wifi-detail':
            panel=state.wifi_panel;row=panel.selected()
            expected=(('wifi:forget:' if target.value else
                       'wifi:disconnect:' if row and row['active'] else 'wifi:connect:')+str(panel.target))
            if row is None or target.identity!=expected:
                self.sync_focus();state.revision+=1
                return False
            state.wifi_panel.detail_cursor = target.value
            changed = state._key(A, 1)
        else:
            changed = state._key(target.value, 1)
        if changed:
            self.sync_focus()
        return changed

    def context_action(self, action):
        target, scope = self.context_target, self.context_scope
        self.context_target = self.context_scope = None
        if scope != self.scope():
            return False
        options = self.options_for(target)
        allowed = options.values() if isinstance(options, dict) else options
        if action not in {option['id'] for option in allowed}:
            return False
        if action == 'select':
            return self.activate(target)
        if action.startswith('network:'):
            _, verb, identity = action.split(':', 2)
            panel = self.state.wifi_panel
            panel.target = identity
            panel.view = 'detail'
            panel.detail_cursor = 1 if verb == 'forget' else 0
            self.state._key(A, 1)
            self.sync_focus()
            return True
        if action in ('back', 'home'):
            self.state._key(B if action == 'back' else MENU, 1)
            self.sync_focus()
        return True

    def options_for(self, identity):
        """Derive relevant actions from current state, never from old labels."""
        target = next((row for row in self.targets() if row.identity == identity), None)
        options = {'left': dict(id='close', label='Close menu')}
        extras = []
        if target and target.identity != 'back':
            options['up'] = dict(id='select', label=target.label)
        if self.state.page != 'home':
            options['right'] = dict(id='back', label='Back')
            options['down'] = dict(id='home', label='Home')
        panel = self.state.wifi_panel if self.state.page == 'wifi' else None
        audio = getattr(self.state, 'audio_panel', None)
        if (self.state.page == 'status' or
                (self.state.page == 'media' and (not audio or audio.view == 'player')) or
                (panel and panel.view == 'list')):
            options.pop('right', None)  # Back and Home have the same destination.
        if self.state.page == 'power':
            options.pop('down', None)
            options['right']['label'] = 'Cancel'
            if target and target.identity == 'power:cancel':
                options.pop('up', None)
        if self.state.page == 'wifi' and not panel and self.state.wifi['state'] == 'scanning':
            options.pop('up', None)
        if panel:
            busy = bool(panel.status.get('busy') or panel.pending_token)
            if panel.view == 'working' and busy:
                options['right']['label'] = 'Cancel task'
            row = None
            if target and target.action == 'wifi-row':
                row = next((row for row in panel.status['networks'] if row['id'] == target.value), None)
                if target.value == 'scan':
                    options['up']['label'] = 'Rescan'
                elif target.value == 'disconnect':
                    options['up']['label'] = 'Disconnect' if panel.status.get('connected') else 'Pause reconnect'
                    if panel.status.get('hold') and not panel.status.get('connected'):
                        options.pop('up', None)
            elif panel.view == 'detail':
                row = panel.selected()
            if busy and panel.view in ('list', 'detail', 'forget'):
                options.pop('up', None)
            elif row:
                available = bool(row['available'] and row['supported'])
                if target and target.action == 'wifi-detail' and target.value == 0 and not available:
                    options.pop('up', None)
                if available and not (target and target.action == 'wifi-detail' and target.value == 0):
                    verb = 'disconnect' if row['active'] else 'connect'
                    extras.append(dict(id='network:' + verb + ':' + row['id'], label=verb.title()))
                if row['saved'] and not (target and target.action == 'wifi-detail' and target.value == 1):
                    extras.append(dict(id='network:forget:' + row['id'], label='Forget'))
            if panel.view == 'forget' and (not panel.selected() or not panel.selected()['saved']):
                options.pop('up', None)
        # Keep familiar cardinal positions for small menus. Larger menus use
        # evenly spaced sectors, with overflow pages supplied by the model.
        if len(options) + len(extras) > 4:
            return ([options['up']] if 'up' in options else []) + extras + [
                options[slot] for slot in ('right', 'down', 'left') if slot in options]
        for extra in extras[:]:
            free = next((slot for slot in ('up', 'right', 'down', 'left') if slot not in options), None)
            if free is None:
                break
            options[free] = extra
            extras.remove(extra)
        return options

    def open_context(self):
        target = self.hovered()
        self.context_target = target.identity if target else None
        self.context_scope = self.scope()
        options = self.options_for(self.context_target)
        self.context_options = options
        x, y = self.pointer.position
        # Reserve the shell's control-hint strip below y=454 for every popup.
        self.pointer.open_context(options, center=(x, min(y, 454 - CONTEXT_MARGIN)))
        return True

    def key(self, code):
        pointer = self.pointer
        if self.state.page=='application' and self.state.application_panel:
            meta=self.state.application_panel.presentation()
            binding={305:0,307:1,308:2,304:3}.get(code)
            if binding in meta.get(5,{}) or (meta.get(0)=='document' and code in DIRECTIONS):
                pointer.close_context()
                return self.state._key(code,1)
        files_panel = (self.state.operations.pages['files']
                       if self.state.operations and self.state.page == 'files' else None)
        menu_is_select = (code == MENU and
                          (self.state.page == 'home' or
                           (files_panel is not None and files_panel.view == 'folder')))
        if pointer.context is None and code in DIRECTIONS:
            self.pointer_active = False
        if code == MENU and not menu_is_select:
            pointer.close_context()
            changed = self.state._key(code, 1)
            self.sync_focus()
            return changed
        if self.state.page == 'home' and pointer.context is None:
            home = self.state.v3_home
            if code in SELECT_KEYS:
                home.world_active = False
                changed = home.toggle_tray()
            elif code == 318:
                return False
            elif code in (312, 313):
                home.world_active = False
                changed = home.scroll(-1 if code == 312 else 1)
            elif home.world_active and code in DIRECTIONS:
                home.world_active=False
                home.tray_active=home.tray_extended and code!=RIGHT
                home.wheel_focus=0;changed=True
            elif code == UP and (home.tray_active or home.wheel_focus==0):
                home.world_active=True;home.cancel_wheel();changed=True
            elif home.tray_extended and code in (LEFT, RIGHT):
                home.tray_active = True
                home.tray_focus = max(0, min(3, home.tray_focus + (-1 if code == LEFT else 1)))
                changed = True
            elif home.tray_extended and code == B:
                home.tray_extended = False;changed = True
            elif code in (UP, DOWN):
                home.tray_active = False
                home.wheel_focus = max(0, min(2, home.wheel_focus + (-1 if code == UP else 1)))
                changed = True
            elif code in (A, 317):
                target = self.hovered() if self.pointer_active else self.focus_target()
                changed = self.activate(target.identity) if target else False
            else:
                return False
            if changed:self.sync_focus();self.state.revision += 1
            return changed
        if self.state.page == 'settings' and pointer.context is None and code in DIRECTIONS:
            from guide_v3_ui import SETTINGS
            count = len(SETTINGS)
            before = self.state.settings_selection
            if code == LEFT and before % 2:self.state.settings_selection -= 1
            elif code == RIGHT and not before % 2 and before + 1 < count:self.state.settings_selection += 1
            elif code == UP and before >= 2:self.state.settings_selection -= 2
            elif code == DOWN and before + 2 < count:self.state.settings_selection += 2
            changed = before != self.state.settings_selection
            if changed:self.sync_focus();self.state.revision += 1
            return changed
        if pointer.context is not None:
            if code in (B, 308, 318):
                pointer.close_context()
                self.context_target = self.context_scope = None
                return True
            direction = DIRECTIONS.get(code)
            if direction is not None and pointer.context.items:
                return pointer.step_choice(-1 if code in (UP, LEFT) else 1)
            if code in (A, 317):
                direction = (pointer.context.highlight if code == A and pointer.context.keyboard_choice
                             else pointer.direction_at(*pointer.position))
            if direction is not None:
                before_page = pointer.context.page
                action = pointer.choose(direction)
                if action is not None:
                    self.context_action(action)
                    return True  # popup closed even if a stale target was rejected
                return pointer.context is not None and pointer.context.page != before_page
            return False
        if code in SELECT_KEYS and self.state.page == 'files' and self.state.operations:
            target = self.hovered() if self.pointer_active else self.focus_target()
            changed = self.state.operations.details(target.identity if target else None)
            if changed:self.sync_focus()
            return changed
        if code in DIRECTIONS and self.grid_layout():
            return self.move_spatial(code)
        if code in (A, 317):
            target = self.hovered() if self.pointer_active else self.focus_target()
            return self.activate(target.identity) if target else False
        if code in (308, 318):
            return self.open_context()
        changed = self.state._key(code, 1)
        if changed:
            self.sync_focus(allow_cancel=code in DIRECTIONS)
        return changed

    def update(self, sample, now=None):
        if self.state.page == 'home':
            previous_position = self.pointer.position
            pointer_changed, _ = self.pointer.update(
                left=sample.get('left'), right=None,
                generation=sample.get('generation', 0), right_click=False, now=now)
            if self.pointer.position != previous_position:
                self.focus_anchor = None;self.pointer_active = True
            home_changed, destination = self.state.v3_home.update(sample, now=now)
            if destination is not None:self.state.open_v3_destination(destination)
            return pointer_changed or home_changed or destination is not None
        if self.pointer.context is not None and self.context_scope != self.scope():
            self.sync_focus()
            return True
        previous_position = self.pointer.position
        changed, action = self.pointer.update(
            left=sample.get('left'), right=sample.get('right'),
            generation=sample.get('generation', 0),
            right_click=bool(sample.get('right_click')), now=now)
        if self.pointer.position != previous_position:
            self.focus_anchor = None;self.pointer_active = True
        if action is not None:
            changed = self.context_action(action) or changed
        return changed
