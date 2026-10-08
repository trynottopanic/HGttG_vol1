"""Visual structure and fixed controls for the approved media draft adaptation."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import ImageChops
from guide_ui_model import ScreenModel,MenuItem,Fact,ActionHint
from guide_v3_ui import V3UI
from guide_deck_layouts import FIELD,PANEL,ROW,FOCUS

TITLE='Interview with the expedition crew — complete recording — Part 02.flac'
BACK=ActionHint('B','Back','blue','back','key',304)

def fixtures():
    rows=tuple(MenuItem('part:'+str(i),TITLE.replace('02',f'{i:02d}'),'audio-row','media:'+str(i),
                        metadata='Expedition recordings · FLAC') for i in (1,2,3))+(MenuItem('night','Night sounds — northern camp.wav','audio-row','media:4',metadata='Field recordings · WAV'),)
    library=ScreenModel('media-library','Media Library',items=rows,focus_id='part:2',actions=(BACK,))
    controls=tuple(MenuItem(identity,label,'audio-row',value) for identity,label,value in
        (('previous','Previous','media-previous'),('pause','Pause','media-pause'),('next','Next','media-next')))
    player=ScreenModel('audio-player','Music Player',items=controls,focus_id='pause',facts=(
        Fact('Title',TITLE),Fact('Source','Expedition recordings'),Fact('Output','Deck speakers'),
        Fact('Elapsed','768'),Fact('Duration','2182'),Fact('State','playing')),actions=(BACK,))
    details=ScreenModel('file-details','File Details',items=(MenuItem('play','Play','play-media',{}),
        MenuItem('copy','Copy…','copy',{}),MenuItem('more','More details','more-details')),
        focus_id='play',facts=(Fact('Name',TITLE),Fact('Folder','/External Card/Expedition recordings/Northern survey/Field interviews/Crew accounts/Complete recordings/'),
        Fact('Extension','flac'),Fact('Type','File'),Fact('Size','248,000,000 bytes'),Fact('Duration','2182')),actions=(BACK,))
    paused=replace(player,items=(controls[0],replace(controls[1],label='Resume',value='media-resume'),controls[2]),
                   facts=tuple(replace(f,value='paused') if f.label=='State' else f for f in player.facts))
    return library,replace(library,focus_id='part:3'),player,paused,details,replace(details,focus_id='copy')


class DeckLayoutTests(unittest.TestCase):
    def setUp(self):self.ui=V3UI()

    def test_draft_palette_and_panel_geometry(self):
        library,_,player,_,details,_=fixtures()
        for model in (library,player,details):
            image=self.ui.render(model).image
            self.assertEqual(image.getpixel((0,28)),(213,221,227))
            self.assertEqual(image.getpixel((0,92)),(206,226,239))
            self.assertEqual(image.getpixel((0,432)),(20,41,54))
        image=self.ui.render(library).image
        self.assertEqual(image.getpixel((20,100)),(78,101,117))
        self.assertEqual(image.getpixel((16,156)),(235,165,46))
        self.assertEqual(image.getpixel((16,332)),(213,221,227))
        image=self.ui.render(details).image
        self.assertEqual(image.getpixel((16,100)),(213,221,227))
        self.assertEqual(image.getpixel((16,212)),(213,221,227))
        self.assertEqual(image.getpixel((16,344)),(235,165,46))

    def test_four_rows_keep_full_identity_and_metadata(self):
        model=fixtures()[0];layout=self.ui.render(model)
        regions=[r for r in layout.regions if r.identity!='back']
        self.assertEqual(len(regions),4)
        self.assertEqual(regions[1].label,TITLE)
        self.assertEqual(regions[1].value,'media:2')
        self.assertEqual(regions[1].rect.tuple(),(16,156,623,211))
        self.assertTrue(self.ui.text.provider.available)

    def test_offscreen_latin_text_keeps_requested_color(self):
        glyphs=self.ui.text.provider.render('GuideOS',24,(213,221,227))
        for pixel in glyphs.getdata():
            if pixel[3]>128:
                self.assertLessEqual(max(abs(a-b) for a,b in zip(pixel[:3],(213,221,227))),2)

    def test_refresh_remains_reachable_without_using_a_recording_row(self):
        model=fixtures()[0]
        refresh=MenuItem('refresh','Refresh card files','audio-row','refresh-media')
        layout=self.ui.render(replace(model,items=(refresh,)+model.items))
        self.assertEqual(len(layout.regions),6)
        self.assertEqual(next(r for r in layout.regions if r.identity=='refresh').rect.top,37)
        self.assertEqual(next(r for r in layout.regions if r.identity=='part:1').rect.top,100)

    def test_list_focus_paginates_and_selected_name_changes(self):
        model=fixtures()[0]
        extra=tuple(MenuItem(str(i),'Another complete name '+str(i)+'.flac','audio-row','media:'+str(i)) for i in range(8))
        model=replace(model,items=model.items+extra,focus_id='7')
        layout=self.ui.render(model)
        self.assertIn('7',layout.visible_ids)
        self.assertNotIn('part:1',layout.visible_ids)

    def test_scroll_repaints_same_model_and_keeps_control_geometry(self):
        from guide_shell import Screen
        model=replace(fixtures()[4],facts=(Fact('Name','Long name '*60+'.flac'),Fact('Folder','/Folder/'*40)))
        screen=Screen.__new__(Screen);screen.schema=self.ui;screen.sink=SimpleNamespace(supports_layers=False)
        state=SimpleNamespace(page='files',installer_panel=None,application_panel=None,
                              operations=SimpleNamespace(pages={'files':None},model=lambda:model))
        with patch('guide_deck_text.time.monotonic',return_value=0):first=screen._v3_layout(state)
        for step in range(1,81):
            with patch('guide_deck_text.time.monotonic',return_value=step/10):last=screen._v3_layout(state)
        self.assertNotEqual(first.image.crop((28,132,612,196)).tobytes(),last.image.crop((28,132,612,196)).tobytes())
        self.assertEqual(first.regions,last.regions)
        self.assertEqual(first.image.crop((0,312,640,480)).tobytes(),last.image.crop((0,312,640,480)).tobytes())

    def test_multilingual_names_are_clipped_and_keep_the_extension(self):
        model=fixtures()[0]
        for name in ('e\u0301'*150+'.flac','العربية שלום '*30+'.ogg','日本語 '*60+'.wav','👩\u200d🚀'*80+'.mp3'):
            item=replace(model.items[0],label=name)
            value=self.ui.text.shorten(name,24,580,filename=True,bold=True)
            self.assertTrue(value.endswith(name[name.rfind('.'):]))
            self.assertLessEqual(self.ui.text.width(value,24,bold=True),580)
            rendered=self.ui.render(replace(model,items=(item,),focus_id=item.identity)).image
            self.assertEqual(rendered.getpixel((0,92)),(206,226,239))
            self.assertEqual(rendered.getpixel((639,431)),(206,226,239))


if __name__=='__main__':unittest.main()
