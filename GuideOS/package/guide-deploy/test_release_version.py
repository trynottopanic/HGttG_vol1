import unittest
from release_version import valid_build_label,valid_label

class ReleaseVersionTests(unittest.TestCase):
    def test_new_series_uses_two_digit_revision_without_resetting_legacy_readers(self):
        for label in ('0.4.3.01','0.4.3.09','0.4.3.10','0.4.3.99','0.4.2','0.4.2.01','0.4.1-home-v3-r23'):
            self.assertTrue(valid_build_label(label),label);self.assertTrue(valid_label(label),label)
        for label in ('0.4.3','0.4.3.00','0.4.3.1','0.4.3.100','0.4.3_bad','0.4.3-01','0.4.3.01-debug'):
            self.assertFalse(valid_build_label(label),label)
