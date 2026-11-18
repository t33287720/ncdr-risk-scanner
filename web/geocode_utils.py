"""地址轉座標：Photon 優先、Nominatim 備援。限速、本機 JSON 快取。

網路請求由呼叫端注入的 http_get(url, params) 完成（回傳 JSON），方便測試時換成假的回應。
"""
import json
import os
import time

PHOTON_URL = 'https://photon.komoot.io/api/'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
MIN_INTERVAL = 1.1  # 秒；Nominatim 政策約每秒 1 次
CACHE_MAX = 5000


def _photon(addr, http_get):
    data = http_get(PHOTON_URL, {'q': addr, 'lang': 'default', 'limit': 1, 'bbox': '118,21,123,27'})
    feats = (data or {}).get('features') or []
    if not feats:
        return None
    lon, lat = feats[0]['geometry']['coordinates'][:2]
    return float(lat), float(lon)


def _nominatim(addr, http_get):
    data = http_get(NOMINATIM_URL, {'q': addr, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'tw'})
    if not data:
        return None
    return float(data[0]['lat']), float(data[0]['lon'])


def geocode_one(addr, http_get):
    """回傳 (lat, lon) 或 None；任何一個服務失敗就換下一個。"""
    for fn in (_photon, _nominatim):
        try:
            res = fn(addr, http_get)
        except Exception:
            res = None
        if res:
            return res
    return None


def load_cache(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(path, cache):
    if len(cache) > CACHE_MAX:  # 淘汰最舊（dict 保留插入順序）
        cache = dict(list(cache.items())[-CACHE_MAX:])
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def geocode_rows(pending, http_get, cache_path, sleep=time.sleep):
    """pending：[(名稱, 地址)]。回傳 (points, failed)。

    points：[(名稱, lon, lat)]；failed：[(名稱, 地址)]。
    只快取成功的結果；命中快取不需等待，真正打外部服務的請求之間才限速。
    """
    cache = load_cache(cache_path)
    points, failed = [], []
    last_call = None
    for name, addr in pending:
        hit = cache.get(addr)
        if hit:
            lat, lon = hit
        else:
            if last_call is not None:
                wait = MIN_INTERVAL - (time.monotonic() - last_call)
                if wait > 0:
                    sleep(wait)
            res = geocode_one(addr, http_get)
            last_call = time.monotonic()
            if not res:
                failed.append((name, addr))
                continue
            lat, lon = res
            cache[addr] = [lat, lon]
        points.append((name, lon, lat))
    save_cache(cache_path, cache)
    return points, failed
