#!/usr/bin/env python3
# coding: utf-8
"""
Worker daemon — polls /data/jobs/ for pending jobs and queries NCDR risk levels
directly via WMS GetFeatureInfo API (no browser required).
"""

import os
import json
import glob
import time
import math
import csv
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))
def now_tw():
    return datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')

import tempfile
import requests
from bs4 import BeautifulSoup
import folium

_session = requests.Session()
_session.headers.update({'User-Agent': 'ncdr-risk-scanner'})

DATA_DIR    = os.environ.get('DATA_DIR', '/data')
JOBS_DIR    = os.path.join(DATA_DIR, 'jobs')
RESULTS_DIR = os.path.join(DATA_DIR, 'results')
KML_DIR     = os.path.join(DATA_DIR, 'kmls')
KML_NS      = 'http://www.opengis.net/kml/2.2'

TOKEN_URL     = 'https://dra.ncdr.nat.gov.tw/Frontend/Tools/GetToken'
FLOOD_WMS_URL = 'https://dwgis1.ncdr.nat.gov.tw/server/services/MAP0626AR6GWLsFlood/AR6GWLsFlood_TW/MapServer/WMSServer'
LAND_WMS_URL  = 'https://dwgis1.ncdr.nat.gov.tw/server/services/MAP0626AR6GWLsLand/AR6GWLsLand_TW/MapServer/WMSServer'
SCENARIO_LAYERS = {
    '1.5C': '68',
    '2C':   '43',
    '4C':   '20',
}
DEFAULT_SCENARIO = '2C'

RISK_COLORS = {
    '第一級': '#CACABA',
    '第二級': '#CAB453',
    '第三級': '#CA7D1D',
    '第四級': '#CA3B00',
    '第五級': '#9F0000',
}
RISK_LEVELS = {1: '第一級', 2: '第二級', 3: '第三級', 4: '第四級', 5: '第五級'}

for d in [JOBS_DIR, RESULTS_DIR, KML_DIR]:
    os.makedirs(d, exist_ok=True)

_seed = '/app/test.kml'
if os.path.exists(_seed) and not os.path.exists(os.path.join(KML_DIR, 'test.kml')):
    import shutil
    shutil.copy(_seed, os.path.join(KML_DIR, 'test.kml'))


# ── Token 管理 ────────────────────────────────────────────

_token = None
_token_expires = 0
TOKEN_TTL = 50 * 60  # 50 分鐘（官方 55 分鐘，留緩衝）

def get_token():
    global _token, _token_expires
    if _token and time.time() < _token_expires:
        return _token
    for attempt in range(3):
        try:
            print("取得 NCDR token...")
            r = _session.get(TOKEN_URL, timeout=10)
            r.raise_for_status()
            _token = r.text.strip()
            _token_expires = time.time() + TOKEN_TTL
            print(f"token 取得成功（有效至 {datetime.fromtimestamp(_token_expires).strftime('%H:%M:%S')}）")
            return _token
        except Exception as e:
            if attempt < 2:
                print(f"token 取得失敗（第 {attempt+1} 次）：{e}，重試中...")
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"無法取得 NCDR token：{e}") from e


# ── 座標轉換 ─────────────────────────────────────────────

def to_3857(lat, lon):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


# ── WMS 查詢通用函式 ──────────────────────────────────────

def _wms_query(url, lat, lon, layer):
    token = get_token()
    cx, cy = to_3857(lat, lon)
    d = 200
    params = {
        'REQUEST': 'GetFeatureInfo', 'SERVICE': 'WMS', 'VERSION': '1.3.0',
        'LAYERS': layer, 'QUERY_LAYERS': layer, 'STYLES': '',
        'CRS': 'EPSG:3857',
        'BBOX': f'{cx-d},{cy-d},{cx+d},{cy+d}',
        'WIDTH': '101', 'HEIGHT': '101', 'I': '50', 'J': '50',
        'INFO_FORMAT': 'text/html', 'TOKEN': token,
    }
    for attempt in range(3):
        try:
            r = _session.get(url, params=params, timeout=20)
            r.encoding = 'utf-8'
            rows = BeautifulSoup(r.text, 'html.parser').find_all('tr')
            if len(rows) >= 2:
                headers = [td.get_text(strip=True) for td in rows[0].find_all(['th', 'td'])]
                values  = [td.get_text(strip=True) for td in rows[1].find_all(['th', 'td'])]
                return dict(zip(headers, values))
            return {}
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"    WMS 查詢失敗（第 {attempt+1} 次），{wait}s 後重試：{e}")
                time.sleep(wait)
            else:
                raise


