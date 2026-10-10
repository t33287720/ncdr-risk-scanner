# coding: utf-8
"""重查失敗地點用的純函式（不依賴網路，方便單元測試）。"""

ERROR_LEVEL = '錯誤'


def failed_indexes(results):
    """回傳查詢失敗（level == '錯誤'）的結果索引。"""
    return [i for i, r in enumerate(results) if r.get('level') == ERROR_LEVEL]


def count_failed(results):
    return len(failed_indexes(results))


def merge_retry(results, retried):
    """把重查結果依索引合併回原結果，回傳新 list（不修改原資料）。
    retried: {索引: 新結果}"""
    return [retried.get(i, r) for i, r in enumerate(results)]
