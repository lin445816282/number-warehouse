#!/usr/bin/env python3
import sys, sqlite3, time, json, os
sys.stdout = open('/tmp/batch_push.log', 'w', buffering=1)
sys.stderr = sys.stdout

import urllib.request
import httpx

DB = "/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db"
STORE_URL = "https://www.ct256.cn/funds-v2/api/external/push"
API_KEY = "funds-v2-ext-2026"
STORE_MAP = {"B级汇总1":"一店","B级汇总2":"二店","B级汇总3":"三店","B级汇总4":"四店","B级汇总5":"五店","B级汇总6":"六店"}

print("=== 开始 ===")
db = sqlite3.connect(DB)
dates = [r[0] for r in db.execute("SELECT DISTINCT date FROM records ORDER BY date").fetchall()]
db.close()
total = len(dates)
print(f"共 {total} 天")

print("--- 保存快照 ---")
t0 = time.time()
for i, d in enumerate(dates):
    try:
        req = urllib.request.Request(f"http://localhost:8012/api/export/save-daily?collection_id=19&date={d}", method="POST")
        urllib.request.urlopen(req, timeout=30).read()
    except: pass
    if i % 200 == 0:
        elapsed = time.time()-t0
        eta = elapsed/(i+1)*total - elapsed if i>0 else 0
        print(f"  {i}/{total} ({round(i/total*100)}%) {d}  已用{elapsed:.0f}s 预计剩余{eta:.0f}s")

print(f"快照完成, 用时{time.time()-t0:.0f}s")

print("--- 推送到门店 ---")
t0 = time.time()
success = fail = 0
BATCH = 16
for i in range(0, total, BATCH):
    batch = dates[i:i+BATCH]
    db = sqlite3.connect(DB)
    rows = db.execute(
        "SELECT date, summary_name, SUM(value) FROM daily_project_snapshots "
        "WHERE collection_id=19 AND date IN ({}) GROUP BY date, summary_name ORDER BY date, summary_name"
        .format(",".join("?"*len(batch))), batch).fetchall()
    db.close()
    records = []
    for r in rows:
        s = STORE_MAP.get(r[1])
        if s:
            records.append({"id":f"{r[0]}-{r[1]}","store":s,"date":r[0],"category":"income","amount":r[2] or 0,"note":""})
    if not records: continue
    try:
        resp = httpx.post(STORE_URL, json={"records":records}, headers={"X-API-Key":API_KEY}, timeout=60)
        if resp.status_code == 200:
            n = resp.json().get("records",0)
            success += n
            print(f"  [{round((i+BATCH)/total*100)}%] {batch[0]}~{batch[-1]}: {len(records)}条→{n}")
        else:
            fail += len(records)
            print(f"  ❌ {batch[0]} HTTP {resp.status_code}")
    except Exception as e:
        fail += len(records)
        print(f"  ❌ {batch[0]}: {e}")
    time.sleep(0.3)

print(f"\n✅ 推送完成 入库{success} 失败{fail} 用时{time.time()-t0:.0f}s")
print("=== 结束 ===")