def _parse_level(val):
    try:
        n = int(float(val))
        return RISK_LEVELS.get(n, '無')
    except (ValueError, TypeError):
        return '無'


# ── 風險查詢 ─────────────────────────────────────────────

def query_risk(lat, lon, scenario=DEFAULT_SCENARIO):
    layer = SCENARIO_LAYERS.get(scenario, SCENARIO_LAYERS[DEFAULT_SCENARIO])
    flood = _wms_query(FLOOD_WMS_URL, lat, lon, layer)
    land  = _wms_query(LAND_WMS_URL,  lat, lon, layer)

    result = {
        'flood_risk':        _parse_level(flood.get('眾數_R')),
        'flood_hazard':      _parse_level(flood.get('眾數_H')),
        'flood_vuln':        _parse_level(flood.get('v_lv')),
        'flood_hazard_vuln': _parse_level(flood.get('眾數_HV')),
        'flood_exposure':    _parse_level(flood.get('e1_lv')),
        'land_hazard':       _parse_level(land.get('眾數_H')),
        'land_hazard_vuln':  _parse_level(land.get('眾數_HV')),
    }

    # 地圖顏色以淹水風險為主
    main_level = result['flood_risk']
    result['level'] = main_level
    result['color'] = RISK_COLORS.get(main_level, '#888888')
    return result


# ── KML 解析 ─────────────────────────────────────────────

def parse_kml(kml_path):
    tree = ET.parse(kml_path)
    root = tree.getroot()
    ns = {'kml': KML_NS}
    entries = []
    for pm in root.findall('.//kml:Placemark', ns):
        name_tag = pm.find('kml:name', ns)
        name = name_tag.text if name_tag is not None else '未命名'
        point = pm.find('.//kml:Point/kml:coordinates', ns)
        if point is not None:
            lon, lat, *_ = map(float, point.text.strip().split(','))
            entries.append({'name': name, 'lon': lon, 'lat': lat})
    return entries


# ── 結果輸出 ─────────────────────────────────────────────

CSV_FIELDS = [
    ('name',             '地點名稱'),
    ('lon',              '經度'),
    ('lat',              '緯度'),
    ('flood_risk',       '淹水風險'),
    ('flood_hazard',     '淹水危害度'),
    ('flood_vuln',       '淹水脆弱度'),
    ('flood_hazard_vuln','淹水危害脆弱度'),
    ('flood_exposure',   '淹水暴露度'),
    ('land_hazard',      '坡地危害度'),
    ('land_hazard_vuln', '坡地危害脆弱度'),
]

