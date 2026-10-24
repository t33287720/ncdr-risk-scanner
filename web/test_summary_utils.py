import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from summary_utils import build_summary, find_county


def test_basic():
    rows = [
        {'地點名稱': '台北市A', '淹水風險': '第五級', '坡地危害度': '第一級'},
        {'地點名稱': '臺北市B', '淹水風險': '第二級'},
        {'地點名稱': '無縣市', '淹水風險': '無'},
    ]
    s = build_summary(rows)
    assert s['counts']['第五級'] == 1 and s['valid'] == 2
    assert s['high'] == 1 and s['high_pct'] == 50
    assert s['top5'][0] == {'name': '台北市A', 'top': '第五級'}
    assert s['counties'] == [{'county': '臺北市', 'total': 2, 'high': 1}]
    assert s['upgrades'] is None
    assert build_summary([]) is None


def test_compare():
    rows = [{'地點名稱': 'x', '淹水風險(2°C)': '第四級', '風險趨勢(1.5→4°C)': '上升'}]
    s = build_summary(rows, compare=True)
    assert s['high'] == 1 and s['upgrades'] == 1


def test_county():
    assert find_county('高雄市前鎮區') == '高雄市'
    assert find_county('abc') is None


if __name__ == '__main__':
    test_basic(); test_compare(); test_county()
    print('ok')
