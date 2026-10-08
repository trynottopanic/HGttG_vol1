"""Guide-owned browsing of storage-provider identities; never accepts paths."""
import os
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from guide_ui_model import Fact, MenuItem, ScreenModel, ActionHint

AUDIO_EXTENSIONS = {'.aac','.flac','.m4a','.mp3','.ogg','.opus','.wav'}
VIDEO_EXTENSIONS = {'.avi','.m4v','.mkv','.mov','.mp4','.mpeg','.mpg','.webm'}


class FilesPanel:
    DEFAULT_LOCATIONS = (
        dict(id='internal', name='Internal storage', available=True, writable=True),
        dict(id='external', name='External storage', available=True, writable=False),
    )

    def __init__(self, client=None, media_available=True):
        self.client = client or self.storage
        self.media_available = media_available
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.timings = None
        self.request_started = 0.0
        self.view = 'locations'
        self.listing = {'locations':[dict(row) for row in self.DEFAULT_LOCATIONS]}
        self.folder = None
        self.history = []
        self.location = None
        self.path = []
        self.offset = 0
        self.selected = None
        self.error = ''
        self.details_started = 0.0
        self.details_progress = 1.0

    @property
    def busy(self):
        return self.future is not None

    @property
    def at_root(self):
        return self.view == 'locations'

    @staticmethod
    def storage(op, args):
        for directory in ('/usr/lib/guideos/installer', '/usr/lib/guideos/ipc'):
            if directory not in sys.path:
                sys.path.insert(0, directory)
        from guide_install_wire import call
        deadline=time.monotonic()+11;args=dict(args)
        if op==2:args['async_listing']=True
        while True:
            result, descriptors = call('/run/guideos-storage/files.sock', op, args)
            for descriptor in descriptors:os.close(descriptor)
            if result.get('errorCode')!='listing-pending' or time.monotonic()>=deadline:break
            args.pop('refresh',None)
            time.sleep(.05)
        if 'errorCode' in result:
            raise ValueError(result['errorCode'].replace('-', ' '))
        return result

    def submit(self, kind, op, **args):
        if self.busy:
            return
        self.error = ''
        self.kind = kind
        self.future = self.pool.submit(self.client, op, args)
        self.request_started = time.monotonic()

    def open(self):
        self.view = 'locations'
        self.folder = None
        self.history = []
        self.location = None
        self.path = []
        self.offset = 0
        self.selected = None
        self.listing = {'locations':[dict(row) for row in self.DEFAULT_LOCATIONS]}
        self.submit('locations', 1)

    def poll(self):
        animated = False
        if self.view == 'details' and self.details_progress < 1.0:
            progress = min(1.0, max(0.0, (time.monotonic()-self.details_started)/.24))
            animated = abs(progress-self.details_progress) > .002
            self.details_progress = progress
        if not self.future or not self.future.done():
            return animated
        future = self.future
        self.future = None
        if self.timings and self.request_started:
            self.timings.add('file_request', time.monotonic()-self.request_started)
        self.request_started = 0.0
        try:
            self.listing = future.result()
        except Exception:
            self.error = 'Storage files are temporarily unavailable.'
            if self.kind == 'folder':
                self.view = 'locations'
                self.folder = None
                self.history = []
                self.listing = {'locations':[dict(row) for row in self.DEFAULT_LOCATIONS]}
        return True

    @property
    def animating(self):
        return self.view == 'details' and self.details_progress < 1.0

    def entry(self, identity):
        return next((row for row in self.listing.get('items', [])
                     if row.get('id') == identity), None)

    def show_details(self, entry, now=None):
        if not isinstance(entry, dict) or entry.get('kind') not in ('file','folder'):
            return False
        self.selected = dict(entry)
        self.view = 'details'
        self.details_started = time.monotonic() if now is None else now
        self.details_progress = 0.0
        return True

    def media_offer(self, entry):
        if (not self.media_available or self.location != 'external' or len(self.path) < 2 or
                [part.casefold() for part in self.path[:2]] != ['guide','media']):
            return None
        suffix=Path(entry.get('name','')).suffix.casefold()
        kind=1 if suffix in AUDIO_EXTENSIONS else 2 if suffix in VIDEO_EXTENSIONS else 0
        if not kind:return None
        return dict(kind=kind,title=entry['name'],folder='/'.join(self.path[2:]))

    def act(self, action, value=None):
        if self.busy:
            return
        if action == 'refresh':
            if self.view == 'locations':
                self.submit('locations', 1)
            elif self.folder:
                self.submit('folder', 2, folder=self.folder, offset=0, refresh=True)
                self.offset=0
        elif action == 'folder':
            if self.view == 'locations':
                next_location='internal' if value == 'internal' else 'external'
                next_path=[]
            else:
                row=self.entry(value)
                if row is None:return
                next_location=self.location
                next_path=self.path+[row['name']]
            self.history.append((self.folder, self.offset, self.location, tuple(self.path)))
            self.folder = value
            self.location = next_location
            self.path = next_path
            self.offset = 0
            self.view = 'folder'
            self.submit('folder', 2, folder=value, offset=0)
        elif action == 'page':
            self.offset = value
            self.submit('folder', 2, folder=self.folder, offset=value, revision=self.listing.get('revision'))
        elif action == 'details':
            self.show_details(value)
        elif action == 'more-details' and self.view == 'details':
            self.view = 'details-more'
        elif action == 'back':
            if self.view == 'details-more':
                self.view = 'details'
                self.details_progress = 1.0
            elif self.view == 'details':
                self.view = 'folder'
            elif self.view == 'folder' and self.history:
                self.folder, self.offset, self.location, path = self.history.pop()
                self.path=list(path)
                if self.folder is None:
                    self.view = 'locations'
                    self.submit('locations', 1)
                else:
                    self.submit('folder', 2, folder=self.folder, offset=self.offset)

    def model(self):
        notice = self.error or ('Working…' if self.busy else '')
        items = []
        if self.view == 'locations':
            title = 'Files'
            for location in self.listing.get('locations', []):
                items.append(MenuItem(location['id'], location['name'], 'folder', location['id'],
                                      enabled=bool(location.get('available'))))
            items.append(MenuItem('node-media', 'Node media  ·  Not connected', 'noop', enabled=False))
        elif self.view == 'folder':
            title = 'Folder'
            for entry in self.listing.get('items', []):
                offer=self.media_offer(entry) if entry['kind']=='file' else None
                action = 'folder' if entry['kind'] == 'folder' else 'play-media' if offer else 'details'
                value = entry['id'] if entry['kind'] == 'folder' else offer or entry
                items.append(MenuItem(entry['id'], entry['name'], action, value))
            if self.offset:
                items.append(MenuItem('previous', 'Previous page', 'page', max(0, self.offset - 32)))
            if self.listing.get('next') is not None:
                items.append(MenuItem('next', 'Next page', 'page', self.listing['next']))
            if not self.listing.get('items') and not self.busy:
                notice = notice or 'This folder is empty.'
            items.append(MenuItem('back', 'Back', 'back'))
        else:
            title = 'File Details'
            entry = self.selected or {}
            size = entry.get('size')
            kind=entry.get('kind','file')
            suffix=Path(entry.get('name','')).suffix
            stamp=lambda value:('Unavailable' if not value else datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M'))
            facts=(Fact('Name',entry.get('name','Unavailable')),
                   Fact('Folder','/'+('External card' if self.location=='external' else 'Internal storage')+('/'+'/'.join(self.path) if self.path else '/')),
                   Fact('Type','Folder' if kind=='folder' else 'File'),
                   Fact('Size','Not applicable' if kind=='folder' else ('Unknown' if size is None else f'{size:,} bytes')),
                   Fact('Extension','Not applicable' if kind=='folder' else ((entry.get('extension') or suffix[1:]) if suffix or entry.get('extension') else 'None')),
                   Fact('Created',stamp(entry.get('created'))),
                   Fact('Modified',stamp(entry.get('modified'))))
            back=ActionHint('B','Back','secondary','back','key',304)
            if self.view == 'details-more':
                return ScreenModel('deck-facts','More details',facts=facts,
                    items=(MenuItem('summary','Return to summary','back'),),
                    actions=(ActionHint('A','Return to summary','secondary','summary','back'),back))
            offer=self.media_offer(entry) if kind=='file' else None
            items.append(MenuItem('play','Play','play-media',offer,enabled=offer is not None))
            items.append(MenuItem('copy','Copy…','copy',{'entry':entry.get('id'),'name':entry.get('name')},enabled=kind=='file' and bool(entry.get('id'))))
            items.append(MenuItem('more-details','More details','more-details'))
            if not offer and not notice:
                notice=('Play is available for supported media in external Guide/Media.'
                        if self.media_available else 'Media playback is not installed in this build.')
            return ScreenModel(pattern='file-details',title=title,items=tuple(items),facts=facts,
                               notice=notice,transition=self.details_progress,actions=(back,))
        return ScreenModel(pattern='standard-menu', title=title, items=tuple(items), notice=notice)

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