def save_results(results, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, 'results.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([label for _, label in CSV_FIELDS])
        for r in results:
            writer.writerow([r.get(key, '') for key, _ in CSV_FIELDS])

    if not results:
        return

    center_lat = sum(r['lat'] for r in results) / len(results)
    center_lon = sum(r['lon'] for r in results) / len(results)
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    for r in results:
        popup_html = (
            f"<b>{r['name']}</b><br>"
            f"淹水風險：{r['flood_risk']}<br>"
            f"淹水危害度：{r['flood_hazard']}<br>"
            f"淹水脆弱度：{r['flood_vuln']}<br>"
            f"淹水危害脆弱度：{r['flood_hazard_vuln']}<br>"
            f"淹水暴露度：{r['flood_exposure']}<br>"
            f"坡地危害度：{r['land_hazard']}<br>"
            f"坡地危害脆弱度：{r['land_hazard_vuln']}"
        )
        folium.CircleMarker(
            location=[r['lat'], r['lon']],
            radius=10,
            color=r['color'],
            fill=True,
            fill_color=r['color'],
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{r['name']}｜淹水風險：{r['flood_risk']}",
        ).add_to(m)
    m.save(os.path.join(output_dir, 'map.html'))


def _write_job(job_file, job):
    """原子寫入：先寫暫存檔再 rename，避免讀到寫到一半的 JSON。"""
    tmp = job_file + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(job, f, ensure_ascii=False)
    os.replace(tmp, job_file)


# ── 工作處理 ─────────────────────────────────────────────

def process_job(job_file):
    with open(job_file, encoding='utf-8') as f:
        job = json.load(f)

    job_id   = job['id']
    kml_path = job['kml_path']
    print(f"[{job_id}] 處理 {job['kml_name']}")

    job['status']  = 'running'
    job['started'] = now_tw()
    _write_job(job_file, job)

    try:
        entries = parse_kml(kml_path)  # 在 try 內，失敗會正確設為 error
        print(f"[{job_id}] {len(entries)} 個地點")

        results = []
        for entry in entries:
            scenario = job.get('scenario', DEFAULT_SCENARIO)
            try:
                risk = query_risk(entry['lat'], entry['lon'], scenario)
                print(f"  {entry['name']} → 淹水:{risk['flood_risk']} 坡地H:{risk['land_hazard']}")
                results.append({**entry, **risk})
            except Exception as e:
                print(f"  {entry['name']} 錯誤: {e}")
                results.append({**entry, 'level': '錯誤', 'color': '#000000',
                                 'flood_risk': '錯誤', 'flood_hazard': '錯誤',
                                 'flood_vuln': '錯誤', 'flood_hazard_vuln': '錯誤',
                                 'flood_exposure': '錯誤', 'land_hazard': '錯誤',
                                 'land_hazard_vuln': '錯誤'})

        save_results(results, os.path.join(RESULTS_DIR, job_id))

        job['status']   = 'done'
        job['finished'] = now_tw()
        job['count']    = len(results)
        job['summary']  = {lvl: sum(1 for r in results if r.get('flood_risk') == lvl)
                           for lvl in ['第五級', '第四級', '第三級', '第二級', '第一級', '無', '錯誤']}
        job['results']  = [{**{k: r.get(k, '無') for k in
                            ['name', 'lat', 'lon', 'flood_risk', 'flood_hazard',
                             'flood_vuln', 'flood_hazard_vuln', 'flood_exposure',
                             'land_hazard', 'land_hazard_vuln']},
                            'scenario': job.get('scenario', DEFAULT_SCENARIO)}
                           for r in results]

    except Exception as e:
        print(f"[{job_id}] 失敗: {e}")
        job['status'] = 'error'
        job['error']  = str(e)

    _write_job(job_file, job)
    print(f"[{job_id}] 完成")


def _cleanup_old_jobs(keep=100):
    """保留最新 keep 筆，其餘連同 results 一併刪除。"""
    import shutil
    all_jobs = sorted(glob.glob(os.path.join(JOBS_DIR, '*.json')))
    to_delete = all_jobs[:-keep] if len(all_jobs) > keep else []
    for job_file in to_delete:
        try:
            with open(job_file, encoding='utf-8') as f:
                job_id = json.load(f).get('id', '')
            os.remove(job_file)
            result_dir = os.path.join(RESULTS_DIR, job_id)
            if job_id and os.path.isdir(result_dir):
                shutil.rmtree(result_dir)
        except Exception as e:
            print(f"清除舊工作失敗 {job_file}: {e}")
    if to_delete:
        print(f"已清除 {len(to_delete)} 筆舊記錄")


print("Worker 啟動（API 模式），監聽工作佇列...")
_cleanup_cycle = 0
while True:
    for job_file in sorted(glob.glob(os.path.join(JOBS_DIR, '*.json'))):
        try:
            with open(job_file, encoding='utf-8') as f:
                job = json.load(f)
            if job.get('status') == 'pending':
                process_job(job_file)
        except Exception as e:
            print(f"讀取工作失敗 {job_file}: {e}")
    _cleanup_cycle += 1
    if _cleanup_cycle >= 50:  # 每 ~100 秒清一次
        _cleanup_old_jobs()
        _cleanup_cycle = 0
    time.sleep(2)
