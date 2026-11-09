import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from csv_utils import csv_to_points, points_to_kml
from kml_utils import extract_points


def test_basic_and_alias():
    raw = 'Name,LAT,Lon\nA,25.0,121.5\nB,23.5,120.9\n'.encode()
    assert csv_to_points(raw) == [('A', 121.5, 25.0), ('B', 120.9, 23.5)]


def test_bom_and_chinese_header():
    raw = '﻿名稱,緯度,經度\n台北,25.0,121.5\n'.encode('utf-8')
    assert csv_to_points(raw) == [('台北', 121.5, 25.0)]


def test_big5():
    raw = '名稱,緯度,經度\n高雄,22.6,120.3\n'.encode('big5')
    assert csv_to_points(raw)[0][0] == '高雄'


def test_missing_column():
    try:
        csv_to_points(b'name,lat\nA,25\n')
    except ValueError as e:
        assert '經度' in str(e)
    else:
        raise AssertionError


def test_bad_number():
    try:
        csv_to_points(b'name,lat,lng\nA,x,121\n')
    except ValueError as e:
        assert '第 2 列' in str(e)
    else:
        raise AssertionError


def test_kml_escape_roundtrip():
    kml = points_to_kml([('A&B <1>', 121.5, 25.0)])
    pts = extract_points(ET.fromstring(kml))
    assert pts == [('A&B <1>', 121.5, 25.0)]


if __name__ == '__main__':
    for k, v in list(globals().items()):
        if k.startswith('test_'):
            v()
    print('ok')
