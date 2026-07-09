#!/usr/bin/env python3
"""全量同步14/16到funds-v2门店"""
import sqlite3, httpx, time, json

DB = '/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db'
FV = 'http://localhost:8009/api/external/push'
API_KEY = 'funds-v2-ext-2026'

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# 清除funds-v2旧记录
print('清除funds-v2旧数据...')
r = httpx.post(FV, json={"records": [{"id":"_bulk_clear_","store":"一店","date":"2020-01-01","category":"income","amount":0,"note":"clear"}]}, headers={"X-API-Key":API_KEY}, timeout=10)
print(f'  回应: {r.json()}')

# 先查funds-v2有哪些记录（按店筛选需直接操作DB）
FV_DB = '/home/xiaolin/projects/funds-v2/backend/funds-v2.db'
fvdb = sqlite3.connect(FV_DB)
old_cnt = fvdb.execute("SELECT COUNT(*) FROM records WHERE store LIKE '%店' OR store LIKE '%集合%'").fetchone()[0]
print(f'funds-v2旧记录: {old_cnt}条')
fvdb.execute("DELETE FROM records WHERE store LIKE '%店' OR store LIKE '%集合%'")
fvdb.commit()
fvdb.close()
print('已清空')

# 读取14/16所有快照
STORE_MAP = {
    "当日汇总1":"一店","当日汇总2":"二店","当日汇总3":"三店",
    "当日汇总4":"四店","当日汇总5":"五店","当日汇总6":"六店",
}
DIR_STORE = {14:"集合14", 16:"集合16"}

t0 = time.time()
rows = db.execute('''
    SELECT date, collection_id, summary_name, total_value, draw_value_rank
    FROM daily_snapshots WHERE collection_id IN (14,16)
    ORDER BY date, collection_id, summary_id
''').fetchall()

# 生成所有records
records = []
from collections import defaultdict
coll_total = defaultdict(lambda: [0, None])  # date_cid -> [total, combined_rank]

for r in rows:
    d, cid, name, tv, rank = r['date'], r['collection_id'], r['summary_name'], r['total_value'], r['draw_value_rank']
    store = STORE_MAP.get(name)
    key = f"{d}_{cid}"
    coll_total[key][0] += (tv or 0)
    
    if store:
        records.append({"id":f"{d}-{name}-income","store":store,"date":d,"category":"income","amount":tv or 0,"note":f"排位 {rank}"})
        records.append({"id":f"{d}-{name}-cat","store":store,"date":d,"category":"cat_1783487972049","amount":rank or 0,"note":f"排位 {rank}  ·  ¥{tv:,.0f}" if tv else f"排位 {rank}"})

# 集合总计（用第一个汇总的排位作合集排位）
for r in rows:
    d, cid, name, rank = r['date'], r['collection_id'], r['summary_name'], r['draw_value_rank']
    key = f"{d}_{cid}"
    if coll_total[key][1] is None:
        coll_total[key][1] = rank

for key, (total, crank) in coll_total.items():
    d, cid_str = key.split('_')
    cid = int(cid_str)
    store = DIR_STORE[cid]
    records.append({"id":f"{d}-col{cid}-income","store":store,"date":d,"category":"income","amount":total,"note":f"集合{cid} 排位{crank}"})
    records.append({"id":f"{d}-col{cid}-cat","store":store,"date":d,"category":"cat_1783487972049","amount":crank or 0,"note":f"集合{cid} 排位{crank} ¥{total:,.0f}"})

print(f'生成 {len(records)} 条记录 ({time.time()-t0:.1f}s)')

# 批量推送（每次1000条）
BATCH = 1000
ok = fail = 0
for i in range(0, len(records), BATCH):
    chunk = records[i:i+BATCH]
    try:
        r = httpx.post(FV, json={"records":chunk}, headers={"X-API-Key":API_KEY}, timeout=60)
        if r.json().get("ok"):
            ok += len(chunk)
        else:
            fail += len(chunk)
    except Exception as e:
        fail += len(chunk)
    if (i//BATCH) % 10 == 0:
        print(f'  进度: {min(i+BATCH, len(records))}/{len(records)}  ok:{ok} fail:{fail}')

print(f'完成: ok={ok} fail={fail}')
db.close()
