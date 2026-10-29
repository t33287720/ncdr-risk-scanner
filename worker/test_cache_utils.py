# coding: utf-8
import os
import tempfile
import unittest
from cache_utils import WmsCache


class WmsCacheTest(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), 'cache', 'wms-cache.json')
        self.now = [1000.0]
        self.clock = lambda: self.now[0]

    def make(self, **kw):
        return WmsCache(self.path, clock=self.clock, **kw)

    def test_hit_and_rounding(self):
        c = self.make()
        c.put(25.0330001, 121.5654, '2C', {'flood_risk': '第三級'})
        self.assertEqual(c.get(25.033, 121.5654, '2C')['flood_risk'], '第三級')
        self.assertIsNone(c.get(25.033, 121.5654, '4C'))
        self.assertEqual(c.hits, 1)

    def test_persist_and_expire(self):
        self.make().put(25, 121, '2C', {'flood_risk': '第二級'})
        self.assertIsNotNone(self.make().get(25, 121, '2C'))
        self.now[0] += 8 * 86400
        c = self.make()
        self.assertIsNone(c.get(25, 121, '2C'))
        self.assertEqual(c.data, {})

    def test_disabled(self):
        c = self.make(days=0)
        c.put(25, 121, '2C', {'flood_risk': '第二級'})
        self.assertIsNone(c.get(25, 121, '2C'))
        self.assertFalse(os.path.exists(self.path))

    def test_corrupt_file(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, 'w') as f:
            f.write('{broken')
        c = self.make()
        self.assertEqual(c.data, {})
        c.put(25, 121, '2C', {'flood_risk': '第二級'})
        self.assertIsNotNone(self.make().get(25, 121, '2C'))

    def test_max_entries_evicts_oldest(self):
        c = self.make(max_entries=2)
        for i in range(3):
            self.now[0] += 1
            c.put(i, 0, '2C', {'flood_risk': '第一級'})
        self.assertIsNone(c.get(0, 0, '2C'))
        self.assertIsNotNone(c.get(2, 0, '2C'))


if __name__ == '__main__':
    unittest.main()
