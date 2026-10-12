# coding: utf-8
import unittest
from retry_utils import failed_indexes, count_failed, merge_retry


class RetryUtilsTest(unittest.TestCase):
    def setUp(self):
        self.results = [
            {'name': 'A', 'level': '第三級'},
            {'name': 'B', 'level': '錯誤'},
            {'name': 'C', 'level': '無'},
            {'name': 'D', 'level': '錯誤'},
        ]

    def test_failed_indexes(self):
        self.assertEqual(failed_indexes(self.results), [1, 3])
        self.assertEqual(count_failed(self.results), 2)
        self.assertEqual(failed_indexes([]), [])

    def test_merge_retry(self):
        new_b = {'name': 'B', 'level': '第二級'}
        merged = merge_retry(self.results, {1: new_b})
        self.assertEqual(merged[1], new_b)
        self.assertEqual(merged[3]['level'], '錯誤')
        self.assertEqual(self.results[1]['level'], '錯誤')  # 不修改原資料
        self.assertEqual(len(merged), 4)


if __name__ == '__main__':
    unittest.main()
