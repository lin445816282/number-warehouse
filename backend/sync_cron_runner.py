#!/usr/bin/env python3
"""读 sync_cron.json 的时间，调同步接口"""
import json, os, urllib.request

CONFIG = os.path.join(os.path.dirname(__file__), "sync_cron.json")

# 检查是否到了配置的时间
cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {"hour": 2, "minute": 0}
url = f"http://localhost:8012/api/export/sync-store?collection_id=19&date={__import__('datetime').date.today().__sub__(__import__('datetime').timedelta(days=1)).isoformat()}"
try:
    req = urllib.request.Request(url, method="POST")
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    print(json.dumps(data, ensure_ascii=False))
except Exception as e:
    print(f"ERROR: {e}")
