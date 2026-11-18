import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from geocode_utils import geocode_one, geocode_rows
from csv_utils import parse_csv, csv_to_points


def fake_get(calls):
    def get(url, params):
        calls.append((url, params['q']))
        if 'photon' in url:
            if params['q'] == '台北101':
                return {'features': [{'geometry': {'coordinates': [121.5645, 25.034]}}]}
            return {'features': []}
        if params['q'] == '高雄港':
            return [{'lat': '22.6', 'lon': '120.3'}]
        return []
    return get


def test_photon_then_nominatim_fallback():
    calls = []
    assert geocode_one('台北101', fake_get(calls)) == (25.034, 121.5645)
    assert len(calls) == 1
    assert geocode_one('高雄港', fake_get(calls)) == (22.6, 120.3)
    assert geocode_one('不存在', fake_get(calls)) is None


def test_service_exception_falls_through():
    def boom(url, params):
        if 'photon' in url:
            raise RuntimeError('down')
        return [{'lat': '23', 'lon': '121'}]
    assert geocode_one('x', boom) == (23.0, 121.0)


def test_rows_cache_and_failed():
    with tempfile.TemporaryDirectory() as d:
        cache = os.path.join(d, 'c', 'geo.json')
        calls = []
        pts, failed = geocode_rows([('A', '台北101'), ('B', '不存在')], fake_get(calls), cache, sleep=lambda s: None)
        assert pts == [('A', 121.5645, 25.034)]
        assert failed == [('B', '不存在')]
        n = len(calls)
        calls.clear()
        pts, failed = geocode_rows([('A2', '台北101')], fake_get(calls), cache, sleep=lambda s: None)
        assert pts == [('A2', 121.5645, 25.034)] and calls == [] and n > 0


def test_bad_cache_file_ignored():
    with tempfile.TemporaryDirectory() as d:
        cache = os.path.join(d, 'geo.json')
        open(cache, 'w').write('{broken')
        pts, _ = geocode_rows([('A', '台北101')], fake_get([]), cache, sleep=lambda s: None)
        assert len(pts) == 1


def test_parse_csv_address_only():
    raw = '名稱,地址\n門市,台北市信義路\n'.encode()
    assert parse_csv(raw) == ([], [('門市', '台北市信義路')])
    try:
        csv_to_points(raw)
    except ValueError as e:
        assert '只有地址' in str(e)
    else:
        raise AssertionError


def test_parse_csv_coords_win_over_address():
    raw = 'name,address,lat,lng\nA,x,25,121\n'.encode()
    assert parse_csv(raw) == ([('A', 121.0, 25.0)], [])


def test_parse_csv_empty_address():
    try:
        parse_csv('名稱,地址\nA,\n'.encode())
    except ValueError as e:
        assert '第 2 列' in str(e)
    else:
        raise AssertionError


if __name__ == '__main__':
    for k, v in list(globals().items()):
        if k.startswith('test_'):
            v()
    print('ok')
