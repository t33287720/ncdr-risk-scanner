# coding: utf-8
"""WMS 查詢結果快取（JSON 檔，純標準函式庫，方便單元測試）。"""
import json
import os
import time

MAX_ENTRIES = 5000


class WmsCache:
    def __init__(self, path, days=7, max_entries=MAX_ENTRIES, clock=time.time):
        self.path = path
        self.ttl = days * 86400
        self.max_entries = max_entries
        self.clock = clock
        self.hits = 0
        self.data = self._load() if self.enabled else {}
        self.purge_expired()

    @property
    def enabled(self):
        return self.ttl > 0

    @staticmethod
    def key(lat, lon, scenario):
        return f'{round(float(lat), 5)},{round(float(lon), 5)},{scenario}'

    def _load(self):
        try:
            with open(self.path, encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def purge_expired(self):
        now = self.clock()
        before = len(self.data)
        self.data = {k: v for k, v in self.data.items()
                     if isinstance(v, dict) and now - v.get('t', 0) < self.ttl
                     and isinstance(v.get('r'), dict)}
        if len(self.data) != before:
            self.save()

    def get(self, lat, lon, scenario):
        if not self.enabled:
            return None
        entry = self.data.get(self.key(lat, lon, scenario))
        if entry is None or self.clock() - entry['t'] >= self.ttl:
            return None
        self.hits += 1
        return dict(entry['r'])

    def put(self, lat, lon, scenario, result):
        if not self.enabled:
            return
        self.data[self.key(lat, lon, scenario)] = {'t': self.clock(), 'r': result}
        if len(self.data) > self.max_entries:
            oldest = sorted(self.data, key=lambda k: self.data[k]['t'])
            for k in oldest[:len(self.data) - self.max_entries]:
                del self.data[k]
        self.save()

    def save(self):
        if not self.enabled:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass
