"""同一份 KML 兩次分析的風險等級比較：純函式，不依賴 Flask，方便單獨測試。"""
from summary_utils import LEVEL_NUM, RANK_COLS


def _lv(row, col):
    return LEVEL_NUM.get((row.get(col) or '').strip(), 0)


def _key(row):
    """以名稱＋座標（取到小數 5 位）配對地點；座標缺漏時只用名稱。"""
    def num(col):
        try:
            return round(float(row.get(col)), 5)
        except (TypeError, ValueError):
            return None
    return ((row.get('地點名稱') or '').strip(), num('經度'), num('緯度'))


def diff_jobs(old_rows, new_rows):
    """比對新舊結果列。回傳 {'changes': {新列索引: 狀態}, 'removed': [名稱], 'counts': {...}}。
    狀態：up／down／same／new；各風險維度的等級差總和 >0 為升級、<0 為降級。"""
    old_by_key = {}
    for r in old_rows:
        old_by_key.setdefault(_key(r), []).append(r)
    changes = {}
    counts = {'up': 0, 'down': 0, 'same': 0, 'new': 0, 'removed': 0}
    for i, r in enumerate(new_rows):
        matches = old_by_key.get(_key(r))
        if not matches:
            changes[i] = 'new'
            counts['new'] += 1
            continue
        old = matches.pop(0)
        delta = sum(_lv(r, c) - _lv(old, c)
                    for c in RANK_COLS if _lv(r, c) and _lv(old, c))
        state = 'up' if delta > 0 else 'down' if delta < 0 else 'same'
        changes[i] = state
        counts[state] += 1
    removed = [k[0] for ms in old_by_key.values() for k in [_key(m) for m in ms]]
    counts['removed'] = len(removed)
    return {'changes': changes, 'removed': removed, 'counts': counts}
