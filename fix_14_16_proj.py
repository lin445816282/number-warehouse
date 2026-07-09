#!/usr/bin/env python3
"""给集合14/16填充项目快照：从集合19复制，映射汇总名"""
import sqlite3

DB = '/home/xiaolin/projects/number-warehouse/backend/data/warehouse.db'
USE_DATE = '2026-07-08'

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

for CID, MAX_N in [(14, 4), (16, 6)]:
    # 读19的汇总名（按顺序取前N个）
    src = db.execute('''
        SELECT summary_name, total_value, draw_value_rank
        FROM daily_snapshots WHERE date=? AND collection_id=19 ORDER BY summary_id
    ''', (USE_DATE,)).fetchall()
    
    name_map = {}
    for i, r in enumerate(src):
        if i < MAX_N:
            name_map[r['summary_name']] = f'当日汇总{i+1}'
    
    # 删旧数据
    db.execute('DELETE FROM daily_project_snapshots WHERE date=? AND collection_id=?', (USE_DATE, CID))
    db.execute('DELETE FROM daily_grid_snapshots WHERE date=? AND collection_id=?', (USE_DATE, CID))
    
    # 复制项目快照
    if name_map:
        ph = ','.join('?' * len(name_map))
        proj_rows = db.execute(f'''
            SELECT summary_name, project_id, project_name, value
            FROM daily_project_snapshots
            WHERE collection_id=19 AND date=? AND summary_name IN ({ph})
        ''', [USE_DATE] + list(name_map.keys())).fetchall()
        
        proj_saved = 0
        for pr in proj_rows:
            tgt = name_map[pr['summary_name']]
            sid_row = db.execute('SELECT id FROM summaries WHERE name=? AND collection_id=?', (tgt, CID)).fetchone()
            if not sid_row:
                continue
            db.execute('''
                INSERT INTO daily_project_snapshots (date, collection_id, summary_id, summary_name, project_id, project_name, value)
                VALUES (?,?,?,?,?,?,?)
            ''', (USE_DATE, CID, sid_row[0], tgt, pr['project_id'], pr['project_name'], pr['value']))
            proj_saved += 1
        
        # 复制格子快照
        grid_rows = db.execute(f'''
            SELECT summary_name, count_n, value, value_x_47, cumulative_sum
            FROM daily_grid_snapshots
            WHERE collection_id=19 AND date=? AND summary_name IN ({ph})
            ORDER BY summary_name, count_n
        ''', [USE_DATE] + list(name_map.keys())).fetchall()
        
        grid_saved = 0
        for gr in grid_rows:
            tgt = name_map[gr['summary_name']]
            db.execute('''
                INSERT INTO daily_grid_snapshots (date, collection_id, summary_name, project_id, project_name, count_n, value, value_x_47, cumulative_sum)
                VALUES (?,?,?,?,?,?,?,?,?)
            ''', (USE_DATE, CID, tgt, 0, '累计', gr['count_n'], gr['value'], gr['value_x_47'], gr['cumulative_sum']))
            grid_saved += 1
        
        print(f'集合{CID}: {proj_saved}项目 + {grid_saved}格子')
    else:
        print(f'集合{CID}: 无数据')

db.commit()

# 验证
for CID in [14, 16]:
    cnt = db.execute('SELECT COUNT(*) FROM daily_project_snapshots WHERE date=? AND collection_id=?', (USE_DATE, CID)).fetchone()[0]
    print(f'验证 集合{CID}: {cnt}条项目快照')

# 还要更新 daily_snapshots 的 summary_id 使其匹配新创建的 summary
for CID, MAX_N in [(14, 4), (16, 6)]:
    for i in range(1, MAX_N + 1):
        name = f'当日汇总{i}'
        sid = db.execute('SELECT id FROM summaries WHERE name=? AND collection_id=?', (name, CID)).fetchone()
        if sid:
            db.execute('''
                UPDATE daily_snapshots SET summary_id=? WHERE date=? AND collection_id=? AND summary_name=?
            ''', (sid[0], USE_DATE, CID, name))

db.commit()
db.close()
print('完成')
