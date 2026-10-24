import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from kml_utils import check_coord, check_points, kml_warnings


def test_check_coord():
    assert check_coord(121.5, 25.0) is None
    assert check_coord(25.0, 121.5) == '經緯度疑似顛倒'
    assert check_coord(-73.9, 40.7) == '座標超出台灣範圍'


def test_duplicates():
    w = check_points([('A', 121.5, 25.0), ('B', 121.5, 25.0), ('C', 120.2, 23.0)])
    assert len(w) == 1 and w[0]['name'] == 'B' and '重複' in w[0]['reason']


def test_file(tmp_path=None):
    import tempfile
    kml = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           '<Placemark><name>好</name><Point><coordinates>121.5,25.0,0</coordinates></Point></Placemark>'
           '<Placemark><name>反</name><Point><coordinates>25.0,121.5</coordinates></Point></Placemark>'
           '<Placemark><Point><coordinates>abc</coordinates></Point></Placemark>'
           '</Document></kml>')
    with tempfile.NamedTemporaryFile('w', suffix='.kml', delete=False, encoding='utf-8') as f:
        f.write(kml)
    try:
        w = kml_warnings(f.name)
        assert w == [{'name': '反', 'reason': '經緯度疑似顛倒'}]
        open(f.name, 'w').write('not xml')
        assert kml_warnings(f.name) == []
    finally:
        os.remove(f.name)


if __name__ == '__main__':
    test_check_coord(); test_duplicates(); test_file()
    print('ok')
