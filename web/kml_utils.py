"""KML 座標檢查：純函式，不依賴 Flask，方便單獨測試。"""
import xml.etree.ElementTree as ET

KML_NS = '{http://www.opengis.net/kml/2.2}'
# 台灣含離島的粗略邊界框
LON_RANGE = (118.0, 123.0)
LAT_RANGE = (21.5, 26.5)


def _in_taiwan(lon, lat):
    return LON_RANGE[0] <= lon <= LON_RANGE[1] and LAT_RANGE[0] <= lat <= LAT_RANGE[1]


def check_coord(lon, lat):
    """檢查單一座標；正常回傳 None，否則回傳原因字串。"""
    if _in_taiwan(lon, lat):
        return None
    if _in_taiwan(lat, lon):
        return '經緯度疑似顛倒'
    return '座標超出台灣範圍'


def check_points(points):
    """points: [(名稱, lon, lat)]；回傳 [{'name', 'reason'}]。"""
    warnings, seen = [], {}
    for name, lon, lat in points:
        reason = check_coord(lon, lat)
        if reason:
            warnings.append({'name': name, 'reason': reason})
        key = (round(lon, 6), round(lat, 6))
        if key in seen:
            warnings.append({'name': name, 'reason': f'座標與「{seen[key]}」重複'})
        else:
            seen[key] = name
    return warnings


def extract_points(root):
    """從 KML 根節點取出 Point 地點 [(名稱, lon, lat)]，格式錯誤的座標略過。"""
    points = []
    for i, pm in enumerate(root.iter(KML_NS + 'Placemark'), 1):
        coords = pm.find(f'.//{KML_NS}Point/{KML_NS}coordinates')
        if coords is None or not (coords.text or '').strip():
            continue
        parts = coords.text.strip().split(',')
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            continue
        name = (pm.findtext(KML_NS + 'name') or '').strip() or f'地點 {i}'
        points.append((name, lon, lat))
    return points


def kml_warnings(path):
    """解析 KML 檔並回傳座標警示清單；解析失敗回傳空清單（交給 worker 處理）。"""
    try:
        return check_points(extract_points(ET.parse(path).getroot()))
    except ET.ParseError:
        return []
