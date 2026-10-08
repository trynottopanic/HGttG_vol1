"""RAM-only captured backdrop and a half-opacity diagnostic pane."""
import array
from pathlib import Path
import time
from PIL import Image,ImageDraw,ImageFont
from guide_status_bar import StatusBar


def capture(framebuffer):
    row_bytes=framebuffer.width*framebuffer.bpp//8
    raw=b''.join(framebuffer.mem[(y+framebuffer.yoff)*framebuffer.stride+framebuffer.xoff*framebuffer.bpp//8:
          (y+framebuffer.yoff)*framebuffer.stride+framebuffer.xoff*framebuffer.bpp//8+row_bytes]
          for y in range(framebuffer.height))
    if framebuffer.bpp==32 and framebuffer.fields==[(16,8,0),(8,8,0),(0,8,0)]:
        return Image.frombytes('RGB',(framebuffer.width,framebuffer.height),raw,'raw','BGRX')
    values=array.array('H' if framebuffer.bpp==16 else 'I')
    values.frombytes(raw)
    pixels=bytes(channel for value in values for offset,length,_ in framebuffer.fields
                 for channel in [((value>>offset)&((1<<length)-1))*255//((1<<length)-1)])
    return Image.frombytes('RGB',(framebuffer.width,framebuffer.height),pixels)


class View:
    def __init__(self,background):
        self.statusbar=StatusBar()
        self.background=background.resize((640,480)).convert('RGBA') if background is not None else Image.new('RGBA',(640,480),(8,12,20,255))
        self.font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
        self.small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)

    def render(self,status,page=0):
        layer=Image.new('RGBA',(640,480),(0,0,0,0))
        draw=ImageDraw.Draw(layer)
        draw.rounded_rectangle((12,32,628,468),radius=12,fill=(8,16,28,128),outline=(220,235,255,180))
        def text(y,value,color=(245,248,255,255),small=False):
            font=self.small if small else self.font
            value=str(value)
            while value and draw.textlength(value,font=font)>580:value=value[:-2]+'…'
            draw.text((28,y),value,font=font,fill=color)
        text(40,'GUIDE DIAGNOSTICS  /  SCREEN PAUSED')
        age=max(0,time.monotonic()-status.get('observed',0))
        if not status or age>15:
            text(65,'Diagnostic data unavailable or stale',(255,206,114,255),small=True)
        else:text(65,f'Sample age: {age:.1f}s   |   Page {page+1}/3',small=True)
        if page==0:
            cpu=status.get('cpu_percent_total')
            text(90,'CPU total: '+(f'{cpu:.1f}%' if cpu is not None else 'waiting for sample'))
            memory=status.get('memory',{})
            mib=lambda key:memory.get(key,0)/1048576
            text(120,f"Memory: {mib('used_bytes'):.0f} MiB used / {mib('MemTotal'):.0f} MiB total")
            text(150,f"Available: {mib('MemAvailable'):.0f} MiB   Free: {mib('MemFree'):.0f} MiB")
            text(190,'PROCESS',small=True)
            draw.text((290,190),'PID / PARENT',font=self.small,fill=(245,248,255,255))
            draw.text((525,190),'CPU',font=self.small,fill=(245,248,255,255))
            rows=sorted(status.get('processes',[]),key=lambda r:r.get('cpu_percent_one_core') or 0,reverse=True)[:6]
            for i,row in enumerate(rows):
                value=row.get('cpu_percent_one_core')
                cpu_text=f'{value:5.1f}%' if value is not None else '   --'
                y=215+i*27
                text(y,''.join(c for c in row['name'][:18] if c.isprintable()),small=True)
                draw.text((290,y),f"{row['pid']} / {row['ppid']}",font=self.small,fill=(245,248,255,255))
                draw.text((525,y),cpu_text,font=self.small,fill=(245,248,255,255))
        elif page==1:
            latest=status.get('latest_events',{})
            audio=dict(latest.get('AUDIO_QUEUE',{}))
            state=latest.get('AUDIO_STATE',{})
            if state.get('recorded',0)>audio.get('recorded',0):audio.update(state)
            text(90,'Audio: '+audio.get('state','no sample')+f"   position {audio.get('position',0):.1f}s")
            text(120,f"Queue: {audio.get('buffer_ms',0):.0f} ms   Queue empty: {audio.get('queue_empty_events','?')}")
            video=latest.get('VIDEO_METRICS',{})
            text(160,f"Boot video: {video.get('frames','--')} frames, {video.get('late_frames','--')} over 33 ms")
            text(190,f"Frame mean/max: {video.get('frame_mean_ms',0):.1f} / {video.get('frame_max_ms',0):.1f} ms")
            for i,(metric,label) in enumerate((('navigation_submit','Navigation'),('audio_ack','Audio ack'),('wifi_ack','Wi-Fi ack'))):
                row=latest.get('TIMING:'+metric,{})
                text(235+i*29,f"{label}: mean {row.get('mean_ms',0):.1f} / max {row.get('max_ms',0):.1f} ms",small=True)
            text(335,f"Events dropped: {status.get('dropped_events',0)}   Log errors: {status.get('log_write_errors',0)}",small=True)
            text(364,f"Sampler: {status.get('sample_cost_ms',0):.1f} ms   CPU quota: 5% of one core",small=True)
            faults=[r['code'] for r in status.get('recent',[]) if 'ERROR' in r['code'] or 'TIMEOUT' in r['code']]
            text(386,'Latest fault: '+(faults[-1] if faults else 'none in recent events'),small=True)
        else:
            text(95,'ACTIVE APPLICATIONS')
            rows=status.get('workloads',[])[:6]
            for i,row in enumerate(rows):
                text(130+i*30,f"{row['label']}   {row['memory']/1048576:.0f} MiB",small=True)
            if not rows:text(130,'No separate applications; Guide interface is active.',small=True)
            notice=status.get('recovery_notice','')
            if notice:text(320,notice,(255,206,114,255),small=True)
            if status.get('confirm_close'):
                text(355,'Unsaved work may be lost.',(255,206,114,255),small=True)
                text(382,'A: confirm close + Home     B: cancel',small=True)
            elif status.get('recovery_busy'):text(370,'Closing applications; waiting for display release.',small=True)
            else:text(370,'A: force close active apps + return Home',small=True)
        text(410,('Recovery incomplete; retry on Active Applications.' if status.get('recovery_failed')
                  else 'Start + Select / B: resume    Left / Right: page'),small=True)
        text(437,'Power and system services remain active.',small=True)
        image=Image.alpha_composite(self.background,layer).convert('RGB')
        self.statusbar.draw(image)
        return image
