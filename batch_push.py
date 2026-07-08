import sqlite3, httpx, json, time, sys
from collections import defaultdict

DB = "/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db"
URL = "https://www.ct256.cn/funds-v2/api/external/push"
HEADERS = {"X-API-Key": "funds-v2-ext-2026", "Content-Type": "application/json"}

STORE_MAP = {
    "B级汇总1": "一店", "B级汇总2": "二店", "B级汇总3": "三店",
    "B级汇总4": "四店", "B级汇总5": "五店", "B级汇总6": "六店",
}

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

rows = db.execute("""
    SELECT date, summary_name, total_value, draw_value_rank 
    FROM daily_snapshots 
    WHERE collection_id=19 AND summary_name IN (?,?,?,?,?,?)
    ORDER BY date
""", list(STORE_MAP.keys())).fetchall()

db.close()

by_date = defaultdict(list)
for r in rows:
    by_date[r["date"]].append(dict(r))

dates = sorted(by_date.keys())
total = len(dates)
pushed = 0
skipped = 0
errors = 0

print(f"共 {total} 天, {sum(len(v) for v in by_date.values())} 条汇总", flush=True)

BATCH = 8

for i in range(0, total, BATCH):
    batch_dates = dates[i:i+BATCH]
    records = []
    for d in batch_dates:
        for s in by_date[d]:
            store = STORE_MAP.get(s["summary_name"])
            if not store: continue
            amount = s["total_value"] or 0
            rank = s["draw_value_rank"] or 0
            records.append({
                "id": f"{d}-{s['summary_name']}-income",
                "store": store, "date": d, "category": "income",
                "amount": amount, "note": f"排位 {rank}"
            })
            records.append({
                "id": f"{d}-{s['summary_name']}-cat",
                "store": store, "date": d, "category": "cat_1783487972049",
                "amount": rank, "note": f"排位 {rank}  ·  ¥{amount:,.0f}"
            })
    
    try:
        resp = httpx.post(URL, json={"records": records}, headers=HEADERS, timeout=30)
        data = resp.json()
        pushed += data.get("records", 0)
        skipped += len(records) - data.get("records", 0)
        
        if i % 160 == 0:
            pct = round(i / total * 100)
            print(f"[{pct}%] {batch_dates[0]}  pushed={pushed}", flush=True)
    except Exception as e:
        errors += 1
        print(f"ERROR {batch_dates[0]}: {e}", flush=True)
    
    time.sleep(0.3)

print(f"\nDone. pushed={pushed} skipped={skipped} errors={errors}", flush=True)
