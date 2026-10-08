import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import guide_boot_console as console

class ConsoleCleanup(unittest.TestCase):
    def test_saved_mode_restores_after_acquisition_failure_and_cleanup_repeats(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'console.json'
            writes=[]
            def ioctl(fd,operation,value,*args):
                if operation==console.KDGETMODE: value[0]=0
                elif operation==console.KDSETMODE:
                    # Recovery intent must exist before changing console mode.
                    self.assertEqual(json.loads(state.read_text()),dict(mode=0))
                    writes.append(value)
                    if value==1: raise OSError('fixture setup failure')
            with patch.object(console,'STATE',state), patch.object(console,'Path',return_value=Mock(exists=lambda:True)), \
                 patch.object(console.os,'open',return_value=7) as opened, patch.object(console.os,'close') as closed, \
                 patch.object(console.fcntl,'ioctl',side_effect=ioctl):
                with self.assertRaises(OSError): console.acquire()
                console.release(); console.release()
                self.assertEqual(writes,[1,0]); self.assertFalse(state.exists())
                self.assertEqual(opened.call_count,2); self.assertEqual(closed.call_count,2)

if __name__=='__main__': unittest.main()
