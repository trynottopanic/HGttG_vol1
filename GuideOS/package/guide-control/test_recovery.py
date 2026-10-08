from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from control_recovery import OverlayLease, force_home


class RecoveryTests(unittest.TestCase):
    def test_crash_checkpoint_precedes_browser_freeze(self):
        foreground=Mock();ack=Mock();ack.wait.return_value=True
        with tempfile.TemporaryDirectory() as tmp:
            group=Path(tmp);(group/'cgroup.events').write_text('populated 1\nfrozen 1\n')
            checkpoint=Mock(side_effect=lambda original,inode:self.assertFalse((group/'cgroup.freeze').exists()))
            with patch('control_recovery.active_vt',return_value=2),patch('control_recovery.switch_vt'),patch('control_recovery.browser_group',return_value=group):
                OverlayLease(foreground).prepare(ack,checkpoint)
            self.assertEqual(checkpoint.call_count,2)

    def test_vt_release_precedes_freeze(self):
        foreground=Mock();ack=Mock();ack.wait.return_value=True
        order=[];foreground.freeze.side_effect=lambda:order.append('freeze')
        with tempfile.TemporaryDirectory() as tmp,patch('control_recovery.active_vt',return_value=2),patch('control_recovery.switch_vt',side_effect=lambda number:order.append('vt:'+str(number))),patch('control_recovery.browser_group',return_value=Path(tmp)/'missing'):
            lease=OverlayLease(foreground);self.assertEqual(lease.prepare(ack),2)
            self.assertEqual(order,['vt:3','freeze'])
            lease.release()
            foreground.thaw.assert_called_once()
            self.assertEqual(order[-1],'vt:2')

    def test_unacknowledged_display_never_frozen_or_overwritten(self):
        foreground=Mock();ack=Mock();ack.wait.return_value=False
        with patch('control_recovery.active_vt',return_value=1),patch('control_recovery.switch_vt') as switch:
            with self.assertRaisesRegex(RuntimeError,'acknowledge'):OverlayLease(foreground).prepare(ack)
            switch.assert_not_called();foreground.freeze.assert_not_called()

    def test_replaced_browser_group_cannot_be_thawed(self):
        with tempfile.TemporaryDirectory() as tmp:
            lease=OverlayLease(Mock());lease.browser=Path(tmp);lease.browser_inode=-1
            with self.assertRaisesRegex(RuntimeError,'replaced'):lease.release()
            lease.foreground.thaw.assert_not_called()

    def test_home_start_follows_display_return(self):
        order=[];runtime=Mock();runtime.command.side_effect=lambda *args:order.append('start')
        lease=OverlayLease(Mock());lease.original=2
        with patch('control_recovery.switch_vt',side_effect=lambda _:order.append('vt')),patch('control_recovery.Host',return_value=runtime):
            lease.release(home=True)
        self.assertEqual(order,['vt','start'])


if __name__=='__main__':unittest.main()
