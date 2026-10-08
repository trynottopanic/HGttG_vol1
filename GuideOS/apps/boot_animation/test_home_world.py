import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guide_boot_world
from guide_home_world import HomeWorldRenderer, WorldUnavailable, load_current, publish_current, validate_world

class HomeWorldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp.name) / "runtime"
        self.runtime.mkdir()
        self.source = self.runtime / "world-test" / "assets"
        guide_boot_world.generate(HERE / "assets", self.source, 7)

    def tearDown(self):
        self.temp.cleanup()

    def test_publish_and_load_revalidates_generated_world(self):
        published = publish_current(self.source, self.runtime)
        directory, loaded = load_current(self.runtime)
        self.assertEqual(directory, self.source.resolve())
        self.assertEqual(loaded["boot"], 7)
        self.assertEqual(published["sha256"], loaded["sha256"])

    def test_rejects_changed_layer(self):
        path = self.source / "roads-fixed-v2.r8"
        path.write_bytes(b"x" * path.stat().st_size)
        with self.assertRaises(WorldUnavailable):
            validate_world(self.source)

    def test_rejects_pointer_outside_runtime(self):
        outside = Path(self.temp.name) / "outside"
        shutil.copytree(self.source, outside)
        with self.assertRaises(WorldUnavailable):
            publish_current(outside, self.runtime)

    def test_renders_small_moving_world(self):
        renderer = HomeWorldRenderer(self.source)
        first = renderer.render((220, 150), .0, .0)
        later = renderer.render((220, 150), .2, .1)
        self.assertEqual(first.size, (220, 150))
        self.assertNotEqual(first.tobytes(), later.tobytes())

if __name__ == "__main__":
    unittest.main()
