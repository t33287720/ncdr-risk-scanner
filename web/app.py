import os
import json
import uuid
import glob
import time
import csv as csv_mod
import requests as _requests
from datetime import datetime, timezone, timedelta

OLLAMA_URL   = os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.1:8b')

TW_TZ = timezone(timedelta(hours=8))
def now_tw():
    return datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

_prefix = os.environ.get('SCRIPT_NAME', '')
if _prefix:
    from werkzeug.middleware.proxy_fix import ProxyFix
    class _PrefixMiddleware:
        def __init__(self, wsgi_app):
            self.wsgi_app = wsgi_app
        def __call__(self, environ, start_response):
            environ['SCRIPT_NAME'] = _prefix
            path = environ.get('PATH_INFO', '')
            if path.startswith(_prefix):
                environ['PATH_INFO'] = path[len(_prefix):]
            return self.wsgi_app(environ, start_response)
    app.wsgi_app = _PrefixMiddleware(app.wsgi_app)

_STATIC_VER = str(int(time.time()))

@app.context_processor
def inject_ver():
    return {'ver': _STATIC_VER}

_LEVEL_CLASS = {'第一級':'lv1','第二級':'lv2','第三級':'lv3','第四級':'lv4','第五級':'lv5'}

@app.template_filter('risk_badge')
def risk_badge(val):
    from markupsafe import Markup
    if not val or val in ('—', '無', '無資料'):
        return Markup('<span class="risk-badge lv0">—</span>')
    cls = _LEVEL_CLASS.get(val, 'lv-err')
    return Markup(f'<span class="risk-badge {cls}">{val}</span>')

DATA_DIR    = os.environ.get('DATA_DIR', '/data')
KML_DIR     = os.path.join(DATA_DIR, 'kmls')
POINTS_DIR  = os.path.join(DATA_DIR, 'points')   # 快速查詢暫存，不顯示在列表
RESULTS_DIR = os.path.join(DATA_DIR, 'results')
JOBS_DIR    = os.path.join(DATA_DIR, 'jobs')

for d in [KML_DIR, POINTS_DIR, RESULTS_DIR, JOBS_DIR]:
    os.makedirs(d, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────

def _load_jobs(limit=50):
    jobs = []
    for f in glob.glob(os.path.join(JOBS_DIR, '*.json')):
        try:
            with open(f, encoding='utf-8') as fh:
                jobs.append(json.load(fh))
        except Exception:
            pass
    # 依建立時間排序（最新的在前），取前 limit 筆
    jobs.sort(key=lambda j: j.get('created', ''), reverse=True)
    return jobs[:limit]


def _points_to_kml(points):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
    ]
    for p in points:
        name = str(p.get('name', '未命名')).replace('&', '&amp;').replace('<', '&lt;')
        lines.append(
            f'  <Placemark><name>{name}</name>'
            f'<Point><coordinates>{p["lon"]},{p["lat"]},0</coordinates></Point>'
            f'</Placemark>'
        )
    lines.append('</Document></kml>')
    return '\n'.join(lines)


VALID_SCENARIOS = {'1.5C', '2C', '4C'}
SCENARIO_LABELS = {'1.5C': '1.5°C', '2C': '2°C', '4C': '4°C'}

def _create_job(kml_name, scenario='2C'):
    return _create_job_with_path(kml_name, os.path.join(KML_DIR, kml_name), scenario, 'batch')

def _create_job_with_path(kml_name, kml_path, scenario='2C', job_type='point'):
    scenario = scenario if scenario in VALID_SCENARIOS else '2C'
    job_id = uuid.uuid4().hex[:8]
    job = {
        'id':       job_id,
        'kml_name': kml_name,
        'kml_path': kml_path,
        'scenario': scenario,
        'type':     job_type,
        'status':   'pending',
        'created':  now_tw(),
    }
    with open(os.path.join(JOBS_DIR, f'{job_id}.json'), 'w', encoding='utf-8') as f:
        json.dump(job, f, ensure_ascii=False)
    return job_id


# ── Pages ─────────────────────────────────────────────────

@app.route('/')
def index():
    kmls = []
    for f in sorted(glob.glob(os.path.join(KML_DIR, '*.kml'))):
        name = os.path.basename(f)
        kmls.append({
            'name':     name,
            'size':     os.path.getsize(f),
            'modified': datetime.fromtimestamp(os.path.getmtime(f), tz=TW_TZ).strftime('%Y-%m-%d %H:%M'),
        })
    jobs = _load_jobs()
    batch_jobs = [j for j in jobs if j.get('status') == 'done'
                  and j.get('type', 'batch') == 'batch'
                  and j.get('results')]
    map_jobs = [j for j in jobs if j.get('status') == 'done' and j.get('results')]
    return render_template('index.html', kmls=kmls, jobs=jobs,
                           batch_jobs=batch_jobs, map_jobs=map_jobs)


