"""結果頁摘要統計：純函式，不依賴 Flask，方便單獨測試。"""

LEVELS = ['第五級', '第四級', '第三級', '第二級', '第一級']
LEVEL_NUM = {'第一級': 1, '第二級': 2, '第三級': 3, '第四級': 4, '第五級': 5}
# 淹水＋坡地等會納入「最高風險前 5 名」比較的欄位
RANK_COLS = ['淹水風險', '淹水危害度', '淹水脆弱度', '淹水危害脆弱度', '淹水暴露度',
             '坡地危害度', '坡地危害脆弱度']
COUNTIES = [
    '臺北市', '新北市', '桃園市', '臺中市', '臺南市', '高雄市', '基隆市', '新竹市', '嘉義市',
    '新竹縣', '苗栗縣', '彰化縣', '南投縣', '雲林縣', '嘉義縣', '屏東縣', '宜蘭縣', '花蓮縣',
    '臺東縣', '澎湖縣', '金門縣', '連江縣',
]


def _lv(row, col):
    return LEVEL_NUM.get((row.get(col) or '').strip(), 0)


def find_county(name):
    """從地點名稱找縣市（臺／台視為相同）；找不到回傳 None。"""
    text = (name or '').replace('台', '臺')
    for c in COUNTIES:
        if c in text:
            return c
    return None


def build_summary(rows, compare=False):
    """依 CSV 列計算摘要；rows 為空時回傳 None。"""
    if not rows:
        return None
    base = '淹水風險(2°C)' if compare and rows and '淹水風險(2°C)' in rows[0] else '淹水風險'
    counts = {lv: 0 for lv in LEVELS}
    valid = 0
    for r in rows:
        n = _lv(r, base)
        if n:
            counts[LEVELS[5 - n]] += 1
            valid += 1
    high = counts['第五級'] + counts['第四級']
    peak = max(counts.values()) or 1

    ranked = []
    for r in rows:
        levels = [_lv(r, c) for c in RANK_COLS]
        top = max(levels)
        if top:
            ranked.append((top, sum(levels), r))
    ranked.sort(key=lambda t: (-t[0], -t[1]))
    top5 = [{'name': r.get('地點名稱', '—'), 'top': LEVELS[5 - t]} for t, _, r in ranked[:5]]

    by_county = {}
    for r in rows:
        c = find_county(r.get('地點名稱'))
        if not c:
            continue
        d = by_county.setdefault(c, {'county': c, 'total': 0, 'high': 0})
        d['total'] += 1
        if _lv(r, base) >= 4:
            d['high'] += 1
    counties = sorted(by_county.values(), key=lambda d: (-d['high'], -d['total'], d['county']))

    upgrades = None
    if compare:
        upgrades = sum(1 for r in rows if r.get('風險趨勢(1.5→4°C)') == '上升')

    return {
        'base_col': base, 'total': len(rows), 'valid': valid, 'counts': counts, 'peak': peak,
        'high': high, 'high_pct': round(high * 100 / valid) if valid else 0,
        'top5': top5, 'counties': counties, 'upgrades': upgrades,
    }
