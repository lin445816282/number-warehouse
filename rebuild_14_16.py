#!/usr/bin/env python3
"""全量重建集合14/16的daily_snapshots，排位从集合19直读"""
import sqlite3, time

DB = '/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db'
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# 1. 获取集合19所有日期的快照（含排位）
t0 = time.time()
src = db.execute('''
    SELECT date, summary_name, total_value, draw_value_rank, draw_number
    FROM daily_snapshots WHERE collection_id=19
    ORDER BY date, summary_id
''').fetchall()
print(f'读取集合19: {len(src)}行 ({time.time()-t0:.1f}s)')

# 2. 清空14/16
db.execute('DELETE FROM daily_snapshots WHERE collection_id IN (14,16)')
db.execute('DELETE FROM daily_grid_snapshots WHERE collection_id IN (14,16)')
db.execute('DELETE FROM daily_project_snapshots WHERE collection_id IN (14,16)')
print(f'清空14/16完成')

# 3. 按日期分组
from collections import defaultdict
by_date = defaultdict(list)
for r in src:
    by_date[r['date']].append(r)

# 4. 获取summary_id映射
sids = {}
for r in db.execute('SELECT id, name, collection_id FROM summaries WHERE collection_id IN (14,16)'):
    sids[(r['collection_id'], r['name'])] = r['id']

# 确保14/16的summary存在
for cid in [14,16]:
    max_n = 4 if cid == 14 else 6
    for i in range(1, max_n + 1):
        name = f'当日汇总{i}'
        if (cid, name) not in sids:
            cur = db.execute('INSERT INTO summaries (name, collection_id) VALUES (?,?)', (name, cid))
            sids[(cid, name)] = cur.lastrowid
db.commit()

# 5. 批量插入
t0 = time.time()
batch = []
for date, rows in sorted(by_date.items()):
    dn = rows[0]['draw_number']
    for cid in [14, 16]:
        max_n = 4 if cid == 14 else 6
        for i, r in enumerate(rows):
            if i >= max_n:
                break
            name = f'当日汇总{i+1}'
            sid = sids.get((cid, name))
            if not sid:
                continue
            batch.append((date, cid, dn, sid, name, 0, 0, r['total_value'], r['draw_value_rank']))

db.executemany('''
    INSERT OR REPLACE INTO daily_snapshots 
    (date, collection_id, draw_number, summary_id, summary_name, projects, hit_rate, total_value, draw_value_rank)
    VALUES (?,?,?,?,?,?,?,?,?)
''', batch)
db.commit()
print(f'插入 {len(batch)}行 ({time.time()-t0:.1f}s)')

# 6. 验证
for cid in [14,16]:
    cnt = db.execute('SELECT COUNT(*) FROM daily_snapshots WHERE collection_id=?', (cid,)).fetchone()[0]
    print(f'集合{cid}: {cnt}行')

db.close()
print('完成')