@app.route('/map-query')
def map_query():
    return render_template('map_query.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/results/<job_id>')
def results(job_id):
    job_file = os.path.join(JOBS_DIR, f'{job_id}.json')
    if not os.path.exists(job_file):
        abort(404)
    with open(job_file, encoding='utf-8') as f:
        job = json.load(f)
    rows = []
    csv_path = os.path.join(RESULTS_DIR, job_id, 'results.csv')
    if os.path.exists(csv_path):
        with open(csv_path, encoding='utf-8-sig') as f:
            rows = list(csv_mod.DictReader(f))
    scenario_label = SCENARIO_LABELS.get(job.get('scenario', '2C'), '2°C')
    return render_template('results.html', job=job, rows=rows, scenario_label=scenario_label)


@app.route('/results/<job_id>/map')
def results_map(job_id):
    path = os.path.join(RESULTS_DIR, job_id, 'map.html')
    if not os.path.exists(path):
        abort(404)
    return send_file(path)


@app.route('/results/<job_id>/csv')
def results_csv(job_id):
    path = os.path.join(RESULTS_DIR, job_id, 'results.csv')
    if not os.path.exists(path):
        abort(404)
    job_file = os.path.join(JOBS_DIR, f'{job_id}.json')
    with open(job_file, encoding='utf-8') as f:
        job = json.load(f)
    return send_file(path, as_attachment=True,
                     download_name=f"{job.get('kml_name', job_id)}_results.csv")


# ── API ───────────────────────────────────────────────────

KML_MAX_POINTS = 200

@app.route('/api/upload', methods=['POST'])
def upload_kml():
    if 'file' not in request.files:
        return jsonify({'error': '沒有上傳檔案'}), 400
    f = request.files['file']
    name = secure_filename(f.filename)
    if not name.lower().endswith('.kml'):
        return jsonify({'error': '只接受 .kml 檔案'}), 400
    path = os.path.join(KML_DIR, name)
    f.save(path)
    # 檢查地點數量
    import xml.etree.ElementTree as ET
    try:
        count = len(ET.parse(path).findall('.//{http://www.opengis.net/kml/2.2}Point'))
        if count > KML_MAX_POINTS:
            os.remove(path)
            return jsonify({'error': f'KML 包含 {count} 個地點，上限為 {KML_MAX_POINTS} 個'}), 400
    except Exception:
        pass  # 解析失敗讓 worker 處理
    return jsonify({'ok': True, 'name': name})


