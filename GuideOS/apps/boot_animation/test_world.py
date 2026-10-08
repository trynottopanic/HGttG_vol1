import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image,ImageChops
from guide_boot_world import selection,generate,rgb565,cloud_tiles,clouds,ocean,word_caption,LAYERS
ASSETS=Path(__file__).parent/'assets'
class WorldTests(unittest.TestCase):
 def test_word_cycles_recur(self):
  words=json.loads((ASSETS/'world-vocabulary-v1.json').read_text())
  first=selection(1,words)
  self.assertEqual(selection(201,words)['terrain'],first['terrain'])
  self.assertEqual(selection(311,words)['clouds'],first['clouds'])
  self.assertEqual(selection(151,words)['lights'],first['lights'])
  self.assertEqual(selection(18601,words),first)
 def test_caption_uses_exact_selected_words_and_all_vocabulary_fits(self):
  vocab=json.loads((ASSETS/'world-vocabulary-v1.json').read_text())
  seeds=selection(4,vocab)
  self.assertEqual(' '.join(seeds[k]['word'] for k in LAYERS),'interstellar coincidence started')
  caption=word_caption(ASSETS,seeds)
  self.assertEqual(caption.size,(600,24));self.assertIsNotNone(caption.getbbox())
  self.assertEqual(caption.tobytes(),word_caption(ASSETS,selection(4,vocab)).tobytes())
  self.assertNotEqual(caption.tobytes(),word_caption(ASSETS,selection(5,vocab)).tobytes())
  longest={k:dict(word=max(vocab[k],key=len)) for k in LAYERS}
  self.assertIsNotNone(word_caption(ASSETS,longest).getbbox())
  self.assertTrue(all(32<=ord(c)<=126 for words in vocab.values() for word in words for c in word))
 def test_rgb565_channel_order(self):
  image=Image.new('RGB',(3,1));image.putdata([(255,0,0),(0,255,0),(0,0,255)])
  self.assertEqual(rgb565(image),b'\x00\xf8\xe0\x07\x1f\x00')
 def test_reproducible_changing_and_independent_maps(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);a,mask,first=generate(ASSETS,d/'one',1)
   _,_,again=generate(ASSETS,d/'again',1)
   _,_,second=generate(ASSETS,d/'two',2)
   _,_,wrapped=generate(ASSETS,d/'wrap',201)
   self.assertEqual(first,again)
   for key,value in first['sha256'].items():self.assertNotEqual(value,second['sha256'][key])
   self.assertEqual(first['sha256']['terrain-fixed-v2.rgb565'],wrapped['sha256']['terrain-fixed-v2.rgb565'])
   self.assertNotEqual(first['sha256']['clouds-fixed-v2.r8'],wrapped['sha256']['clouds-fixed-v2.r8'])
   self.assertEqual(a.crop((0,0,1,512)).tobytes(),a.crop((1023,0,1024,512)).tobytes())
   for y in (0,15,496,511):self.assertEqual(set(mask.crop((0,y,1024,y+1)).tobytes()),{255})
   for name,size in [('terrain-fixed-v2.rgb565',1048576),('clouds-fixed-v2.r8',1048576),('lights-fixed-v2.r8',524288),('roads-fixed-v2.r8',524288)]:self.assertEqual((d/'one'/name).stat().st_size,size)
   ocean=ImageChops.invert(mask)
   for name in ('lights-fixed-v2.r8','roads-fixed-v2.r8'):
    layer=Image.frombytes('L',(1024,512),(d/'one'/name).read_bytes())
    self.assertIsNone(ImageChops.multiply(ocean,layer).getbbox())
 def test_cloud_atlas_opacity_and_wrapping(self):
  tiles=cloud_tiles(ASSETS/'cloud-atlas-draft-v1.png')
  self.assertEqual(len(tiles),8)
  for tile in tiles:
   self.assertIsNotNone(tile.getbbox())
   self.assertGreater(len(set(tile.tobytes())),8)
  layer=clouds(tiles,17)
  self.assertEqual(layer.size,(2048,512))
  self.assertEqual(layer.tobytes(),clouds(tiles,17).tobytes())
  self.assertNotEqual(layer.tobytes(),clouds(tiles,18).tobytes())
  self.assertEqual(layer.crop((0,0,1,512)).tobytes(),layer.crop((2047,0,2048,512)).tobytes())
  coverage=sum(v>32 for v in layer.tobytes())/(2048*512)
  self.assertGreater(coverage,.08);self.assertLess(coverage,.55)
  with tempfile.TemporaryDirectory() as d:
   bad=Path(d)/'colored.png';Image.new('RGBA',(512,256),(0,255,255,255)).save(bad)
   with self.assertRaises(ValueError):cloud_tiles(bad)
 def test_ocean_has_reproducible_longitude_detail(self):
  water=ocean(17)
  self.assertEqual(water.tobytes(),ocean(17).tobytes())
  self.assertNotEqual(water.tobytes(),ocean(18).tobytes())
  self.assertGreater(len(set(water.crop((0,256,1024,257)).getdata())),15)
  self.assertEqual(water.crop((0,0,1,512)).tobytes(),water.crop((1023,0,1024,512)).tobytes())
if __name__=='__main__':unittest.main()
