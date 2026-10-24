"""CSV 地點清單轉 KML：純函式，不依賴 Flask，方便單獨測試。"""
import csv
import io
from xml.sax.saxutils import escape

NAME_KEYS = ('名稱', 'name')
LAT_KEYS = ('緯度', 'lat', 'latitude')
LNG_KEYS = ('經度', 'lng', 'lon', 'longitude')


def decode_csv(raw):
    """依序嘗試 UTF-8（含 BOM）與 Big5 解碼。"""
    for enc in ('utf-8-sig', 'big5'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError('無法判斷 CSV 編碼，請另存為 UTF-8')


def _find_col(header, keys):
    for i, h in enumerate(header):
        if h.strip().lower() in keys:
            return i
    return None


def csv_to_points(raw):
    """回傳 [(名稱, lon, lat)]；欄位缺漏或座標格式錯誤時丟出 ValueError（訊息可直接顯示）。"""
    rows = list(csv.reader(io.StringIO(decode_csv(raw))))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ValueError('CSV 是空的')
    header = rows[0]
    ni, yi, xi = (_find_col(header, k) for k in (NAME_KEYS, LAT_KEYS, LNG_KEYS))
    missing = [label for label, idx in (('名稱', ni), ('緯度', yi), ('經度', xi)) if idx is None]
    if missing:
        raise ValueError('CSV 缺少欄位：' + '、'.join(missing) + '（需要「名稱,緯度,經度」）')
    points = []
    for n, row in enumerate(rows[1:], 2):
        try:
            lat, lon = float(row[yi]), float(row[xi])
        except (ValueError, IndexError):
            raise ValueError(f'第 {n} 列的緯度／經度不是數字')
        name = (row[ni].strip() if ni < len(row) else '') or f'地點 {n - 1}'
        points.append((name, lon, lat))
    if not points:
        raise ValueError('CSV 沒有任何地點')
    return points


def points_to_kml(points):
    """[(名稱, lon, lat)] → 與 worker 相容的 KML 字串（名稱已跳脫）。"""
    marks = ''.join(
        f'<Placemark><name>{escape(name)}</name>'
        f'<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>'
        for name, lon, lat in points)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            + marks + '</Document></kml>')