@app.route('/api/delete-kml', methods=['POST'])
def delete_kml():
    name = secure_filename((request.json or {}).get('name', ''))
    path = os.path.join(KML_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({'ok': True})


@app.route('/api/analyze', methods=['POST'])
def analyze():
    data     = request.json or {}
    kml_name = secure_filename(data.get('kml_name', ''))
    kml_path = os.path.realpath(os.path.join(KML_DIR, kml_name))
    if not kml_path.startswith(os.path.realpath(KML_DIR) + os.sep):
        return jsonify({'error': '無效的檔案名稱'}), 400
    if not os.path.exists(kml_path):
        return jsonify({'error': 'KML 不存在'}), 404
    scenario = data.get('scenario', '2C')
    job_id = _create_job(kml_name, scenario)
    return jsonify({'ok': True, 'job_id': job_id})


@app.route('/api/status/<job_id>')
def job_status(job_id):
    job_file = os.path.join(JOBS_DIR, f'{job_id}.json')
    if not os.path.exists(job_file):
        return jsonify({'error': '找不到工作'}), 404
    with open(job_file, encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/save-points', methods=['POST'])
def save_points():
    """Save manually placed map points as a KML file."""
    data     = request.json or {}
    points   = data.get('points', [])
    filename = secure_filename(data.get('filename', 'manual.kml'))
    if not filename.endswith('.kml'):
        filename += '.kml'
    if not points:
        return jsonify({'error': '沒有地點'}), 400

    path = os.path.join(KML_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(_points_to_kml(points))
    return jsonify({'ok': True, 'name': filename})



@app.route('/api/query-point', methods=['POST'])
def query_point():
    """Create a single-point analysis job — saves to points/ (not shown in KML list)."""
    data = request.json or {}
    try:
        lat = float(data.get('lat'))
        lon = float(data.get('lon'))
    except (TypeError, ValueError):
        return jsonify({'error': '無效的座標'}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({'error': '座標超出範圍'}), 400
    label     = data.get('label') or f'{lat:.4f},{lon:.4f}'
    filename  = f'point_{uuid.uuid4().hex[:6]}.kml'
    kml_path  = os.path.join(POINTS_DIR, filename)

    with open(kml_path, 'w', encoding='utf-8') as f:
        f.write(_points_to_kml([{'name': label, 'lat': lat, 'lon': lon}]))

    scenario = data.get('scenario', '2C')
    job_id   = _create_job_with_path(filename, kml_path, scenario)
    return jsonify({'ok': True, 'job_id': job_id})


@app.route('/api/save-point-kml', methods=['POST'])
def save_point_kml():
    """把快速查詢的點另存為 KML（顯示在列表中），以時間戳命名。"""
    data    = request.json or {}
    try:
        lat = float(data.get('lat'))
        lon = float(data.get('lon'))
    except (TypeError, ValueError):
        return jsonify({'error': '無效的座標'}), 400
    label   = data.get('label') or f'{lat:.4f},{lon:.4f}'
    ts      = datetime.now(TW_TZ).strftime('%Y%m%d_%H%M%S')
    filename = secure_filename(f'query_{ts}.kml')

    with open(os.path.join(KML_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(_points_to_kml([{'name': label, 'lat': lat, 'lon': lon}]))

    return jsonify({'ok': True, 'name': filename})


@app.route('/api/ai-analyze/<job_id>', methods=['POST'])
def ai_analyze(job_id):
    job_file = os.path.join(JOBS_DIR, f'{job_id}.json')
    if not os.path.exists(job_file):
        return jsonify({'error': '找不到工作'}), 404
    with open(job_file, encoding='utf-8') as f:
        job = json.load(f)
    if job.get('status') != 'done' or not job.get('results'):
        return jsonify({'error': '分析尚未完成'}), 400

    scenario_labels = {'1.5C': '1.5°C', '2C': '2°C', '4C': '4°C'}
    scenario = scenario_labels.get(job.get('scenario', '2C'), '2°C')
    results  = job['results']

    purpose = (request.json or {}).get('purpose', '選址評估')

    LEVEL_DESC = {
        '第一級': '低風險',
        '第二級': '中低風險',
        '第三級': '中風險',
        '第四級': '中高風險',
        '第五級': '高風險',
        '無':     '無資料',
        '錯誤':   '查詢失敗',
    }
    lines = ['地點名稱 | 淹水風險(整合) | 淹水危害度(強度) | 淹水脆弱度(承受力) | 淹水危害脆弱度 | 淹水暴露度(人口) | 坡地危害度 | 坡地危害脆弱度']
    for r in results:
        row = ' | '.join([
            r.get('name', '—'),
            r.get('flood_risk', '—'),
            r.get('flood_hazard', '—'),
            r.get('flood_vuln', '—'),
            r.get('flood_hazard_vuln', '—'),
            r.get('flood_exposure', '—'),
            r.get('land_hazard', '—'),
            r.get('land_hazard_vuln', '—'),
        ])
        lines.append(row)
    table = '\n'.join(lines)

    prompt = f"""以下是 {len(results)} 個地點在 NCDR「{scenario}暖化情境」下的災害風險資料（第一至五級，五級最高）：

{table}

指標說明：
- 淹水危害度：積水深度與範圍（越高越危險）
- 淹水脆弱度：當地居民承受災害的能力（越高越脆弱，越低代表有能力自我保護）
- 淹水暴露度：受影響的人口密度
- 淹水風險：三者的整合評分
- 坡地危害度：土石流或山崩風險

使用目的：{purpose}

請用繁體中文，針對上述目的，完成以下任務：
1. 比較這些地點的差異，指出哪些地點相對適合、哪些需要避免，說明理由（直接用地點名稱，不要只說「某地點」）。
2. 對最高風險的地點，說明在「{purpose}」情境下具體會發生什麼問題，以及可以採取的對策。
3. 列出 2-3 個做最終決策前需要進一步調查的問題。"""

    try:
        resp = _requests.post(
            f'{OLLAMA_URL}/api/generate',
            json={
                'model': OLLAMA_MODEL,
                'system': '你是一位專業的台灣氣候風險顧問，擅長解讀 NCDR 的災害風險指標並給出具體可行的建議。回答必須精準、有根據、直指問題核心，不說廢話。',
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.3, 'top_p': 0.9},
            },
            timeout=120,
        )
        resp.raise_for_status()
        analysis = resp.json().get('response', '').strip()
        return jsonify({'ok': True, 'analysis': analysis})
    except _requests.exceptions.ConnectionError:
        return jsonify({'error': f'無法連接 Ollama（{OLLAMA_URL}）'}), 503
    except Exception as e:
        app.logger.error(f'AI 分析失敗：{e}')
        return jsonify({'error': 'AI 分析失敗，請稍後再試'}), 500


if __name__ == '__main__':
    dev = os.environ.get('FLASK_DEBUG') == '1'
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=dev)
