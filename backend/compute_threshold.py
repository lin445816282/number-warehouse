"""独立脚本：计算阈值数据（绕过API超时）"""
import sqlite3, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))

DB = os.path.join(os.path.dirname(__file__), "data", "warehouse.db")

def main(date_str=None):
    from datetime import date as dt
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row

    if date_str:
        use_date = date_str
    else:
        rec = db.execute("SELECT MAX(date) FROM records").fetchone()
        use_date = rec[0] or dt.today().isoformat()

    if use_date > dt.today().isoformat():
        print(f"日期 {use_date} 超过今天，拒绝")
        return

    cv_map = {r["count_n"]: r["value"] for r in db.execute("SELECT count_n, value FROM count_value_map")}

    # 取 col19 前6个汇总
    src_rows = db.execute(
        "SELECT summary_id, summary_name FROM daily_snapshots WHERE date=? AND collection_id=19 ORDER BY summary_id LIMIT 6",
        (use_date,)
    ).fetchall()
    if not src_rows:
        print("col19 无快照数据")
        return

    src_list = [(r["summary_id"], r["summary_name"]) for r in src_rows]
    print(f"col19 汇总: {[s[1] for s in src_list]}")

    def build_grid(sids):
        """返回 (top25, bottom24) 或 None"""
        placeholders = ",".join("?" * len(sids))
        pids = [r[0] for r in db.execute(
            f"SELECT DISTINCT rgi.project_id FROM run_group_items rgi "
            f"JOIN run_groups rg ON rgi.run_group_id = rg.id "
            f"WHERE rg.summary_id IN ({placeholders})", sids
        ).fetchall()]
        if not pids:
            print(f"  sids={sids} → 无项目")
            return None

        # 批量取每个项目的最大sim_run_id
        pplace = ",".join("?" * len(pids))
        max_runs = dict(db.execute(
            f"SELECT project_id, MAX(id) FROM sim_runs WHERE project_id IN ({pplace}) GROUP BY project_id",
            pids
        ).fetchall())
        run_ids = list(max_runs.values())

        rplace = ",".join("?" * len(run_ids))
        sr_rows = db.execute(
            f"SELECT sr.count_n, sr.numbers_json FROM sim_results sr "
            f"WHERE sr.run_id IN ({rplace}) AND sr.date=?",
            run_ids + [use_date]
        ).fetchall()
        if not sr_rows:
            print(f"  sids={sids} → {len(pids)}项目 {len(run_ids)}runs → 0 sim_results")
            return None

        pos = {n: 0 for n in range(1, 50)}
        for sr in sr_rows:
            val = cv_map.get(sr["count_n"], 0)
            for num in json.loads(sr["numbers_json"]):
                if 1 <= num <= 49:
                    pos[num] += val

        sorted_pos = sorted(pos.items(), key=lambda x: x[1], reverse=True)
        all_nums = [num for num, _ in sorted_pos]
        return all_nums[:25], all_nums[25:]

    # 清理旧数据
    db.execute("DELETE FROM collection_threshold_numbers WHERE date=?", (use_date,))

    results = []
    sids_all = [sid for sid, _ in src_list]

    # --- 汇总级 ---
    for sid, sname in src_list:
        print(f"计算 {sname}...", end=" ", flush=True)
        r = build_grid([sid])
        if r is None:
            print("跳过")
            continue
        top25, bottom24 = r
        for threshold, nums in [(25, top25), (24, bottom24)]:
            db.execute(
                "INSERT INTO collection_threshold_numbers (date, collection_id, threshold, summary_name, numbers_json) VALUES (?,0,?,?,?)",
                (use_date, threshold, sname, json.dumps(nums)))
        results.append((0, sname))
        print(f"OK ({len(top25)}+{len(bottom24)})")

    # --- 集合14 ---
    if len(sids_all) >= 4:
        print("计算 集合14...", end=" ", flush=True)
        r = build_grid(sids_all[:4])
        if r:
            top25, bottom24 = r
            for threshold, nums in [(25, top25), (24, bottom24)]:
                db.execute(
                    "INSERT INTO collection_threshold_numbers (date, collection_id, threshold, summary_name, numbers_json) VALUES (?,14,?,?,?)",
                    (use_date, threshold, "", json.dumps(nums)))
            results.append((14, ""))
            print(f"OK")
        else:
            print("跳过")

    # --- 集合16 ---
    if len(sids_all) >= 6:
        print("计算 集合16...", end=" ", flush=True)
        r = build_grid(sids_all[:6])
        if r:
            top25, bottom24 = r
            for threshold, nums in [(25, top25), (24, bottom24)]:
                db.execute(
                    "INSERT INTO collection_threshold_numbers (date, collection_id, threshold, summary_name, numbers_json) VALUES (?,16,?,?,?)",
                    (use_date, threshold, "", json.dumps(nums)))
            results.append((16, ""))
            print(f"OK")

    db.commit()
    db.close()
    print(f"\n完成！共 {len(results)} 组: {results}")

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(date_arg)
