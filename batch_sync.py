#!/usr/bin/env python3
"""批量生成集合14/16快照并同步到门店。
用法：
  python3 batch_sync.py 7          # 先跑最近7天，验证
  python3 batch_sync.py all        # 跑全部剩余日期
  python3 batch_sync.py 7 --sync   # 跑7天并同步到门店
"""

import sys, time, httpx, sqlite3

NW = "http://localhost:8012"
FV = "http://localhost:8009/api/external/push"
API_KEY = "funds-v2-ext-2026"

def get_dates_to_run(limit=None):
    db = sqlite3.connect('/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db')
    d19 = {r[0] for r in db.execute("SELECT DISTINCT date FROM daily_snapshots WHERE collection_id=19").fetchall()}
    d14 = {r[0] for r in db.execute("SELECT DISTINCT date FROM daily_snapshots WHERE collection_id=14").fetchall()}
    missing = sorted(d19 - d14, reverse=True)
    db.close()
    return missing[:limit] if limit else missing

def save_daily(cid, date):
    try:
        r = httpx.post(f"{NW}/api/export/save-daily?collection_id={cid}&date={date}", timeout=60)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"    ERR: {e}")
        return False

def sync(cid, date):
    db = sqlite3.connect('/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db')
    db.row_factory = sqlite3.Row
    mn = 4 if cid == 14 else 6
    rows = db.execute("SELECT total_value,draw_value_rank FROM daily_snapshots WHERE collection_id=? AND date=? AND summary_name LIKE '当日汇总%'",(cid,date)).fetchall()
    db.close()
    if not rows: return False
    total = sum(r['total_value'] or 0 for i,r in enumerate(rows) if i<mn)
    rank = rows[0]['draw_value_rank']
    records = [
        {"id":f"{date}-c{cid}-inc","store":f"集合{cid}","date":date,"category":"income","amount":total,"note":f"排{rank}"},
        {"id":f"{date}-c{cid}-cat","store":f"集合{cid}","date":date,"category":"cat_1783487972049","amount":rank or 0,"note":f"排{rank} ¥{total:,.0f}"},
    ]
    r = httpx.post(FV, json={"records":records}, headers={"X-API-Key":API_KEY}, timeout=30)
    return r.json().get("ok", False)

def show(dates):
    db = sqlite3.connect('/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db')
    db.row_factory = sqlite3.Row
    for cid in [14,16]:
        rows = db.execute("SELECT date,SUM(total_value) t,draw_value_rank r,draw_number d FROM daily_snapshots WHERE collection_id=? AND date BETWEEN ? AND ? GROUP BY date ORDER BY date DESC",(cid,dates[-1],dates[0])).fetchall()
        print(f"\n集合{cid}:")
        for r in rows:
            print(f"  {r['d']}  ¥{r['t']:>+10,.0f}  排{r['r']:>3}  #{r['d']}")
    db.close()

if __name__ == "__main__":
    do_sync = "--sync" in sys.argv
    arg = [a for a in sys.argv[1:] if not a.startswith("--")][0] if len(sys.argv)>1 else "7"
    
    if arg == "all":
        dates = get_dates_to_run()
        print(f"全部剩余: {len(dates)}天")
    else:
        n = int(arg)
        dates = get_dates_to_run(n)
        print(f"最近{n}天: {dates[-1]} ~ {dates[0]}")
    
    if not dates:
        print("没有需要跑的日期")
        sys.exit(0)
    
    input("按Enter开始...")
    t0 = time.time()
    ok14 = ok16 = sync_ok = 0
    
    for i, d in enumerate(dates):
        r14 = save_daily(14, d)
        r16 = save_daily(16, d)
        if r14: ok14 += 1
        if r16: ok16 += 1
        
        s = ""
        if do_sync and r14 and r16:
            if sync(14, d) and sync(16, d):
                sync_ok += 1
                s = " +sync"
        
        elapsed = time.time() - t0
        eta = (elapsed/(i+1))*(len(dates)-i-1) if i>0 else 0
        print(f"  [{i+1}/{len(dates)}] {d}  14:{'✓'if r14 else'✗'} 16:{'✓'if r16 else'✗'}{s}  {elapsed:.0f}s ETA:{eta:.0f}s")
    
    elapsed = time.time() - t0
    print(f"\n完成: {elapsed:.0f}s | 14:{ok14} 16:{ok16}", end="")
    if do_sync: print(f" 同步:{sync_ok}天")
    else: print()
    show(dates)
