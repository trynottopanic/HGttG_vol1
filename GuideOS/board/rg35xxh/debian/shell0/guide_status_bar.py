"""Shared, read-only status chrome for the shell and resident overlay."""
from datetime import datetime
from math import ceil
import json
from pathlib import Path
import time

HEIGHT = 28


class StatusBar:
    def __init__(self, sys_root='/sys', run_root='/run', clock=datetime.now,
                 monotonic=time.monotonic):
        self.sys, self.run = Path(sys_root), Path(run_root)
        self.clock, self.monotonic = clock, monotonic
        self.next_poll = self.next_hardware = 0
        self.battery, self.wifi = 'BAT --', 'WiFi ?'
        self.labels = ()
        self.font = None
        self.tone = None
        self.tone_font = None
        self.volume = None
        self.volume_started = None
        self.volume_frame = 0
        self.volume_font = None
        self.next_wifi = 0
        self.wifi_link, self.wifi_strength = "unknown", None
        self.bluetooth_connected = False
        self.pending_update = False

    @staticmethod
    def read(path):
        return path.read_text().strip()

    def hardware(self):
        self.battery, self.wifi = 'BAT --', 'WiFi N/A'
        for supply in sorted((self.sys/'class/power_supply').glob('*'))[:32]:
            try:
                if self.read(supply/'type') != 'Battery':continue
                value = int(self.read(supply/'capacity'))
                if not 0 <= value <= 100:continue
                charging = self.read(supply/'status') == 'Charging' if (supply/'status').exists() else False
                self.battery = f'BAT {value}%' + ('+' if charging else '')
                break
            except (OSError, ValueError):continue
        radios = []
        for radio in sorted((self.sys/'class/rfkill').glob('rfkill*'))[:32]:
            try:
                if self.read(radio/'type') != 'wlan':continue
                radios.append(self.read(radio/'soft') == '0' and self.read(radio/'hard') == '0')
            except OSError:
                self.wifi = 'WiFi ?'
        if radios:self.wifi = 'WiFi ON' if any(radios) else 'WiFi OFF'

    def poll_wifi(self, now):
        if now < self.next_wifi:
            return False
        self.next_wifi = now + 1
        link, strength = 'unknown', None
        try:
            with (self.run/'guideos-wifi/status.json').open('rb') as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError('Oversized Wi-Fi status')
            state = json.loads(raw)
            if not 0 <= now-float(state['observed']) <= 15:
                raise ValueError('Stale Wi-Fi status')
            if state.get('state') in ('off','blocked','no-adapter') or self.wifi == 'WiFi OFF':
                link = 'unavailable'
            elif state.get('state') == 'ready' and state.get('result') != 'unavailable':
                connected = state['connected']
                if connected is None:
                    link = 'offline'
                elif isinstance(connected,str) and connected:
                    link = 'online'
                    rows = state['networks']
                    if not isinstance(rows,list) or len(rows)>128:
                        raise ValueError('Bad network list')
                    # The strongest nearby AP is not necessarily our connection.
                    row = next((r for r in rows if isinstance(r,dict) and
                                r.get('id') == connected and r.get('active') is True), {})
                    value = row.get('signal')
                    if type(value) is int and 0 <= value <= 100:
                        strength = value
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            link, strength = 'unknown', None
        changed = (link,strength) != (self.wifi_link,self.wifi_strength)
        self.wifi_link, self.wifi_strength = link,strength
        return changed

    @property
    def wifi_icon_state(self):
        if self.wifi == 'WiFi OFF' or self.wifi_link == 'unavailable':
            return 'unavailable'
        if self.wifi_link == 'online':
            return 'connected'
        if self.wifi_link == 'offline' or self.wifi == 'WiFi ON':
            return 'disconnected'
        return 'unavailable'

    def draw_wifi(self, draw):
        """One bars glyph: dim, outlined, or filled. No companion indicators."""
        state = self.wifi_icon_state
        for index,height in enumerate((4,7,10,14)):
            x=346+index*7
            rect=(x,22-height,x+4,21)
            if state == 'connected':
                draw.rectangle(rect,fill='#edf1f5')
            else:
                draw.rectangle(rect,outline='#edf1f5' if state == 'disconnected' else '#465362')

    def volume_alpha(self, now=None):
        """Hold briefly, then fade; use elapsed time, never a frame counter."""
        if self.volume_started is None:
            return 0.0
        elapsed = (self.monotonic() if now is None else now) - self.volume_started
        return max(0.0, min(1.0, (1.1-elapsed)/.45))

    def volume_tick(self, now):
        frame = ceil(self.volume_alpha(now)*20)
        changed = frame != self.volume_frame
        self.volume_frame = frame
        return changed

    def observe_volume(self, value, now):
        if value is None:
            self.volume = self.volume_started = None
            return
        value = int(value)
        # First observation (including provider reconnection) is a baseline,
        # not a user adjustment. Show only confirmed level changes.
        if self.volume is not None and value != self.volume:
            self.volume_started = now
        self.volume = value

    def poll(self):
        now = self.monotonic()
        animation_changed = self.volume_tick(now)
        if now < self.next_poll:return animation_changed
        self.next_poll = now + .1
        if now >= self.next_hardware:
            self.hardware()
            self.next_hardware = now + 5
        wifi_changed = self.poll_wifi(now)
        connected, volume = False, 'VOL --'
        level = None
        try:
            path = self.run/'guideos-audio/status.json'
            if path.stat().st_size > 128*1024:raise ValueError('Oversized status')
            state = json.loads(path.read_text())
            if not 0 <= now-float(state['observed']) <= 12:raise ValueError('Stale status')
            devices = state['devices']
            if not isinstance(devices,list) or len(devices)>128:raise ValueError('Bad devices')
            connected = any(row.get('connected') is True for row in devices)
            value = state.get('volume')
            if type(value) in (int,float) and 0 <= value <= 100:
                level = int(value)
                volume = f'VOL {level}%'
        except (OSError,ValueError,TypeError,KeyError,AttributeError):pass
        self.observe_volume(level, now)
        animation_changed = self.volume_tick(now) or animation_changed
        verified = (self.run/'systemd/timesync/synchronized').exists()
        stamp = self.clock()
        labels = (self.battery, stamp.strftime('%H:%M')+('' if verified else '*'),
                  stamp.strftime('%m/%d/%y'), self.wifi, '', volume)
        tone=None
        try:
            path=self.run/'guideos-tone-status.json'
            if path.stat().st_size>2048:raise ValueError()
            candidate=json.loads(path.read_text())
            if (0 < float(candidate['expires'])-now <= 65 and
                candidate['tone'] in ('file-s16','file-s32','file-s16-higher','internal-sine','sequence') and
                candidate['phase'] in ('countdown','playing','restoring','finished','failed') and
                type(candidate['seconds']) is int and 0 <= candidate['seconds'] <= 5):tone=candidate
        except (OSError,ValueError,TypeError,KeyError):pass
        changed = labels != self.labels or tone != self.tone or connected != self.bluetooth_connected
        self.tone=tone
        self.labels = labels
        self.bluetooth_connected = connected
        return changed or animation_changed or wifi_changed

    def draw_bluetooth(self, draw):
        if not self.bluetooth_connected:return
        color='#edf1f5';x=410
        draw.line((x,4,x,24),fill=color,width=2)
        draw.line((x,4,x+7,11,x-4,19),fill=color,width=2)
        draw.line((x,24,x+7,17,x-4,9),fill=color,width=2)

    def volume_layer(self):
        from PIL import Image, ImageDraw, ImageFont
        if self.volume is None:return None
        if getattr(self,'_volume_tile_value',None)==self.volume:return self._volume_tile
        if self.volume_font is None:
            self.volume_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        # Composite a fresh small layer, preserving the screen underneath.
        layer = Image.new("RGBA", (76, 252), (0,0,0,0))
        draw = ImageDraw.Draw(layer)
        color = lambda rgb, opacity: (*rgb, opacity)
        draw.rounded_rectangle((0,0,75,251), radius=14, fill=color((15,25,37),155))
        draw.text((38,20), "VOL", font=self.volume_font, anchor="mm", fill=color((245,248,255),255))
        draw.rounded_rectangle((27,43,49,201), radius=10, fill=color((232,238,244),65))
        height = round(158*self.volume/100)
        if height:
            draw.rounded_rectangle((27,201-height,49,201), radius=min(10,height/2),
                                   fill=color((99,230,176),230))
        draw.text((38,228), f"{self.volume}/100", font=self.volume_font, anchor="mm",
                  fill=color((245,248,255),255))
        self._volume_tile_value,self._volume_tile=self.volume,layer
        return layer

    def draw_volume(self, image):
        from PIL import Image
        alpha=self.volume_alpha()
        if not alpha:return
        layer=self.volume_layer()
        if layer is None:return
        if alpha!=1:
            layer=layer.copy()
            layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
        box = (10,114,86,366)
        background = image.crop(box).convert("RGBA")
        image.paste(Image.alpha_composite(background,layer).convert(image.mode), box[:2])

    def draw(self, image, volume=True):
        from PIL import ImageDraw,ImageFont
        if self.font is None:
            self.font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0,0,image.width-1,HEIGHT-1),fill='#111a26')
        draw.line((0,HEIGHT-1,image.width-1,HEIGHT-1),fill='#586679')
        import os
        field=True
        if field:draw.text((8,5),'GuideOS',font=self.font,fill='#edf1f5')
        # Fixed cells prevent changing values from shifting the rest of the bar.
        for index,(x,label) in enumerate(zip((84,169,220,284,398,514) if field else (10,118,184,284,398,514),self.labels)):
            if index == 3:continue  # Wi-Fi is represented solely by the bars glyph.
            draw.text((x,5),label,font=self.font,fill='#edf1f5')
        self.draw_wifi(draw)
        if self.pending_update:
            # Compact alert glyph in its own cell, immediately left of Wi-Fi.
            draw.rectangle((323,8,326,17),fill='#edf1f5')
            draw.rectangle((323,20,326,22),fill='#edf1f5')
        self.draw_bluetooth(draw)
        if volume:self.draw_volume(image)
        if self.tone:
            if self.tone_font is None:self.tone_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
            title={'internal-sine':'INTERNAL TONE ONLY','file-s16':'16-BIT FILE TONE ONLY','file-s16-higher':'LOUDER FILE TONE (+6 dB)','file-s32':'32-BIT FILE TONE ONLY','sequence':'TONE SEQUENCE'}[self.tone['tone']]
            phase=self.tone['phase']
            line={'countdown':f"Starts in {self.tone['seconds']}",'playing':'LISTEN NOW','restoring':'Restoring audio...','finished':'Ended - report whether you heard it','failed':'Test stopped - inspect diagnostic report'}[phase]
            draw.rectangle((12,165,627,300),fill='#EFEDE1',outline='#3A3B30',width=3)
            draw.text((320,195),title,font=self.tone_font,fill='#3A3B30',anchor='mm')
            draw.text((320,240),line,font=self.tone_font,fill='#3A3B30',anchor='mm')

    def layers(self):
        from PIL import Image
        from guide_gpu_framebuffer import Layer
        # The cached bar/tone is an RGBA surface; transparent pixels retain Home.
        key=(self.labels,self.wifi_icon_state,self.wifi_strength,self.bluetooth_connected,self.pending_update,
             json.dumps(self.tone,sort_keys=True))
        if key!=getattr(self,'_layer_key',None):
            tile=Image.new('RGBA',(640,480))
            self.draw(tile,volume=False)
            self._layer_key,self._layer_tile=key,tile
        result=[]
        alpha=self.volume_alpha()
        if alpha and self.volume is not None:
            result.append(Layer(self.volume_layer(),10,114,opacity=alpha,cache_key='volume'))
        # Status/tone is above the volume exactly as in the software renderer.
        result.append(Layer(self._layer_tile,cache_key='status'))
        return tuple(result)


class StatusSink:
    def __init__(self,sink,status):
        self.sink,self.status = sink,status

    def show(self,image,dirty=None):
        self.status.draw(image)
        if dirty is None:self.sink.show(image)
        else:self.sink.show(image,dirty=dirty)

    @property
    def supports_layers(self):return getattr(self.sink,'supports_layers',False)

    def show_layers(self,image,layers=()):
        self.sink.show_layers(image,tuple(layers)+self.status.layers())
