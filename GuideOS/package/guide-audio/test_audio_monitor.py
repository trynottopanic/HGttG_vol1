import unittest
from audio_monitor import route_snapshot


class RouteTests(unittest.TestCase):
    def test_selected_route_not_unrelated_default(self):
        def node(name, mute, volume):
            return {'info': {'props': {'node.name': name},
                             'params': {'Props': [{'mute': mute, 'channelVolumes': [volume,volume]}]}}}
        items = [node('speaker', True, .1), node('earbud', False, .7)]
        self.assertEqual(route_snapshot(items,'speaker'),dict(muted=1,route_volume=10))
        self.assertEqual(route_snapshot(items,'earbud'),dict(muted=0,route_volume=70))
        self.assertEqual(route_snapshot(items,'gone'),dict(muted=-1,route_volume=-1))

    def test_no_route_parameters_are_unknown_not_unmuted(self):
        self.assertEqual(route_snapshot([{'info': {'props': {'node.name':'speaker'}}}], 'speaker'),
                         dict(muted=-1,route_volume=-1))
