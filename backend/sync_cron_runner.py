#!/usr/bin/env python3
"""读 sync_cron.json 的时间，调同步接口（集合19 + 14 + 16）"""
import json, os, urllib.request
from datetime import date, timedelta

CONFIG = os.path.join(os.path.dirname(__file__), "sync_cron.json")

today = date.today()
target_date = (today - timedelta(days=1)).isoformat()

for cid in (19, 14, 16):
    url = f"http://localhost:8012/api/export/sync-store?collection_id={cid}&date={target_date}"
    try:
        req = urllib.request.Request(url, method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        ok = "✓" if data.get("ok") else "✗"
        print(f"集合{cid} {ok}: {data.get('records',0)}条")
    except Exception as e:
        print(f"集合{cid} ✗: {e}")

cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {"hour": 2, "minute": 0}
