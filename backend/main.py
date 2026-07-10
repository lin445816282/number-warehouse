"""
次数映射与数字仓库轮换系统 — FastAPI 后端
"""
import os, json, copy
from datetime import date as dt_date, timedelta
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3

from auth import auth_router, AuthMiddleware, init_auth_db

app = FastAPI(title="数字仓库轮换系统")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "warehouse.db")

BASE_DATE = dt_date(2026, 1, 1)  # 基准日
GROUPS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]

BASE_GROUPS = {
    "A": [3, 12, 25, 38],
    "B": [7, 19, 31, 44],
    "C": [2, 15, 27, 40],
    "D": [9, 21, 34, 47],
    "E": [5, 18, 30, 42],
    "F": [11, 23, 36, 49],
    "G": [1, 14, 26, 39],
    "H": [8, 20, 33, 46],
    "I": [6, 17, 29, 41],
    "J": [10, 22, 35, 48],
    "K": [4, 16, 28, 37],
    "L": [13, 24, 32, 43, 45],
}

DEFAULT_MAPPING = [
    {"n_min": 1, "n_max": 3, "output": 0},
    {"n_min": 4, "n_max": 4, "output": 5},
    {"n_min": 5, "n_max": 5, "output": 10},
    {"n_min": 6, "n_max": 51, "step": 5, "base_n": 4, "base_output": 5},
    {"n_min": 52, "n_max": 52, "output": 100},
    {"n_min": 53, "n_max": 999, "output": 0},
]


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS snapshots (
            date TEXT PRIMARY KEY,
            draw_number INTEGER,
            rotation_rule TEXT DEFAULT 'rule1',
            groups_json TEXT NOT NULL,
            count_json TEXT NOT NULL,
            value_map_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            day_seq INTEGER NOT NULL,
            draw_number INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            deleted_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS project_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            numbers TEXT NOT NULL DEFAULT '[]',
            deleted_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(project_id, group_name)
        );
        CREATE TABLE IF NOT EXISTS project_period_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            groups_json TEXT NOT NULL DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS dev_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            is_locked INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 0,
            deleted_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS sim_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            shift_amount INTEGER NOT NULL DEFAULT 1,
            project_id INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS sim_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            total_days INTEGER NOT NULL DEFAULT 0,
            hit_count INTEGER NOT NULL DEFAULT 0,
            project_id INTEGER DEFAULT NULL,
            project_name TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS sim_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            draw_number INTEGER NOT NULL,
            hit_group TEXT,
            group_name TEXT NOT NULL,
            numbers_json TEXT NOT NULL DEFAULT '[]',
            count_n INTEGER NOT NULL DEFAULT 0,
            UNIQUE(run_id, date, group_name)
        );
        CREATE TABLE IF NOT EXISTS count_value_map (
            count_n INTEGER PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS analysis_daily (
            date TEXT PRIMARY KEY,
            draw_number INTEGER NOT NULL,
            count_n INTEGER NOT NULL DEFAULT 0,
            value INTEGER NOT NULL DEFAULT 0,
            value_x_47 INTEGER NOT NULL DEFAULT 0,
            cumulative_sum INTEGER NOT NULL DEFAULT 0,
            result INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            remark TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );
        CREATE TABLE IF NOT EXISTS run_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            total_days INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            profit INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (summary_id) REFERENCES summaries(id)
        );
        CREATE TABLE IF NOT EXISTS run_group_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_group_id INTEGER NOT NULL,
            sim_run_id INTEGER NOT NULL DEFAULT 0,
            project_id INTEGER NOT NULL,
            project_name TEXT DEFAULT '',
            total_days INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            profit INTEGER DEFAULT 0,
            UNIQUE(run_group_id, project_id),
            FOREIGN KEY (run_group_id) REFERENCES run_groups(id),
            FOREIGN KEY (sim_run_id) REFERENCES sim_runs(id)
        );
        CREATE TABLE IF NOT EXISTS run_group_stats (
            run_group_id INTEGER PRIMARY KEY,
            project_count INTEGER DEFAULT 0,
            total_days INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            hit_rate REAL DEFAULT 0,
            profit INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (run_group_id) REFERENCES run_groups(id)
        );
        CREATE TABLE IF NOT EXISTS direct_mapping (
            num INTEGER PRIMARY KEY,
            group_name TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    # 初始化配置
    for k, v in [("mapping", json.dumps(DEFAULT_MAPPING, ensure_ascii=False)),
                 ("rotation", "rule1")]:
        db.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (k, v))
    # 种子：3个主项目 + 默认A-L组
    for pid in range(1, 4):
        db.execute("INSERT OR IGNORE INTO projects (id, name) VALUES (?,?)",
                   (pid, f"主项目{pid}"))
    for pid in range(1, 4):
        for g in GROUPS:
            nums = json.dumps(BASE_GROUPS[g])
            db.execute(
                "INSERT OR IGNORE INTO project_groups (project_id, group_name, numbers) VALUES (?,?,?)",
                (pid, g, nums))
    # 种子：开发规则
    db.execute("INSERT OR IGNORE INTO dev_rules (id, name, rule_type, config_json, is_locked, is_active) VALUES (?,?,?,?,?,?)",
               (1, "左移规则 (A←L)", "rotation",
                json.dumps({"desc": "全组左移一位，A←L,B←A,...,L←K", "config": {"rotation": "rule1"}}), 0, 1))
    db.execute("INSERT OR IGNORE INTO dev_rules (id, name, rule_type, config_json, is_locked, is_active) VALUES (?,?,?,?,?,?)",
               (2, "右移规则 (A←B)", "rotation",
                json.dumps({"desc": "全组右移一位，A←B,B←C,...,L←A", "config": {"rotation": "rule2"}}), 0, 0))
    db.execute("INSERT OR IGNORE INTO dev_rules (id, name, rule_type, config_json, is_locked, is_active) VALUES (?,?,?,?,?,?)",
               (3, "默认次数映射", "mapping",
                json.dumps({"desc": "n1-3→0, n4→5, n5→10, n6-51步骤5, n52→100, n53+→0", "config": DEFAULT_MAPPING}), 0, 1))
    # 种子：每个项目默认左1规则（仅表空时）
    cnt = db.execute("SELECT COUNT(*) FROM sim_rules").fetchone()[0]
    if cnt == 0:
        for pid in range(1, 4):
            db.execute(
                "INSERT INTO sim_rules (id, name, shift_amount, project_id) VALUES (?,?,?,?)",
                (pid, "左1 (A←L)", 1, pid))
    # 兼容旧表：添加可能缺失的列
    try:
        db.execute("ALTER TABLE sim_runs ADD COLUMN project_id INTEGER DEFAULT NULL")
    except Exception: pass
    try:
        db.execute("ALTER TABLE sim_runs ADD COLUMN project_name TEXT DEFAULT ''")
    except Exception: pass
    # 集合管理层：run_group_id 外键
    try:
        db.execute("ALTER TABLE sim_runs ADD COLUMN run_group_id INTEGER DEFAULT NULL")
    except Exception: pass
    # 分时段表新增时间列
    try:
        db.execute("ALTER TABLE project_period_groups ADD COLUMN start_time TEXT DEFAULT ''")
    except Exception: pass
    try:
        db.execute("ALTER TABLE project_period_groups ADD COLUMN end_time TEXT DEFAULT ''")
    except Exception: pass
    # 导出快照表：抽签号 1-49 排位
    try:
        db.execute("ALTER TABLE daily_snapshots ADD COLUMN draw_value_rank INTEGER DEFAULT NULL")
    except Exception: pass
    # 种子：次数映射值 1-52
    count_values = [0,0,0,25,30,35,40,45,50,55,60,64,72,81,91,102,113,126,140,156,173,191,211,233,257,283,312,343,377,415,456,501,549,603,661,725,795,871,955,1046,1145,1254,1373,1503,1645,1801,1971,2207,2473,2769,3101,3473]
    for i, v in enumerate(count_values):
        db.execute("INSERT OR IGNORE INTO count_value_map (count_n, value) VALUES (?,?)", (i+1, v))
    db.commit()
    db.close()


def get_config(db, key: str) -> str:
    row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_config(db, key: str, value: str):
    db.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?,?)", (key, value))
    db.commit()


# ==================== 核心算法 ====================

def days_since_base(target_date: dt_date) -> int:
    return (target_date - BASE_DATE).days


def rotate_left_shift(prev_groups: dict) -> dict:
    """规则1：全组左移一位 A←L, B←A, C←B ... L←K"""
    new_groups = {}
    new_groups["A"] = list(prev_groups["L"])
    for i in range(1, len(GROUPS)):
        new_groups[GROUPS[i]] = list(prev_groups[GROUPS[i - 1]])
    return new_groups


def rotate_left_n(prev_groups: dict, n: int) -> dict:
    """通用左移n位：A←(A-n) mod 12, B←(B-n) mod 12 ...
    n=1 等效左1(A←L), n=9 等效左9(A←D)
    """
    n = n % len(GROUPS)
    if n == 0:
        return {g: list(prev_groups[g]) for g in GROUPS}
    new_groups = {}
    for i in range(len(GROUPS)):
        src_idx = (i - n) % len(GROUPS)
        new_groups[GROUPS[i]] = list(prev_groups[GROUPS[src_idx]])
    return new_groups


def rotate_right_shift(prev_groups: dict) -> dict:
    """规则2：全组右移一位 A←B, B←C ... L←A（第1天A拿B的数，第12天回A）"""
    new_groups = {}
    for i in range(len(GROUPS) - 1):
        new_groups[GROUPS[i]] = list(prev_groups[GROUPS[i + 1]])
    new_groups["L"] = list(prev_groups["A"])
    return new_groups


def get_groups_for_date(target_date: dt_date, db) -> dict:
    """计算指定日期的数字仓库（组→数字列表）"""
    days = days_since_base(target_date)
    if days < 0:
        raise HTTPException(400, "日期不能早于基准日2026-01-01")

    rotation = get_config(db, "rotation") or "rule1"
    groups = {g: list(BASE_GROUPS[g]) for g in GROUPS}
    for _ in range(days):
        if rotation == "rule2":
            groups = rotate_right_shift(groups)
        else:
            groups = rotate_left_shift(groups)
    return groups


def apply_mapping(n: int, mapping_config: list) -> int:
    """将累计次数映射为输出数值"""
    for rule in mapping_config:
        if rule["n_min"] <= n <= rule["n_max"]:
            if "output" in rule:
                return rule["output"]
            if "step" in rule and "base_n" in rule:
                steps = n - rule["base_n"]
                return rule["base_output"] + steps * rule["step"]
    return 0


def compute_snapshot(target_date: dt_date, draw_number: int, db) -> dict:
    """计算完整快照：组→数字+次数+映射值"""
    groups = get_groups_for_date(target_date, db)
    mapping_config = json.loads(get_config(db, "mapping") or "[]")

    # 获取前一日快照
    prev_date = (target_date - timedelta(days=1)).isoformat()
    prev = db.execute("SELECT count_json FROM snapshots WHERE date=?", (prev_date,)).fetchone()

    if prev:
        prev_counts = json.loads(prev["count_json"])
    else:
        prev_counts = {g: 1 for g in GROUPS}

    # 找命中的组
    hit_group = None
    for g in GROUPS:
        if draw_number in groups[g]:
            hit_group = g
            break

    # 计算新次数
    is_first_day = target_date == BASE_DATE
    new_counts = {}
    for g in GROUPS:
        if is_first_day:
            new_counts[g] = 1  # 首日全部保持1
        elif g == hit_group:
            new_counts[g] = 1  # 命中重置
        else:
            new_counts[g] = prev_counts.get(g, 1) + 1

    # 映射
    value_map = {}
    for g in GROUPS:
        val = apply_mapping(new_counts[g], mapping_config)
        for num in groups[g]:
            value_map[str(num)] = val

    return {
        "date": target_date.isoformat(),
        "draw_number": draw_number,
        "rotation_rule": "rule1",
        "hit_group": hit_group,
        "groups": {g: {"numbers": groups[g], "count_n": new_counts[g],
                        "mapped_value": apply_mapping(new_counts[g], mapping_config)}
                   for g in GROUPS},
        "counts": new_counts,
        "value_map": value_map,
        "base_counts": prev_counts,
    }


# ==================== API ====================

class DrawRequest(BaseModel):
    date: str  # YYYY-MM-DD
    number: int  # 1-49


@app.post("/api/draw")
def draw(req: DrawRequest):
    target = dt_date.fromisoformat(req.date)
    if target < BASE_DATE:
        raise HTTPException(400, "日期不能早于2026-01-01")
    if req.number < 1 or req.number > 49:
        raise HTTPException(400, "抽签数字需在1-49之间")

    db = get_db()
    # 幂等检查
    existing = db.execute("SELECT * FROM snapshots WHERE date=?", (req.date,)).fetchone()
    if existing:
        result = json.loads(existing["value_map_json"])
        db.close()
        return {"ok": True, "already_exists": True, "value_map": result}

    snap = compute_snapshot(target, req.number, db)
    db.execute(
        "INSERT INTO snapshots (date, draw_number, rotation_rule, groups_json, count_json, value_map_json) VALUES (?,?,?,?,?,?)",
        (snap["date"], snap["draw_number"], snap["rotation_rule"],
         json.dumps(snap["groups"], ensure_ascii=False),
         json.dumps(snap["counts"], ensure_ascii=False),
         json.dumps(snap["value_map"], ensure_ascii=False))
    )
    db.commit()
    db.close()
    return {"ok": True, "snapshot": snap}


@app.get("/api/snapshot")
def get_snapshot(date: str = Query(...)):
    db = get_db()
    row = db.execute("SELECT * FROM snapshots WHERE date=?", (date,)).fetchone()
    if row:
        result = {
            "date": row["date"],
            "draw_number": row["draw_number"],
            "groups": json.loads(row["groups_json"]),
            "counts": json.loads(row["count_json"]),
            "value_map": json.loads(row["value_map_json"]),
        }
        db.close()
        return result

    # 未存储，实时计算（但需要抽签数字）
    db.close()
    raise HTTPException(404, f"日期 {date} 暂无快照，请先设置抽签数字")


@app.get("/api/snapshot/today")
def get_today():
    today_str = dt_date.today().isoformat()
    db = get_db()
    row = db.execute("SELECT * FROM snapshots WHERE date=?", (today_str,)).fetchone()
    if row:
        result = {
            "date": row["date"],
            "draw_number": row["draw_number"],
            "groups": json.loads(row["groups_json"]),
            "counts": json.loads(row["count_json"]),
            "value_map": json.loads(row["value_map_json"]),
        }
        db.close()
        return result
    db.close()
    return {"date": today_str, "no_data": True, "message": "今日尚无抽签数据"}


@app.get("/api/history")
def list_history():
    db = get_db()
    rows = db.execute(
        "SELECT date, draw_number FROM snapshots ORDER BY date DESC LIMIT 60"
    ).fetchall()
    db.close()
    return [{"date": r["date"], "draw_number": r["draw_number"]} for r in rows]


# ==================== 数据记录 CRUD ====================

class RecordIn(BaseModel):
    date: str
    draw_number: int


class RecordUpdate(BaseModel):
    date: Optional[str] = None
    draw_number: Optional[int] = None


def calc_day_seq(d: dt_date) -> int:
    """计算日期序号：每年1月1日=1，逐日+1"""
    year_start = dt_date(d.year, 1, 1)
    return (d - year_start).days + 1


@app.get("/api/records")
def list_records(page: int = 1, page_size: int = 30, year: str = ""):
    db = get_db()
    if year and year.isdigit():
        where = "WHERE date >= ? AND date < ?"
        params = [f"{year}-01-01", f"{int(year)+1}-01-01"]
    else:
        where = ""
        params = []
    total = db.execute(f"SELECT COUNT(*) FROM records {where}", params).fetchone()[0]
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM records {where} ORDER BY date DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    db.close()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "year": year or "all",
    }


@app.post("/api/records")
def create_record(r: RecordIn):
    target = dt_date.fromisoformat(r.date)
    day_seq = calc_day_seq(target)
    if r.draw_number < 1 or r.draw_number > 49:
        raise HTTPException(400, "抽签数字需在1-49之间")
    db = get_db()
    existing = db.execute("SELECT id FROM records WHERE date=?", (r.date,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(400, f"日期 {r.date} 已有记录，请使用编辑")
    db.execute(
        "INSERT INTO records (date, day_seq, draw_number) VALUES (?,?,?)",
        (r.date, day_seq, r.draw_number)
    )
    db.commit()
    row = db.execute("SELECT * FROM records WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "record": dict(row)}


@app.put("/api/records/{rid}")
def update_record(rid: int, r: RecordUpdate):
    db = get_db()
    existing = db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "记录不存在")
    new_date = r.date if r.date is not None else existing["date"]
    new_draw = r.draw_number if r.draw_number is not None else existing["draw_number"]
    if r.date is not None:
        dup = db.execute("SELECT id FROM records WHERE date=? AND id!=?", (r.date, rid)).fetchone()
        if dup:
            db.close()
            raise HTTPException(400, f"日期 {r.date} 已有记录")
    if new_draw < 1 or new_draw > 49:
        db.close()
        raise HTTPException(400, "抽签数字需在1-49之间")
    day_seq = calc_day_seq(dt_date.fromisoformat(new_date))
    db.execute(
        "UPDATE records SET date=?, day_seq=?, draw_number=?, updated_at=datetime('now','localtime') WHERE id=?",
        (new_date, day_seq, new_draw, rid)
    )
    db.commit()
    row = db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
    db.close()
    return {"ok": True, "record": dict(row)}


@app.delete("/api/records/{rid}")
def delete_record(rid: int):
    db = get_db()
    db.execute("DELETE FROM records WHERE id=?", (rid,))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/records/years")
def get_record_years():
    """返回有数据的年份列表"""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT substr(date,1,4) as y FROM records ORDER BY y"
    ).fetchall()
    db.close()
    return [r["y"] for r in rows]


# ==================== 项目与组别 CRUD ====================

class ProjectIn(BaseModel):
    name: str
    collection_id: Optional[int] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    collection_id: Optional[int] = None


class GroupIn(BaseModel):
    project_id: int
    group_name: str
    numbers: list


class GroupUpdate(BaseModel):
    group_name: Optional[str] = None
    numbers: Optional[list] = None


class PeriodGroupIn(BaseModel):
    project_id: int
    start_date: str = ""
    end_date: str = ""
    start_time: str = ""   # HH:MM，空=不限时段
    end_time: str = ""     # HH:MM
    groups_json: str = "{}"


class PeriodGroupUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    groups_json: Optional[str] = None
    is_active: Optional[int] = None


@app.get("/api/projects")
def list_projects(collection_id: Optional[int] = None):
    db = get_db()
    if collection_id is not None:
        rows = db.execute(
            "SELECT * FROM projects WHERE deleted_at IS NULL AND collection_id=? ORDER BY id",
            (collection_id,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY id"
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/api/projects")
def create_project(p: ProjectIn):
    db = get_db()
    # 同名项目 → 原地复用（优先活跃，其次已删除），防止ID漂移导致汇总孤儿
    cid = p.collection_id
    if cid:
        existing = db.execute(
            "SELECT id, deleted_at FROM projects WHERE name=? AND collection_id=? "
            "ORDER BY deleted_at IS NULL DESC, id ASC LIMIT 1",
            (p.name, cid)
        ).fetchone()
    else:
        existing = db.execute(
            "SELECT id, deleted_at FROM projects WHERE name=? AND collection_id IS NULL "
            "ORDER BY deleted_at IS NULL DESC, id ASC LIMIT 1",
            (p.name,)
        ).fetchone()

    if existing:
        pid = existing["id"]
        if existing["deleted_at"]:
            db.execute("UPDATE projects SET deleted_at=NULL WHERE id=?", (pid,))
        db.commit()
        row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        db.close()
        return {"ok": True, "project": dict(row), "reused": True}

    db.execute("INSERT INTO projects (name, collection_id) VALUES (?,?)", (p.name, cid))
    db.commit()
    row = db.execute("SELECT * FROM projects WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "project": dict(row)}


@app.put("/api/projects/{pid}")
def update_project(pid: int, p: ProjectUpdate):
    db = get_db()
    if not db.execute("SELECT id FROM projects WHERE id=? AND deleted_at IS NULL", (pid,)).fetchone():
        db.close()
        raise HTTPException(404, "项目不存在")
    if p.name is not None:
        db.execute("UPDATE projects SET name=? WHERE id=?", (p.name, pid))
    if p.collection_id is not None:
        db.execute("UPDATE projects SET collection_id=? WHERE id=?", (p.collection_id, pid))
    db.commit()
    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    return {"ok": True, "project": dict(row)}


@app.delete("/api/projects/{pid}")
def delete_project(pid: int):
    """软删除"""
    db = get_db()
    db.execute("UPDATE projects SET deleted_at=datetime('now','localtime') WHERE id=?", (pid,))
    db.execute("UPDATE project_groups SET deleted_at=datetime('now','localtime') WHERE project_id=?", (pid,))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/projects/{pid}/groups")
def list_groups(pid: int):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM project_groups WHERE project_id=? AND deleted_at IS NULL ORDER BY group_name",
        (pid,)
    ).fetchall()
    db.close()
    return [{"id": r["id"], "group_name": r["group_name"],
             "numbers": json.loads(r["numbers"]),
             "project_id": r["project_id"]} for r in rows]


@app.post("/api/groups")
def create_group(g: GroupIn):
    db = get_db()
    # check project exists
    if not db.execute("SELECT id FROM projects WHERE id=? AND deleted_at IS NULL", (g.project_id,)).fetchone():
        db.close()
        raise HTTPException(404, "项目不存在")
    existing = db.execute(
        "SELECT id FROM project_groups WHERE project_id=? AND group_name=? AND deleted_at IS NULL",
        (g.project_id, g.group_name)
    ).fetchone()
    if existing:
        db.close()
        raise HTTPException(400, f"组 {g.group_name} 已存在")
    db.execute(
        "INSERT INTO project_groups (project_id, group_name, numbers) VALUES (?,?,?)",
        (g.project_id, g.group_name, json.dumps(g.numbers))
    )
    db.commit()
    row = db.execute("SELECT * FROM project_groups WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "group": {"id": row["id"], "group_name": row["group_name"],
                                   "numbers": json.loads(row["numbers"]),
                                   "project_id": row["project_id"]}}


@app.put("/api/groups/{gid}")
def update_group(gid: int, g: GroupUpdate):
    db = get_db()
    existing = db.execute("SELECT * FROM project_groups WHERE id=? AND deleted_at IS NULL", (gid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "组不存在")
    new_name = g.group_name if g.group_name is not None else existing["group_name"]
    new_nums = json.dumps(g.numbers) if g.numbers is not None else existing["numbers"]
    # check uniqueness
    if g.group_name is not None:
        dup = db.execute(
            "SELECT id FROM project_groups WHERE project_id=? AND group_name=? AND id!=? AND deleted_at IS NULL",
            (existing["project_id"], g.group_name, gid)
        ).fetchone()
        if dup:
            db.close()
            raise HTTPException(400, f"组 {g.group_name} 已存在")
    db.execute(
        "UPDATE project_groups SET group_name=?, numbers=?, updated_at=datetime('now','localtime') WHERE id=?",
        (new_name, new_nums, gid)
    )
    db.commit()
    row = db.execute("SELECT * FROM project_groups WHERE id=?", (gid,)).fetchone()
    db.close()
    return {"ok": True, "group": {"id": row["id"], "group_name": row["group_name"],
                                   "numbers": json.loads(row["numbers"]),
                                   "project_id": row["project_id"]}}


@app.delete("/api/groups/{gid}")
def delete_group(gid: int):
    """软删除"""
    db = get_db()
    db.execute("UPDATE project_groups SET deleted_at=datetime('now','localtime') WHERE id=?", (gid,))
    db.commit()
    db.close()
    return {"ok": True}


# ==================== 分时段分组 ====================

def get_effective_groups(db, project_id: int, dt: str = None) -> dict:
    """获取当前生效的分组。优先匹配分时段（时间>日期），否则回落项目默认分组。

    匹配优先级：
    1. 分时段组别有 start_time/end_time → 检查当前时间是否在范围内
    2. 分时段组别有 start_date/end_date → 检查当前日期是否在范围内
    3. 都没有 → 回落项目默认 project_groups
    4. 如果项目也无默认分组 → 用 BASE_GROUPS
    """
    from datetime import datetime as dt_module
    now = dt_module.now()
    cur_date = now.strftime("%Y-%m-%d")
    cur_time = now.strftime("%H:%M")

    # 先查分时段（同时满足日期+时间才命中）
    rows = db.execute("""
        SELECT groups_json, start_date, end_date, start_time, end_time
        FROM project_period_groups
        WHERE project_id=? AND is_active=1
        ORDER BY start_time DESC, start_date DESC
    """, (project_id,)).fetchall()

    for row in rows:
        sd = row["start_date"] or ""
        ed = row["end_date"] or ""
        st = row["start_time"] or ""
        et = row["end_time"] or ""

        # 日期匹配（空=不限）
        date_ok = True
        if sd or ed:
            if sd and cur_date < sd: date_ok = False
            if ed and cur_date > ed: date_ok = False

        # 时间匹配（空=不限）
        time_ok = True
        if st or et:
            if st and cur_time < st: time_ok = False
            if et and cur_time >= et: time_ok = False

        if date_ok and time_ok:
            return json.loads(row["groups_json"])

    # 项目默认分组
    proj_groups = db.execute(
        "SELECT group_name, numbers FROM project_groups WHERE project_id=? AND deleted_at IS NULL ORDER BY group_name",
        (project_id,)
    ).fetchall()
    if proj_groups:
        return {r["group_name"]: json.loads(r["numbers"]) for r in proj_groups}

    # 全局默认
    return {g: list(BASE_GROUPS[g]) for g in GROUPS}


@app.get("/api/projects/{pid}/period-groups")
def list_period_groups(pid: int):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM project_period_groups WHERE project_id=? AND is_active=1 ORDER BY start_date",
        (pid,)
    ).fetchall()
    db.close()
    return [{"id": r["id"], "project_id": r["project_id"], "start_date": r["start_date"],
             "end_date": r["end_date"], "start_time": r["start_time"], "end_time": r["end_time"],
             "groups_json": json.loads(r["groups_json"])} for r in rows]


@app.post("/api/projects/{pid}/period-groups")
def create_period_group(pid: int, pg: PeriodGroupIn):
    db = get_db()
    if not db.execute("SELECT id FROM projects WHERE id=? AND deleted_at IS NULL", (pid,)).fetchone():
        db.close()
        raise HTTPException(404, "项目不存在")
    db.execute(
        "INSERT INTO project_period_groups (project_id, start_date, end_date, start_time, end_time, groups_json) VALUES (?,?,?,?,?,?)",
        (pid, pg.start_date, pg.end_date, pg.start_time, pg.end_time, pg.groups_json)
    )
    db.commit()
    row = db.execute("SELECT * FROM project_period_groups WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "period": {"id": row["id"], "project_id": row["project_id"],
              "start_date": row["start_date"], "end_date": row["end_date"],
              "start_time": row["start_time"], "end_time": row["end_time"],
              "groups_json": json.loads(row["groups_json"])}}


@app.put("/api/period-groups/{pgid}")
def update_period_group(pgid: int, pg: PeriodGroupUpdate):
    db = get_db()
    existing = db.execute("SELECT * FROM project_period_groups WHERE id=? AND is_active=1", (pgid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "分时段分组不存在")
    updates = []
    vals = []
    if pg.start_date is not None:
        updates.append("start_date=?"); vals.append(pg.start_date)
    if pg.end_date is not None:
        updates.append("end_date=?"); vals.append(pg.end_date)
    if pg.start_time is not None:
        updates.append("start_time=?"); vals.append(pg.start_time)
    if pg.end_time is not None:
        updates.append("end_time=?"); vals.append(pg.end_time)
    if pg.groups_json is not None:
        updates.append("groups_json=?"); vals.append(pg.groups_json)
    if pg.is_active is not None:
        updates.append("is_active=?"); vals.append(pg.is_active)
    if updates:
        updates.append("updated_at=datetime('now','localtime')")
        vals.append(pgid)
        db.execute(f"UPDATE project_period_groups SET {','.join(updates)} WHERE id=?", vals)
        db.commit()
    db.close()
    return {"ok": True}


@app.delete("/api/period-groups/{pgid}")
def delete_period_group(pgid: int):
    db = get_db()
    db.execute("UPDATE project_period_groups SET is_active=0, updated_at=datetime('now','localtime') WHERE id=?", (pgid,))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/projects/{pid}/effective-groups")
def get_project_effective_groups(pid: int):
    """获取项目当前生效的分组（含分时段匹配结果）"""
    db = get_db()
    # 获取默认分组
    def_groups = db.execute(
        "SELECT group_name, numbers FROM project_groups WHERE project_id=? AND deleted_at IS NULL ORDER BY group_name",
        (pid,)
    ).fetchall()
    defaults = {r["group_name"]: json.loads(r["numbers"]) for r in def_groups} if def_groups else None

    # 获取当前生效的分时段分组
    effective = get_effective_groups(db, pid)
    db.close()

    is_time_period = False
    if def_groups and effective != defaults:
        is_time_period = True

    return {
        "project_id": pid,
        "effective_groups": effective,
        "default_groups": defaults or {g: list(BASE_GROUPS[g]) for g in GROUPS},
        "is_time_period": is_time_period,
        "current_time": __import__("datetime").datetime.now().strftime("%H:%M"),
    }


# ==================== 开发规则 CRUD ====================

class RuleIn(BaseModel):
    name: str
    rule_type: str
    config_json: str = "{}"


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    config_json: Optional[str] = None
    is_locked: Optional[int] = None
    is_active: Optional[int] = None


@app.get("/api/dev-rules")
def list_dev_rules():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM dev_rules WHERE deleted_at IS NULL ORDER BY rule_type, id"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/api/dev-rules")
def create_dev_rule(r: RuleIn):
    db = get_db()
    db.execute(
        "INSERT INTO dev_rules (name, rule_type, config_json) VALUES (?,?,?)",
        (r.name, r.rule_type, r.config_json)
    )
    db.commit()
    row = db.execute("SELECT * FROM dev_rules WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "rule": dict(row)}


@app.put("/api/dev-rules/{rid}")
def update_dev_rule(rid: int, r: RuleUpdate):
    db = get_db()
    existing = db.execute("SELECT * FROM dev_rules WHERE id=? AND deleted_at IS NULL", (rid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "规则不存在")
    if existing["is_locked"]:
        db.close()
        raise HTTPException(400, "规则已锁定，无法修改")
    sets = []
    vals = []
    for field in ["name", "rule_type", "config_json", "is_locked", "is_active"]:
        v = getattr(r, field, None)
        if v is not None:
            sets.append(f"{field}=?")
            vals.append(v if field not in ("is_locked", "is_active") else int(v))
    if sets:
        sets.append("updated_at=datetime('now','localtime')")
        vals.append(rid)
        db.execute(f"UPDATE dev_rules SET {', '.join(sets)} WHERE id=?", vals)
        db.commit()
    row = db.execute("SELECT * FROM dev_rules WHERE id=?", (rid,)).fetchone()
    db.close()
    return {"ok": True, "rule": dict(row)}


@app.delete("/api/dev-rules/{rid}")
def delete_dev_rule(rid: int):
    """软删除"""
    db = get_db()
    existing = db.execute("SELECT * FROM dev_rules WHERE id=? AND deleted_at IS NULL", (rid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "规则不存在")
    if existing["is_locked"]:
        db.close()
        raise HTTPException(400, "规则已锁定，无法删除")
    db.execute("UPDATE dev_rules SET deleted_at=datetime('now','localtime') WHERE id=?", (rid,))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/history")
def list_history():
    db = get_db()
    rows = db.execute(
        "SELECT date, draw_number FROM snapshots ORDER BY date DESC LIMIT 60"
    ).fetchall()
    db.close()
    return [{"date": r["date"], "draw_number": r["draw_number"]} for r in rows]


# ==================== 模拟规则 CRUD ====================

class SimRuleIn(BaseModel):
    name: str
    shift_amount: int
    project_id: int


class SimRuleUpdate(BaseModel):
    name: Optional[str] = None
    shift_amount: Optional[int] = None
    is_active: Optional[int] = None


@app.get("/api/sim/rules")
def list_sim_rules(project_id: Optional[int] = None):
    db = get_db()
    if project_id:
        rows = db.execute(
            "SELECT * FROM sim_rules WHERE project_id=? ORDER BY shift_amount",
            (project_id,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM sim_rules ORDER BY project_id, shift_amount").fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/api/sim/rules")
def create_sim_rule(r: SimRuleIn):
    if r.shift_amount < 1 or r.shift_amount > 12:
        raise HTTPException(400, "移位数需在1-12之间")
    db = get_db()
    db.execute(
        "INSERT INTO sim_rules (name, shift_amount, project_id) VALUES (?,?,?)",
        (r.name, r.shift_amount, r.project_id)
    )
    db.commit()
    row = db.execute("SELECT * FROM sim_rules WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "rule": dict(row)}


@app.put("/api/sim/rules/{rid}")
def update_sim_rule(rid: int, r: SimRuleUpdate):
    db = get_db()
    existing = db.execute("SELECT * FROM sim_rules WHERE id=?", (rid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "规则不存在")
    sets, vals = [], []
    for f in ["name", "is_active"]:
        v = getattr(r, f, None)
        if v is not None:
            sets.append(f"{f}=?")
            vals.append(v)
    if r.shift_amount is not None:
        if r.shift_amount < 1 or r.shift_amount > 12:
            db.close()
            raise HTTPException(400, "移位数需在1-12之间")
        sets.append("shift_amount=?")
        vals.append(r.shift_amount)
    if sets:
        vals.append(rid)
        db.execute(f"UPDATE sim_rules SET {', '.join(sets)} WHERE id=?", vals)
        db.commit()
    row = db.execute("SELECT * FROM sim_rules WHERE id=?", (rid,)).fetchone()
    db.close()
    return {"ok": True, "rule": dict(row)}


@app.delete("/api/sim/rules/{rid}")
def delete_sim_rule(rid: int):
    db = get_db()
    db.execute("DELETE FROM sim_rules WHERE id=?", (rid,))
    db.commit()
    db.close()
    return {"ok": True}


# ==================== 模拟运行 ====================

def load_project_groups(db, project_id: int) -> dict:
    """加载项目的A-L组基础数字"""
    rows = db.execute(
        "SELECT group_name, numbers FROM project_groups WHERE project_id=? AND deleted_at IS NULL ORDER BY group_name",
        (project_id,)
    ).fetchall()
    return {r["group_name"]: json.loads(r["numbers"]) for r in rows}


def run_simulation(db, rule_id: int, start_date: str, end_date: str, project_id: int = None):
    """执行模拟运行：按日期范围推进左移+次数匹配。
    - 已有相同规则+项目的运行记录则从最后日期接续
    - 日期已覆盖则跳过，返回 skipped=True
    """
    rule = db.execute("SELECT * FROM sim_rules WHERE id=?", (rule_id,)).fetchone()
    if not rule:
        raise HTTPException(404, "规则不存在")

    shift = rule["shift_amount"]
    pid = project_id or rule["project_id"]
    proj_name = db.execute("SELECT name FROM projects WHERE id=? AND deleted_at IS NULL", (pid,)).fetchone()
    proj_name = proj_name["name"] if proj_name else f"项目{pid}"

    # 加载基础组数字
    base = load_project_groups(db, pid)
    if len(base) != 12:
        raise HTTPException(400, f"项目{pid}缺少A-L组设置")

    # === 检查已有运行，确定实际起止日期和初始状态 ===
    existing = db.execute(
        "SELECT * FROM sim_runs WHERE rule_id=? AND project_id=? ORDER BY id DESC LIMIT 1",
        (rule_id, pid)
    ).fetchone()

    groups = {g: list(base[g]) for g in GROUPS}
    counts = {g: 1 for g in GROUPS}
    day_offset = 0  # 已运行天数
    reset_tomorrow = set()  # 昨天命中的组，今天重置为1

    # 生成日期序列
    sd = dt_date.fromisoformat(start_date)
    ed = dt_date.fromisoformat(end_date)
    all_dates = []
    d = sd
    while d <= ed:
        all_dates.append(d.isoformat())
        d += timedelta(days=1)

    # 加载抽签记录（查整个范围）
    records = db.execute(
        "SELECT date, draw_number FROM records WHERE date BETWEEN ? AND ? ORDER BY date",
        (start_date, end_date)
    ).fetchall()
    records_by_date = {}
    for rec in records:
        if rec["draw_number"] is not None and rec["draw_number"] != 0:
            records_by_date[rec["date"]] = rec["draw_number"]

    # 同时查 snapshots 表补全（集合系统用 snapshots）
    snapshots = db.execute(
        "SELECT date, draw_number FROM snapshots WHERE date BETWEEN ? AND ? "
        "AND draw_number IS NOT NULL AND draw_number > 0 ORDER BY date",
        (start_date, end_date)
    ).fetchall()
    for snap in snapshots:
        if snap["date"] not in records_by_date:
            records_by_date[snap["date"]] = snap["draw_number"]

    # === 向前查一天：取最后一次已知抽签，用于截断逻辑判断 ===
    prev_record = db.execute(
        "SELECT date, draw_number FROM records WHERE date < ? "
        "AND draw_number IS NOT NULL AND draw_number > 0 "
        "ORDER BY date DESC LIMIT 1",
        (start_date,)
    ).fetchone()
    if prev_record:
        records_by_date[prev_record["date"]] = prev_record["draw_number"]
    if not prev_record:
        prev_snap = db.execute(
            "SELECT date, draw_number FROM snapshots WHERE date < ? "
            "AND draw_number IS NOT NULL AND draw_number > 0 "
            "ORDER BY date DESC LIMIT 1",
            (start_date,)
        ).fetchone()
        if prev_snap:
            records_by_date[prev_snap["date"]] = prev_snap["draw_number"]

    # === 自动前推：请求起始在最新抽签之后 → 包含最新抽签日 ===
    start_was_adjusted = False
    end_was_adjusted = False
    req_start_date = start_date  # 记录原始请求
    req_end_date = end_date
    if records_by_date:
        max_record_date = max(records_by_date.keys())
        if start_date > max_record_date:
            start_was_adjusted = True
            start_date = max_record_date
            sd = dt_date.fromisoformat(start_date)
            all_dates = []
            d = sd
            while d <= ed:
                all_dates.append(d.isoformat())
                d += timedelta(days=1)
            # 补查新范围内的抽签记录
            new_records = db.execute(
                "SELECT date, draw_number FROM records WHERE date BETWEEN ? AND ? ORDER BY date",
                (start_date, end_date)
            ).fetchall()
            for rec in new_records:
                if rec["draw_number"] is not None and rec["draw_number"] != 0:
                    records_by_date[rec["date"]] = rec["draw_number"]
            new_snaps = db.execute(
                "SELECT date, draw_number FROM snapshots WHERE date BETWEEN ? AND ? "
                "AND draw_number IS NOT NULL AND draw_number > 0 ORDER BY date",
                (start_date, end_date)
            ).fetchall()
            for snap in new_snaps:
                if snap["date"] not in records_by_date:
                    records_by_date[snap["date"]] = snap["draw_number"]

    # === 严格限制：end_date = 最新抽签日期 + 1天（只允许一天待开） ===
    if records_by_date:
        max_record_date = max(records_by_date.keys())
        max_allowed = (dt_date.fromisoformat(max_record_date) + timedelta(days=1)).isoformat()
        if max_allowed < end_date:
            raise HTTPException(400, f"只能演算到 {max_allowed}（最新抽签 {max_record_date}+1天），无法生成 {end_date} 的数据")
    elif existing:
        # 完全没有新记录→已有范围≥请求起始才沿用，否则保持请求范围（允许往后一天预测）
        if existing["end_date"] >= start_date:
            end_date = existing["end_date"]
            ed = dt_date.fromisoformat(end_date)
            all_dates = []
            d = sd
            while d <= ed:
                all_dates.append(d.isoformat())
                d += timedelta(days=1)
        # else: start_date > existing_end → 保持原始 all_dates（用户请求预测）

    if not all_dates:
        raise HTTPException(400, "无效日期范围")

    pending_days = []
    if existing and (not start_was_adjusted or start_date >= existing["start_date"]):
        existing_end = existing["end_date"]
        # 检查是否有待开奖的天需要更新（只对有抽签记录的日期，无抽签的"待开"不算pending避免死循环）
        pending_days = []
        if end_date <= existing_end:
            # 查最大有抽签日期（已开奖），无抽签的"待开"日不算pending避免死循环
            max_draw = db.execute(
                "SELECT MAX(date) FROM ("
                "SELECT MAX(date) as date FROM records WHERE draw_number IS NOT NULL AND draw_number>0 "
                "UNION ALL "
                "SELECT MAX(date) FROM snapshots WHERE draw_number IS NOT NULL AND draw_number>0"
                ")"
            ).fetchone()
            max_draw_date = max_draw[0] if max_draw and max_draw[0] else "0000-01-01"
            pending_days = db.execute(
                "SELECT DISTINCT date FROM sim_results WHERE run_id=? AND hit_group IS NULL "
                "AND date BETWEEN ? AND ? AND date <= ?",
                (existing["id"], start_date, end_date, max_draw_date)
            ).fetchall()
        if not pending_days and end_date <= existing_end:
            msg = f"已有 {existing_end} 前数据，跳过"
            if start_was_adjusted or end_was_adjusted:
                msg += f"（日期已自动调整：{req_start_date}~{req_end_date} → {start_date}~{end_date}）"
            return {
                "ok": True, "run_id": existing["id"], "skipped": True,
                "total_days": existing["total_days"], "hit_count": existing["hit_count"],
                "start_date": existing["start_date"], "end_date": existing_end,
                "project_id": pid, "project_name": proj_name,
                "message": msg
            }
        # 有pending或需要接续 → 从接入点开始
        if pending_days:
            # 重新运行：先删该范围已有结果，从start_date前一天加载状态
            db.execute("DELETE FROM sim_results WHERE run_id=? AND date >= ?",
                       (existing["id"], start_date))
            # 从 start_date 前一天恢复状态
            prev_date = (dt_date.fromisoformat(start_date) - timedelta(days=1)).isoformat()
            prev_results = db.execute(
                "SELECT group_name, numbers_json, count_n FROM sim_results "
                "WHERE run_id=? AND date=? ORDER BY group_name",
                (existing["id"], prev_date)
            ).fetchall()
            if prev_results:
                for r in prev_results:
                    groups[r["group_name"]] = json.loads(r["numbers_json"])
                    counts[r["group_name"]] = r["count_n"]
                # 补偿存储时的+1（数据库存的是当天递增前的值，需要恢复为当天结束时的值）
                for g in GROUPS:
                    counts[g] = counts.get(g, 1) + 1
                # 检查前一天是否有命中，有则次日需要重置
                prev_hit = db.execute(
                    "SELECT hit_group FROM sim_results WHERE run_id=? AND date=? AND hit_group IS NOT NULL LIMIT 1",
                    (existing["id"], prev_date)
                ).fetchone()
                if prev_hit:
                    reset_tomorrow.add(prev_hit["hit_group"])
                # 计算到前一天为止的天数
                prev_day_count = db.execute(
                    "SELECT COUNT(DISTINCT date) FROM sim_results WHERE run_id=? AND date <= ?",
                    (existing["id"], prev_date)
                ).fetchone()[0]
                day_offset = prev_day_count
            else:
                day_offset = 0
            real_start = start_date
            run_id = existing["id"]
            is_new_run = False
        else:
            # 从已有最后一天接续
            real_start_dt = dt_date.fromisoformat(existing_end) + timedelta(days=1)
            real_start = real_start_dt.isoformat()
            last_results = db.execute(
                "SELECT group_name, numbers_json, count_n FROM sim_results "
                "WHERE run_id=? AND date=? ORDER BY group_name",
                (existing["id"], existing_end)
            ).fetchall()
            if last_results:
                for r in last_results:
                    groups[r["group_name"]] = json.loads(r["numbers_json"])
                    counts[r["group_name"]] = r["count_n"]
            # 补偿存储时的+1（数据库存的是当天递增前的值，需要恢复为当天结束时的值）
            for g in GROUPS:
                counts[g] = counts.get(g, 1) + 1
            # 检查最后一天是否有命中，有则次日需要重置
            last_hit = db.execute(
                "SELECT hit_group FROM sim_results WHERE run_id=? AND date=? AND hit_group IS NOT NULL LIMIT 1",
                (existing["id"], existing_end)
            ).fetchone()
            if last_hit:
                reset_tomorrow.add(last_hit["hit_group"])
            day_offset = existing["total_days"]
            run_id = existing["id"]
            is_new_run = False
    else:
        real_start = start_date
        is_new_run = True

    # 过滤all_dates到real_start之后
    process_dates = [dt for dt in all_dates if dt >= real_start]

    if is_new_run:
        db.execute(
            "INSERT INTO sim_runs (rule_id, start_date, end_date, total_days, project_id, project_name) VALUES (?,?,?,?,?,?)",
            (rule_id, process_dates[0] if process_dates else start_date, end_date, 0, pid, proj_name)
        )
        run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    hit_count = 0
    pending_count = 0
    current_base = None

    for day_idx, dt in enumerate(process_dates):
        draw = records_by_date.get(dt)  # None 表示无抽签 → 待开奖

        eff_groups = get_effective_groups(db, pid, dt)
        eff_key = json.dumps(eff_groups, sort_keys=True)
        is_first_day = (day_offset + day_idx == 0)
        skip_rotate = False
        if eff_key != current_base:
            if is_first_day and existing and not pending_days:
                current_base = eff_key
            else:
                groups = eff_groups
                for _ in range(max(0, day_offset + day_idx - 1)):
                    groups = rotate_left_n(groups, shift)
                current_base = eff_key
                if day_offset + day_idx == 0:
                    skip_rotate = True

        if not skip_rotate and day_offset + day_idx >= 1:
            groups = rotate_left_n(groups, shift)

        # === 第一步：应用昨日命中的重置（命中次日才重置为1）===
        if is_first_day:
            counts = {g: 1 for g in GROUPS}
        else:
            for g in reset_tomorrow:
                counts[g] = 1
        reset_tomorrow.clear()

        # === 第二步：检测今天是否命中 ===
        hit_group = None
        if draw is not None:
            for g in GROUPS:
                if draw in groups[g]:
                    hit_group = g
                    hit_count += 1
                    break
        else:
            pending_count += 1

        pre_hit = counts.get(hit_group) if hit_group else None

        # === 第三步：存储（当天开始时的次数）===
        for g in GROUPS:
            db.execute(
                "INSERT OR REPLACE INTO sim_results (run_id, date, draw_number, hit_group, group_name, numbers_json, count_n, pre_hit_count_n) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (run_id, dt, draw or 0, hit_group, g,
                 json.dumps(groups[g]), counts[g],
                 pre_hit if g == hit_group else None)
            )

        # === 第四步：每天统一递增（命中组也不例外，次日才重置）===
        for g in GROUPS:
            counts[g] = counts.get(g, 1) + 1

        # === 第五步：标记今天命中的组，明天重置 ===
        if hit_group:
            reset_tomorrow.add(hit_group)

    total_days = day_offset + len(process_dates)
    if is_new_run:
        db.execute(
            "UPDATE sim_runs SET end_date=?, total_days=?, hit_count=? WHERE id=?",
            (process_dates[-1] if process_dates else end_date, total_days, hit_count, run_id)
        )
    else:
        db.execute(
            "UPDATE sim_runs SET end_date=?, total_days=?, hit_count=hit_count+? WHERE id=?",
            (process_dates[-1] if process_dates else end_date, total_days, hit_count, run_id)
        )
    db.commit()

    # 自动刷新该项目所在的所有记录组统计
    rg_items = db.execute(
        "SELECT DISTINCT run_group_id FROM run_group_items WHERE sim_run_id=? AND run_group_id IS NOT NULL",
        (run_id,)
    ).fetchall()
    for rg in rg_items:
        _refresh_run_group_stats(db, rg["run_group_id"])
    if rg_items:
        db.commit()

    msg = f"演算完成 {total_days}天 {hit_count}命中"
    if start_was_adjusted or end_was_adjusted:
        msg += f"（日期已自动调整：{req_start_date}~{req_end_date} → {start_date}~{process_dates[-1] if process_dates else end_date}）"
    return {
        "ok": True, "run_id": run_id, "skipped": False,
        "total_days": total_days, "hit_count": db.execute(
            "SELECT hit_count FROM sim_runs WHERE id=?", (run_id,)).fetchone()["hit_count"],
        "start_date": db.execute("SELECT start_date FROM sim_runs WHERE id=?", (run_id,)).fetchone()["start_date"],
        "end_date": process_dates[-1] if process_dates else end_date,
        "new_days": len(process_dates),
        "pending_count": pending_count,
        "project_id": pid, "project_name": proj_name,
        "continued": not is_new_run,
        "message": msg
    }


@app.get("/api/sim/runs")
def list_sim_runs(rule_id: Optional[int] = None, project_id: Optional[int] = None):
    db = get_db()
    if project_id:
        rows = db.execute(
            "SELECT r.*, s.name as rule_name, s.shift_amount FROM sim_runs r "
            "JOIN sim_rules s ON r.rule_id=s.id WHERE s.project_id=? ORDER BY r.id DESC LIMIT 30",
            (project_id,)
        ).fetchall()
    elif rule_id:
        rows = db.execute(
            "SELECT r.*, s.name as rule_name, s.shift_amount FROM sim_runs r "
            "JOIN sim_rules s ON r.rule_id=s.id WHERE r.rule_id=? ORDER BY r.id DESC LIMIT 30",
            (rule_id,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT r.*, s.name as rule_name, s.shift_amount FROM sim_runs r "
            "JOIN sim_rules s ON r.rule_id=s.id ORDER BY r.id DESC LIMIT 30"
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.get("/api/sim/runs/{run_id}")
def get_sim_run(run_id: int, limit: Optional[int] = Query(None)):
    db = get_db()
    run = db.execute(
        "SELECT r.*, s.name as rule_name, s.shift_amount FROM sim_runs r "
        "JOIN sim_rules s ON r.rule_id=s.id WHERE r.id=?",
        (run_id,)
    ).fetchone()
    if not run:
        db.close()
        raise HTTPException(404, "运行不存在")

    # 预加载次数→值映射
    count_values = {}
    for row in db.execute("SELECT count_n, value FROM count_value_map").fetchall():
        count_values[row["count_n"]] = row["value"]

    # 按日期分组结果（desc，限制天数）
    seen_dates = set()
    daily = {}
    for r in db.execute(
        "SELECT * FROM sim_results WHERE run_id=? ORDER BY date DESC, group_name",
        (run_id,)
    ).fetchall():
        dt = r["date"]
        if dt not in seen_dates:
            if limit and len(seen_dates) >= limit:
                break
            seen_dates.add(dt)
        if dt not in daily:
            daily[dt] = {
                "date": dt,
                "draw_number": r["draw_number"],
                "hit_group": r["hit_group"],
                "groups": {}
            }
        daily[dt]["groups"][r["group_name"]] = {
            "numbers": json.loads(r["numbers_json"]),
            "count_n": r["count_n"],
            "value": count_values.get(r["count_n"], 0)
        }

    db.close()
    return {
        "run": dict(run),
        "daily": [daily[k] for k in sorted(daily.keys(), reverse=True)],
    }


class SimRunRequest(BaseModel):
    rule_ids: list  # [rule_id, ...]
    project_ids: list  # [project_id, ...]  — 多项目并行
    start_date: str = "2020-03-18"
    end_date: str = "2026-07-03"


@app.post("/api/sim/run")
def run_simulation_endpoint(body: SimRunRequest):
    """运行模拟：{rule_ids:[], project_ids:[], start_date, end_date}
    多项目并行：每个project配一个rule（按索引对应，不足则用最后一个rule）。
    """
    if not body.project_ids:
        raise HTTPException(400, "project_ids 不能为空")
    if not body.rule_ids:
        raise HTTPException(400, "rule_ids 不能为空")

    db = get_db()
    results = []
    errors = []
    try:
        all_skipped = True
        for i, pid in enumerate(body.project_ids):
            rid = body.rule_ids[min(i, len(body.rule_ids) - 1)]
            try:
                r = run_simulation(db, rid, body.start_date, body.end_date, pid)
                results.append(r)
                if not r.get("skipped"):
                    all_skipped = False
            except HTTPException as e:
                errors.append({"project_id": pid, "rule_id": rid, "error": e.detail})
            except Exception as e:
                errors.append({"project_id": pid, "rule_id": rid, "error": str(e)})
        if not all_skipped:
            refresh_analysis(db)
        # 返回最后一条的run_id给前端默认展示
        last = results[-1] if results else None
        return {"ok": True, "runs": results, "errors": errors, "last_run_id": last["run_id"] if last else None}
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 模拟结果查询 ====================

@app.get("/api/sim/results/query")
def query_sim_results(
    project_id: Optional[int] = None,
    project_ids: Optional[str] = None,
    rule_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 30
):
    """查询模拟运行记录（支持多条件筛选，project_ids为逗号分隔）"""
    db = get_db()
    wheres = ["1=1"]
    params = []

    if project_ids:
        ids = [int(x) for x in project_ids.split(',') if x.strip().isdigit()]
        if ids:
            placeholders = ','.join('?' * len(ids))
            wheres.append(f"r.project_id IN ({placeholders})")
            params.extend(ids)
    elif project_id:
        wheres.append("r.project_id=?")
        params.append(project_id)
    if rule_id:
        wheres.append("r.rule_id=?")
        params.append(rule_id)
    if start_date:
        wheres.append("r.end_date >= ?")
        params.append(start_date)
    if end_date:
        wheres.append("r.start_date <= ?")
        params.append(end_date)

    where = " AND ".join(wheres)
    # 只取每个项目的最新一次运行
    sub = f"SELECT MAX(id) FROM sim_runs r2 WHERE r2.project_id = r.project_id"
    where += f" AND r.id = ({sub})"
    total = db.execute(f"SELECT COUNT(*) FROM sim_runs r WHERE {where}", params).fetchone()[0]

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT r.*, s.name as rule_name, s.shift_amount FROM sim_runs r "
        f"JOIN sim_rules s ON r.rule_id=s.id WHERE {where} ORDER BY r.id DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()

    db.close()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size)
    }


@app.delete("/api/sim/runs/{run_id}")
def delete_sim_run(run_id: int):
    db = get_db()
    db.execute("DELETE FROM sim_results WHERE run_id=?", (run_id,))
    db.execute("DELETE FROM sim_runs WHERE id=?", (run_id,))
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/api/sim/clear-all")
def clear_all_sim_data():
    """一键清空所有模拟数据（sim_runs + sim_results）"""
    db = get_db()
    try:
        db.execute("DELETE FROM sim_results")
        db.execute("DELETE FROM sim_runs")
        db.execute("DELETE FROM sqlite_sequence WHERE name IN ('sim_runs','sim_results')")
        db.commit()
        return {"ok": True, "message": "已清空所有模拟运行数据"}
    finally:
        db.close()

# ==================== 次数映射值 ====================

def get_count_value(count_n: int, db) -> int:
    """查映射表，53+返回0"""
    if count_n > 52:
        return 0
    row = db.execute("SELECT value FROM count_value_map WHERE count_n=?", (count_n,)).fetchone()
    return row["value"] if row else 0


def get_count_map_dict(db) -> dict:
    """获取全部映射"""
    rows = db.execute("SELECT count_n, value FROM count_value_map ORDER BY count_n").fetchall()
    return {r["count_n"]: r["value"] for r in rows}


@app.get("/api/count-values")
def list_count_values():
    db = get_db()
    data = get_count_map_dict(db)
    db.close()
    return data


@app.post("/api/count-values")
def set_count_values(data: dict):
    """批量设置映射 {count_n: value}"""
    db = get_db()
    for k, v in data.items():
        n = int(k)
        db.execute("INSERT OR REPLACE INTO count_value_map (count_n, value) VALUES (?,?)", (n, v))
    db.commit()
    db.close()
    return {"ok": True}


# ==================== 次数映射管理 ====================

@app.get("/api/mapping")
def get_mapping():
    """获取全部次数→值映射"""
    db = get_db()
    rows = db.execute("SELECT count_n, value FROM count_value_map ORDER BY count_n").fetchall()
    db.close()
    return [{"count_n": r["count_n"], "value": r["value"]} for r in rows]


class MappingItem(BaseModel):
    count_n: int
    value: int


@app.post("/api/mapping")
def save_mapping(item: MappingItem):
    """新增或更新映射"""
    db = get_db()
    db.execute("INSERT OR REPLACE INTO count_value_map (count_n, value) VALUES (?,?)",
               (item.count_n, item.value))
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/api/mapping/{count_n}")
def delete_mapping(count_n: int):
    """删除映射"""
    db = get_db()
    db.execute("DELETE FROM count_value_map WHERE count_n=?", (count_n,))
    db.commit()
    db.close()
    return {"ok": True}


# ==================== 数据分析 ====================

def refresh_analysis(db):
    """重建 analysis_daily 表，按项目独立计算。
    cumulative_sum = 每天结果的累计求和（运行中的净收益趋势）
    result = 命中组value × 47 - 当天所有49个数字的映射值之和（当日净收益）"""
    db.execute("DELETE FROM analysis_daily")
    value_map = get_count_map_dict(db)
    
    runs = db.execute("""
        SELECT srn.id, srn.project_id, srn.project_name, sr.name as rule_name
        FROM sim_runs srn
        JOIN sim_rules sr ON srn.rule_id = sr.id
        WHERE sr.is_active = 1
        AND srn.id = (SELECT MAX(id) FROM sim_runs WHERE project_id = srn.project_id)
    """).fetchall()
    
    all_data = []
    for run in runs:
        pid, pname = run["project_id"], run["project_name"]
        
        dates = db.execute("""
            SELECT DISTINCT date FROM sim_results 
            WHERE run_id = ? ORDER BY date
        """, (run["id"],)).fetchall()
        
        cumulative_sum = 0  # 运行中的结果累计求和
        for date_row in dates:
            dt = date_row["date"]
            
            groups = db.execute("""
                SELECT group_name, count_n, numbers_json, hit_group, draw_number
                FROM sim_results 
                WHERE run_id = ? AND date = ?
            """, (run["id"], dt)).fetchall()
            
            if not groups:
                continue
            
            # 计算当日成本 = Σ(各组 value × 组内数字个数)
            daily_cost = 0
            hit_count_n = None
            hit_val = 0
            draw_number = groups[0]["draw_number"]
            
            for g in groups:
                nums = json.loads(g["numbers_json"])
                val = value_map.get(g["count_n"], 0)
                daily_cost += val * len(nums)
                if g["hit_group"] and g["hit_group"] == g["group_name"]:
                    hit_count_n = g["count_n"]
                    hit_val = val
            
            if hit_count_n is None:
                continue
            
            temp = hit_val * 47
            result = temp - daily_cost
            cumulative_sum += result  # 累加结果
            
            day_seq = db.execute(
                "SELECT day_seq FROM records WHERE date=?", (dt,)
            ).fetchone()
            
            all_data.append((
                dt, draw_number, hit_count_n, hit_val, temp, cumulative_sum, result,
                pid, pname,
                day_seq[0] if day_seq else None
            ))
    
    if all_data:
        db.executemany(
            "INSERT INTO analysis_daily (date, draw_number, count_n, value, value_x_47, cumulative_sum, result, project_id, project_name, day_seq) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)", all_data)
    db.commit()


@app.post("/api/analysis/refresh")
def api_refresh_analysis():
    """全量重建分析数据"""
    db = get_db()
    refresh_analysis(db)
    count = db.execute("SELECT COUNT(*) FROM analysis_daily").fetchone()[0]
    db.close()
    return {"ok": True, "count": count}


@app.delete("/api/analysis/clear")
def api_clear_analysis():
    """清空分析数据（不影响 records）"""
    db = get_db()
    db.execute("DELETE FROM analysis_daily")
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/analysis")
def get_analysis(start_date: str = "2020-03-18", end_date: str = "2026-07-03",
                 page: int = 1, page_size: int = 50, project_id: int = None,
                 project_ids: str = None):
    """数据分析：从 analysis_daily 读，支持按项目或项目列表筛选"""
    db = get_db()

    cnt = db.execute("SELECT COUNT(*) FROM analysis_daily").fetchone()[0]
    if cnt == 0:
        return {"items": [], "total": 0, "page": 1, "page_size": page_size,
                "total_pages": 0, "cumulative_sum": 0, "message": "请先运行规则模拟生成数据"}

    where = "WHERE date BETWEEN ? AND ?"
    params = [start_date, end_date]
    if project_ids:
        ids = [int(x) for x in project_ids.split(',') if x.strip().isdigit()]
        if ids:
            placeholders = ','.join('?' * len(ids))
            where += f" AND project_id IN ({placeholders})"
            params.extend(ids)
    elif project_id:
        where += " AND project_id = ?"
        params.append(project_id)

    total = db.execute(
        f"SELECT COUNT(*) FROM analysis_daily {where}", params
    ).fetchone()[0]

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM analysis_daily {where} ORDER BY date LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()

    # 查询总累计
    last_row = db.execute(
        f"SELECT cumulative_sum FROM analysis_daily {where} ORDER BY date DESC LIMIT 1",
        params
    ).fetchone()
    final_cumulative = last_row["cumulative_sum"] if last_row else 0

    # 获取规则命中（从分析数据已有的 project_id 查）
    items = []
    for r in rows:
        pid = r["project_id"]
        hit_rule = None
        if pid:
            hits = db.execute(
                "SELECT DISTINCT sr.name FROM sim_results mr "
                "JOIN sim_runs srn ON mr.run_id=srn.id "
                "JOIN sim_rules sr ON srn.rule_id=sr.id "
                "WHERE mr.date=? AND mr.hit_group IS NOT NULL AND srn.project_id=?",
                (r["date"], pid)
            ).fetchall()
            if hits:
                hit_rule = [h["name"] for h in hits]
        items.append({
            "date": r["date"],
            "draw": r["draw_number"],
            "day_seq": r["day_seq"],
            "project_name": r["project_name"] or "",
            "project_id": pid,
            "count_n": r["count_n"],
            "value": r["value"],
            "value_x_47": r["value_x_47"],
            "cumulative_sum": r["cumulative_sum"],
            "result": r["result"],
            "hit_rules": hit_rule,
        })

    db.close()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "cumulative_sum": final_cumulative,
    }


# ==================== 集合管理 ====================

class CollectionIn(BaseModel):
    name: str

class SummaryIn(BaseModel):
    name: str

class RunGroupIn(BaseModel):
    name: str
    project_ids: list = []  # 要包含的项目ID列表

class RunGroupItemUpdate(BaseModel):
    project_ids: list = []  # 要设为的项目ID列表（全量替换）


@app.get("/api/collections")
def list_collections():
    """列出所有集合"""
    db = get_db()
    rows = db.execute("SELECT * FROM collections ORDER BY id DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/api/collections")
def create_collection(c: CollectionIn):
    db = get_db()
    db.execute("INSERT INTO collections (name) VALUES (?)", (c.name,))
    db.commit()
    row = db.execute("SELECT * FROM collections WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "collection": dict(row)}


@app.put("/api/collections/{cid}")
def update_collection(cid: int, c: CollectionIn):
    db = get_db()
    db.execute("UPDATE collections SET name=? WHERE id=?", (c.name, cid))
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/api/collections/{cid}")
def delete_collection(cid: int):
    """删除集合及其下所有汇总+记录组"""
    db = get_db()
    sums = db.execute("SELECT id FROM summaries WHERE collection_id=?", (cid,)).fetchall()
    for s in sums:
        rgs = db.execute("SELECT id FROM run_groups WHERE summary_id=?", (s["id"],)).fetchall()
        for rg in rgs:
            db.execute("DELETE FROM run_group_items WHERE run_group_id=?", (rg["id"],))
            db.execute("DELETE FROM run_group_stats WHERE run_group_id=?", (rg["id"],))
        db.execute("DELETE FROM run_groups WHERE summary_id=?", (s["id"],))
    db.execute("DELETE FROM summaries WHERE collection_id=?", (cid,))
    db.execute("DELETE FROM collections WHERE id=?", (cid,))
    db.commit()
    db.close()
    return {"ok": True}


# --- 汇总 ---

@app.get("/api/collections/{cid}/summaries")
def list_summaries(cid: int):
    """列出某集合下所有汇总，含聚合统计"""
    db = get_db()
    rows = db.execute(
        "SELECT s.*, "
        "  (SELECT COUNT(*) FROM run_groups WHERE summary_id=s.id) as run_count, "
        "  (SELECT COALESCE(SUM(project_count),0) FROM run_group_stats WHERE run_group_id IN (SELECT id FROM run_groups WHERE summary_id=s.id)) as project_count, "
        "  (SELECT COALESCE(SUM(hit_count),0) FROM run_group_stats WHERE run_group_id IN (SELECT id FROM run_groups WHERE summary_id=s.id)) as hit_count, "
        "  (SELECT COALESCE(SUM(total_days),0) FROM run_group_stats WHERE run_group_id IN (SELECT id FROM run_groups WHERE summary_id=s.id)) as total_days, "
        "  (SELECT COALESCE(SUM(profit),0) FROM run_group_stats WHERE run_group_id IN (SELECT id FROM run_groups WHERE summary_id=s.id)) as total_value "
        "FROM summaries s WHERE s.collection_id=? ORDER BY s.id DESC",
        (cid,)
    ).fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        d["hit_rate"] = round(d["hit_count"]/d["total_days"]*100, 1) if d["total_days"] else 0
        result.append(d)
    return result


@app.post("/api/collections/{cid}/summaries")
def create_summary(cid: int, s: SummaryIn):
    db = get_db()
    db.execute("INSERT INTO summaries (collection_id, name) VALUES (?,?)", (cid, s.name))
    db.commit()
    row = db.execute("SELECT * FROM summaries WHERE rowid=last_insert_rowid()").fetchone()
    db.close()
    return {"ok": True, "summary": dict(row)}


@app.put("/api/summaries/{sid}")
def update_summary(sid: int, s: SummaryIn):
    db = get_db()
    db.execute("UPDATE summaries SET name=? WHERE id=?", (s.name, sid))
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/api/summaries/{sid}")
def delete_summary(sid: int):
    db = get_db()
    rgs = db.execute("SELECT id FROM run_groups WHERE summary_id=?", (sid,)).fetchall()
    for rg in rgs:
        db.execute("DELETE FROM run_group_items WHERE run_group_id=?", (rg["id"],))
        db.execute("DELETE FROM run_group_stats WHERE run_group_id=?", (rg["id"],))
    db.execute("DELETE FROM run_groups WHERE summary_id=?", (sid,))
    db.execute("DELETE FROM summaries WHERE id=?", (sid,))
    db.commit()
    db.close()
    return {"ok": True}


# --- 记录组 (Run Group) ---

@app.get("/api/summaries/{sid}/run-groups")
def list_run_groups(sid: int):
    """列出汇总下所有记录组（含各记录累计结果值）"""
    db = get_db()
    rows = db.execute(
        "SELECT rg.*, rgs.project_count, rgs.hit_rate "
        "FROM run_groups rg LEFT JOIN run_group_stats rgs ON rg.id=rgs.run_group_id "
        "WHERE rg.summary_id=? ORDER BY rg.id DESC",
        (sid,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # 计算该记录组的 49 格累计总值
        items = db.execute("SELECT project_id FROM run_group_items WHERE run_group_id=?", (d["id"],)).fetchall()
        pids = [i["project_id"] for i in items]
        grid_data = _build_49_grid(db, pids) if pids else {"grid": []}
        d["total_value"] = sum(g["value"] for g in grid_data.get("grid", []))
        result.append(d)
    db.close()
    return result


@app.post("/api/summaries/{sid}/run-groups")
def create_run_group(sid: int, body: RunGroupIn):
    """创建记录组容器（不运行模拟），关联选中的项目"""
    if not body.project_ids:
        raise HTTPException(400, "至少选一个项目")
    db = get_db()
    summary = db.execute("SELECT * FROM summaries WHERE id=?", (sid,)).fetchone()
    if not summary:
        db.close()
        raise HTTPException(404, "汇总不存在")

    db.execute("INSERT INTO run_groups (summary_id, name) VALUES (?,?)", (sid, body.name))
    rg_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    for pid in body.project_ids:
        proj_name = db.execute("SELECT name FROM projects WHERE id=? AND deleted_at IS NULL", (pid,)).fetchone()
        proj_name = proj_name["name"] if proj_name else f"项目{pid}"
        db.execute(
            "INSERT INTO run_group_items (run_group_id, sim_run_id, project_id, project_name) VALUES (?,0,?,?)",
            (rg_id, pid, proj_name)
        )

    # 自动关联已有 sim_runs
    _link_existing_sim_runs(db, rg_id)

    # 刷新统计
    _refresh_run_group_stats(db, rg_id)
    db.commit()
    db.close()
    return {"ok": True, "run_group_id": rg_id}


def _link_existing_sim_runs(db, rg_id: int):
    """为记录组关联已有 sim_runs（每个项目取最新一条，不限归属）"""
    items = db.execute(
        "SELECT id, project_id FROM run_group_items WHERE run_group_id=? AND sim_run_id=0", (rg_id,)
    ).fetchall()
    for it in items:
        latest = db.execute(
            "SELECT id FROM sim_runs WHERE project_id=? ORDER BY id DESC LIMIT 1",
            (it["project_id"],)
        ).fetchone()
        if latest:
            db.execute("UPDATE run_group_items SET sim_run_id=? WHERE id=?", (latest["id"], it["id"]))
            db.execute("UPDATE sim_runs SET run_group_id=? WHERE id=?", (rg_id, latest["id"]))


def _refresh_run_group_stats(db, rg_id: int):
    """重建记录组统计，含profit（各项目分析累计值之和）"""
    items = db.execute(
        "SELECT rgi.id, rgi.sim_run_id FROM run_group_items rgi WHERE rgi.run_group_id=? AND rgi.sim_run_id > 0", (rg_id,)
    ).fetchall()
    if not items:
        db.execute("INSERT OR REPLACE INTO run_group_stats (run_group_id, project_count, total_days, hit_count, hit_rate, profit) VALUES (?,0,0,0,0,0)", (rg_id,))
        return
    sim_ids = [i["sim_run_id"] for i in items]
    placeholders = ",".join("?" * len(sim_ids))
    rows = db.execute(
        f"SELECT COALESCE(SUM(total_days),0) as td, COALESCE(SUM(hit_count),0) as hc FROM sim_runs WHERE id IN ({placeholders})",
        sim_ids
    ).fetchone()
    td, hc = rows["td"], rows["hc"]
    hr = round(hc / td * 100, 1) if td else 0

    # 计算 profit：每个项目的最后一次累计值之和
    sim_runs = db.execute(
        f"SELECT project_id, hit_count, total_days FROM sim_runs WHERE id IN ({placeholders})", sim_ids
    ).fetchall()
    project_ids = list(set(r["project_id"] for r in sim_runs))
    total_profit = 0
    for pid in project_ids:
        last = db.execute(
            "SELECT cumulative_sum FROM analysis_daily WHERE project_id=? ORDER BY date DESC LIMIT 1", (pid,)
        ).fetchone()
        total_profit += last["cumulative_sum"] if last else 0

    db.execute(
        "INSERT OR REPLACE INTO run_group_stats (run_group_id, project_count, total_days, hit_count, hit_rate, profit) VALUES (?,?,?,?,?,?)",
        (rg_id, len(items), td, hc, hr, total_profit)
    )


def _build_49_grid(db, project_ids: list, target_date: str = None, run_ids: list = None) -> dict:
    """给定项目ID列表，聚合 49 格。target_date 指定日期，不传则取最新日。run_ids 可选指定具体 sim_run"""
    value_map = get_count_map_dict(db)
    if not project_ids:
        return {"last_date": "", "grid": [], "projects": []}

    # 1) 取 sim_runs：优先用 run_ids，否则每个项目取最新
    p = ",".join("?" * len(project_ids))
    if run_ids:
        rp = ",".join("?" * len(run_ids))
        run_rows = db.execute(
            f"SELECT srn.id, srn.project_id, srn.project_name, srn.hit_count, srn.total_days "
            f"FROM sim_runs srn WHERE srn.id IN ({rp})", run_ids
        ).fetchall()
    else:
        run_rows = db.execute(
            f"SELECT srn.id, srn.project_id, srn.project_name, srn.hit_count, srn.total_days "
            f"FROM sim_runs srn "
            f"JOIN (SELECT project_id, MAX(id) as max_id FROM sim_runs WHERE project_id IN ({p}) GROUP BY project_id) mx "
            f"ON srn.project_id=mx.project_id AND srn.id=mx.max_id "
            f"ORDER BY srn.project_id",
            project_ids
        ).fetchall()

    if not run_rows:
        return {"last_date": "", "grid": [], "projects": []}

    run_ids = [r["id"] for r in run_rows]
    rp = ",".join("?" * len(run_ids))
    run_by_pid = {r["project_id"]: r for r in run_rows}

    # 2) 确定 use_date
    if target_date:
        use_date = target_date
    else:
        last = db.execute(
            f"SELECT MAX(date) as dt FROM sim_results WHERE run_id IN ({rp})", run_ids
        ).fetchone()
        use_date = last["dt"] or ""

    # 3) 批量查所有 sim_results
    sim_rows = []
    if use_date:
        sim_rows = db.execute(
            f"SELECT run_id, date, hit_group, group_name, count_n, numbers_json "
            f"FROM sim_results WHERE run_id IN ({rp}) AND date=?",
            run_ids + [use_date]
        ).fetchall()

    # 按 run_id 分组
    from collections import defaultdict
    by_run = defaultdict(list)
    for sr in sim_rows:
        by_run[sr["run_id"]].append(sr)

    # 4) 一次遍历构建 projects + 49格
    projects = []
    grid = {n: 0 for n in range(1, 50)}
    for pr in run_rows:
        groups = by_run.get(pr["id"], [])
        proj_val = 0
        hit_group = ""
        for g in groups:
            nums = json.loads(g["numbers_json"])
            val = value_map.get(g["count_n"], 0)
            proj_val += val * len(nums)
            for n in nums:
                grid[n] = grid.get(n, 0) + val
            if not hit_group:
                hit_group = g["hit_group"] or ""
        projects.append({
            "project_id": pr["project_id"], "project_name": pr["project_name"],
            "last_date": use_date if groups else (use_date if target_date else ""),
            "hit_group": hit_group,
            "value": proj_val,
            "hit_count": pr["hit_count"], "total_days": pr["total_days"],
        })

    grid_list = [{"n": n, "value": grid[n]} for n in range(1, 50)]

    # 5) 补全项目（无 sim_run 的项目）
    proj_miss = db.execute(
        f"SELECT id, name FROM projects WHERE id IN ({p}) AND deleted_at IS NULL", project_ids
    ).fetchall()
    shown_ids = {pr["project_id"] for pr in projects}
    for pm in proj_miss:
        if pm["id"] not in shown_ids:
            projects.append({
                "project_id": pm["id"], "project_name": pm["name"],
                "last_date": use_date if target_date else "",
                "hit_group": "", "value": 0, "hit_count": 0, "total_days": 0,
            })

    rec = db.execute("SELECT draw_number FROM records WHERE date=?", (use_date,)).fetchone()
    return {"last_date": use_date, "grid": grid_list, "projects": projects,
            "draw_number": rec["draw_number"] if rec else None}


@app.get("/api/run-groups/{rgid}/grid")
def get_run_group_grid(rgid: int, date: str = None):
    """记录组: 49值聚合（按项目最新 sim_run）"""
    db = get_db()
    items = db.execute(
        "SELECT project_id FROM run_group_items WHERE run_group_id=?", (rgid,)
    ).fetchall()
    ids = [i["project_id"] for i in items]
    result = _build_49_grid(db, ids, date)
    db.close()
    return result


@app.get("/api/projects/{pid}/grid")
def get_project_grid(pid: int, date: str = None):
    """单项目: 49格明细（点查询用）"""
    db = get_db()
    result = _build_49_grid(db, [pid], date)
    proj = result["projects"][0] if result["projects"] else {}
    grid = result.get("grid", [])
    total = sum(g["value"] for g in grid)
    db.close()
    return {
        "project_name": proj.get("project_name", ""),
        "last_date": result.get("last_date", ""),
        "total": total,
        "draw_number": result.get("draw_number"),
        "grid": grid,
    }


@app.get("/api/summaries/{sid}/grid")
def get_summary_grid(sid: int, date: str = None):
    """汇总: 49值聚合(跨所有记录组)"""
    db = get_db()
    items = db.execute(
        "SELECT DISTINCT rgi.project_id FROM run_group_items rgi "
        "JOIN run_groups rg ON rgi.run_group_id=rg.id "
        "WHERE rg.summary_id=?", (sid,)
    ).fetchall()
    ids = [i["project_id"] for i in items]
    result = _build_49_grid(db, ids, date)
    db.close()
    return result


@app.get("/api/collections/{cid}/grid")
def get_collection_grid(cid: int, date: str = None, summary_ids: str = None):
    """集合: 49值聚合。summary_ids=1,2,3 可选过滤指定汇总。多汇总时分别取各自日期再合并"""
    db = get_db()
    if summary_ids:
        sids = [int(x.strip()) for x in summary_ids.split(",") if x.strip()]
        if len(sids) == 1:
            # 单汇总：直接走原逻辑（快速路径）
            p = ",".join("?" * len(sids))
            rows = db.execute(
                f"SELECT DISTINCT rgi.project_id FROM run_group_items rgi "
                f"JOIN run_groups rg ON rgi.run_group_id=rg.id "
                f"WHERE rg.summary_id IN ({p})", sids
            ).fetchall()
            ids = [r["project_id"] for r in rows]
            result = _build_49_grid(db, ids, date)
        else:
            # 多汇总：分别计算每个汇总的 grid，再合并（各自用各自的日期）
            grid = {n: 0 for n in range(1, 50)}
            projects = []
            last_date = ""
            for sid in sids:
                rows = db.execute(
                    "SELECT DISTINCT rgi.project_id FROM run_group_items rgi "
                    "JOIN run_groups rg ON rgi.run_group_id=rg.id "
                    "WHERE rg.summary_id=?", (sid,)
                ).fetchall()
                ids = [r["project_id"] for r in rows]
                sub = _build_49_grid(db, ids, date)
                if sub["last_date"] and (not last_date or sub["last_date"] > last_date):
                    last_date = sub["last_date"]
                for g in sub["grid"]:
                    grid[g["n"]] += g["value"]
                projects.extend(sub.get("projects", []))
            rec = db.execute("SELECT draw_number FROM records WHERE date=?", (last_date,)).fetchone()
            result = {
                "last_date": last_date,
                "grid": [{"n": n, "value": grid[n]} for n in range(1, 50)],
                "projects": projects,
                "draw_number": rec["draw_number"] if rec else None
            }
    else:
        items = db.execute("SELECT id FROM projects WHERE deleted_at IS NULL").fetchall()
        ids = [i["id"] for i in items]
        result = _build_49_grid(db, ids, date)
    db.close()
    return result


@app.get("/api/collections/{cid}/num-summary-map")
def get_num_summary_map(cid: int):
    """返回 1-49 每个数字归属的汇总名称。走 project_groups → project → run_group → summary 链路。"""
    db = get_db()
    summaries = db.execute("SELECT id, name FROM summaries WHERE collection_id=? ORDER BY name", (cid,)).fetchall()
    sid_names = {s["id"]: s["name"] for s in summaries}
    if not sid_names:
        db.close()
        return {"map": {}, "summaries": []}

    rows = db.execute("""
        SELECT pg.numbers, s.id as sid, s.name as sname
        FROM project_groups pg
        JOIN projects p ON p.id = pg.project_id AND p.deleted_at IS NULL
        JOIN run_group_items rgi ON rgi.project_id = p.id
        JOIN run_groups rg ON rg.id = rgi.run_group_id
        JOIN summaries s ON s.id = rg.summary_id AND s.collection_id = ?
        WHERE pg.deleted_at IS NULL
    """, (cid,)).fetchall()

    db.close()
    # 数→汇总计数
    num_counter = {}
    for r in rows:
        nums = json.loads(r["numbers"]) if r["numbers"] else []
        for n in nums:
            n = int(n)
            if 1 <= n <= 49:
                if n not in num_counter:
                    num_counter[n] = {}
                sname = r["sname"]
                num_counter[n][sname] = num_counter[n].get(sname, 0) + 1

    # 选归属最多的汇总
    result = {}
    for n in range(1, 50):
        if n in num_counter:
            best = max(num_counter[n], key=num_counter[n].get)
            result[n] = best
        else:
            result[n] = None

    return {"map": result, "summaries": list(sid_names.values())}


class RunGroupExec(BaseModel):
    start_date: str
    end_date: str


@app.post("/api/run-groups/{rgid}/run")
def exec_run_group(rgid: int, body: RunGroupExec):
    """为记录组所有项目运行模拟（自动取各项目绑定的规则）"""
    db = get_db()
    rg = db.execute("SELECT * FROM run_groups WHERE id=?", (rgid,)).fetchone()
    if not rg:
        db.close()
        raise HTTPException(404, "记录组不存在")

    items = db.execute(
        "SELECT id, project_id FROM run_group_items WHERE run_group_id=?", (rgid,)
    ).fetchall()
    if not items:
        db.close()
        raise HTTPException(400, "记录组内无项目")

    results = []
    for it in items:
        # 自动取该项目绑定的活跃规则
        rule = db.execute(
            "SELECT id FROM sim_rules WHERE project_id=? AND is_active=1 ORDER BY id LIMIT 1",
            (it["project_id"],)
        ).fetchone()
        if not rule:
            results.append({"project_id": it["project_id"], "error": "该项目无活跃规则"})
            continue
        r = run_simulation(db, rule["id"], body.start_date, body.end_date, it["project_id"])
        db.execute("UPDATE run_group_items SET sim_run_id=? WHERE id=?", (r["run_id"], it["id"]))
        db.execute("UPDATE sim_runs SET run_group_id=? WHERE id=?", (rgid, r["run_id"]))
        results.append({"project_id": it["project_id"], "rule_id": rule["id"], "run_id": r["run_id"], **r})

    _refresh_run_group_stats(db, rgid)
    db.commit()
    db.close()
    return {"ok": True, "runs": results}


@app.delete("/api/run-groups/{rgid}")
def delete_run_group(rgid: int):
    """删除记录组及其项目关联"""
    db = get_db()
    items = db.execute("SELECT sim_run_id FROM run_group_items WHERE run_group_id=?", (rgid,)).fetchall()
    for it in items:
        db.execute("UPDATE sim_runs SET run_group_id=NULL WHERE id=?", (it["sim_run_id"],))
    db.execute("DELETE FROM run_group_items WHERE run_group_id=?", (rgid,))
    db.execute("DELETE FROM run_group_stats WHERE run_group_id=?", (rgid,))
    db.execute("DELETE FROM run_groups WHERE id=?", (rgid,))
    db.commit()
    db.close()
    return {"ok": True}


class RunGroupItemAdd(BaseModel):
    project_id: int
    sim_run_id: int = 0
    rule_id: int = 0


@app.post("/api/run-groups/{rgid}/items")
def add_run_group_item(rgid: int, body: RunGroupItemAdd):
    """添加单个项目到记录组"""
    db = get_db()
    rg = db.execute("SELECT * FROM run_groups WHERE id=?", (rgid,)).fetchone()
    if not rg:
        db.close()
        raise HTTPException(404, "记录组不存在")
    existing = db.execute(
        "SELECT id FROM run_group_items WHERE run_group_id=? AND project_id=?", (rgid, body.project_id)
    ).fetchone()
    if existing:
        db.close()
        raise HTTPException(400, "项目已在记录组中")
    proj_name = db.execute("SELECT name FROM projects WHERE id=? AND deleted_at IS NULL", (body.project_id,)).fetchone()
    proj_name = proj_name["name"] if proj_name else f"项目{body.project_id}"
    db.execute(
        "INSERT INTO run_group_items (run_group_id, sim_run_id, project_id, project_name) VALUES (?,?,?,?)",
        (rgid, body.sim_run_id, body.project_id, proj_name)
    )
    _link_existing_sim_runs(db, rgid)
    _refresh_run_group_stats(db, rgid)
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/api/run-group-items/{item_id}")
def delete_run_group_item(item_id: int):
    """删除记录组中的单个项目"""
    db = get_db()
    item = db.execute("SELECT * FROM run_group_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        db.close()
        raise HTTPException(404, "项目不存在")
    rgid = item["run_group_id"]
    db.execute("DELETE FROM run_group_items WHERE id=?", (item_id,))
    _refresh_run_group_stats(db, rgid)
    db.commit()
    db.close()
    return {"ok": True}


@app.put("/api/run-groups/{rgid}/items")
def update_run_group_items(rgid: int, body: RunGroupItemUpdate):
    """修改记录组项目列表（全量替换），方便增减项目"""
    if not body.project_ids:
        raise HTTPException(400, "至少保留一个项目")
    db = get_db()
    rg = db.execute("SELECT * FROM run_groups WHERE id=?", (rgid,)).fetchone()
    if not rg:
        db.close()
        raise HTTPException(404, "记录组不存在")

    # 删除不在新列表中的项目
    db.execute("DELETE FROM run_group_items WHERE run_group_id=? AND project_id NOT IN ({seq})".format(
        seq=",".join("?"*len(body.project_ids))
    ), [rgid] + body.project_ids)

    # 添加新项目
    for pid in body.project_ids:
        existing = db.execute(
            "SELECT id FROM run_group_items WHERE run_group_id=? AND project_id=?", (rgid, pid)
        ).fetchone()
        if existing: continue
        proj_name = db.execute("SELECT name FROM projects WHERE id=? AND deleted_at IS NULL", (pid,)).fetchone()
        proj_name = proj_name["name"] if proj_name else f"项目{pid}"
        db.execute(
            "INSERT INTO run_group_items (run_group_id, sim_run_id, project_id, project_name) VALUES (?,0,?,?)",
            (rgid, pid, proj_name)
        )

    _link_existing_sim_runs(db, rgid)
    _refresh_run_group_stats(db, rgid)
    db.commit()
    db.close()
    return {"ok": True}


# --- 演算当天：按范围取项目+规则 ---

@app.get("/api/scope/projects")
def get_scope_projects(
    collection_id: Optional[int] = Query(None),
    summary_id: Optional[int] = Query(None),
    run_group_id: Optional[int] = Query(None),
):
    """按范围（集合/汇总/记录组）获取去重项目列表及其活跃规则。
    不传任何参数则返回全部项目。"""
    db = get_db()
    base_sql = (
        "SELECT DISTINCT p.id as project_id, p.name as project_name, "
        "sr.id as rule_id, sr.name as rule_name, sr.shift_amount "
        "FROM projects p "
        "LEFT JOIN sim_rules sr ON sr.project_id = p.id AND sr.is_active = 1 "
    )
    if run_group_id:
        rows = db.execute(
            base_sql +
            "JOIN run_group_items rgi ON rgi.project_id = p.id "
            "WHERE rgi.run_group_id = ? AND p.deleted_at IS NULL",
            (run_group_id,)
        ).fetchall()
    elif summary_id:
        rows = db.execute(
            base_sql +
            "JOIN run_group_items rgi ON rgi.project_id = p.id "
            "JOIN run_groups rg ON rgi.run_group_id = rg.id "
            "WHERE rg.summary_id = ? AND p.deleted_at IS NULL",
            (summary_id,)
        ).fetchall()
    elif collection_id:
        rows = db.execute(
            base_sql +
            "JOIN run_group_items rgi ON rgi.project_id = p.id "
            "JOIN run_groups rg ON rgi.run_group_id = rg.id "
            "JOIN summaries s ON rg.summary_id = s.id "
            "WHERE s.collection_id = ? AND p.deleted_at IS NULL",
            (collection_id,)
        ).fetchall()
    else:
        rows = db.execute(
            base_sql + "WHERE p.deleted_at IS NULL"
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# --- 四层下钻查询 ---

@app.get("/api/run-groups/{rgid}/items")
def get_run_group_items(rgid: int):
    """获取记录组下所有项目结果"""
    db = get_db()
    rows = db.execute(
        "SELECT rgi.*, srn.hit_count, srn.total_days, srn.start_date, srn.end_date "
        "FROM run_group_items rgi LEFT JOIN sim_runs srn ON rgi.sim_run_id=srn.id AND rgi.sim_run_id > 0 "
        "WHERE rgi.run_group_id=? ORDER BY rgi.id",
        (rgid,)
    ).fetchall()
    db.close()
    items = []
    for r in rows:
        d = dict(r)
        d["hit_rate"] = round(d["hit_count"]/d["total_days"]*100, 1) if d["total_days"] else 0
        items.append(d)
    return items


@app.get("/api/run-groups/{rgid}/results")
def get_run_group_results(rgid: int):
    """获取记录组下所有项目的日结果（合并视图）"""
    db = get_db()
    items = db.execute(
        "SELECT sim_run_id FROM run_group_items WHERE run_group_id=? ORDER BY id", (rgid,)
    ).fetchall()
    if not items:
        db.close()
        return {"items": []}

    sim_run_ids = [i["sim_run_id"] for i in items]
    placeholders = ",".join("?" * len(sim_run_ids))
    rows = db.execute(
        f"SELECT * FROM sim_results WHERE run_id IN ({placeholders}) ORDER BY date, run_id, group_name",
        sim_run_ids
    ).fetchall()
    db.close()

    # 合并为 daily 结构
    daily = {}
    for r in rows:
        dt = r["date"]
        key = f"{dt}_{r['run_id']}"
        if key not in daily:
            daily[key] = {"date": dt, "run_id": r["run_id"], "draw_number": r["draw_number"],
                          "hit_group": r["hit_group"], "groups": {}}
        daily[key]["groups"][r["group_name"]] = {
            "numbers": json.loads(r["numbers_json"]),
            "count_n": r["count_n"],
        }
    return {"items": sorted(daily.values(), key=lambda x: x["date"], reverse=True)}


# --- 盈亏日明细 ---

@app.get("/api/scope/daily")
def get_scope_daily(
    collection_id: Optional[int] = Query(None),
    summary_id: Optional[int] = Query(None),
    run_group_id: Optional[int] = Query(None),
    date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    level: str = "projects",  # projects | run_groups | summaries
    expand: bool = False,
    page: int = 1,
    page_size: int = 30,
):
    """按范围取盈亏明细，支持单日/时间段，三级钻取；expand=true 时返回树形嵌套"""
    # 模式判断
    is_range = bool(start_date and end_date)
    if is_range:
        date_filter = "date BETWEEN ? AND ?"
        date_params = [start_date, end_date]
    else:
        date_filter = "date = ?"
        date_params = [date]
    db = get_db()

    # ==================== 展开模式：树形嵌套 ====================
    if expand and is_range and collection_id:
        value_map = get_count_map_dict(db)
        # 查该集合下所有汇总
        summaries = db.execute(
            "SELECT id, name FROM summaries WHERE collection_id=?", (collection_id,)
        ).fetchall()
        result = []
        for srow in summaries:
            sid = srow["id"]
            # 该汇总下所有记录组
            rgs = db.execute(
                "SELECT id, name FROM run_groups WHERE summary_id=?", (sid,)
            ).fetchall()
            rg_list = []
            for rgrow in rgs:
                rgid = rgrow["id"]
                # 该记录组下所有项目
                projs = db.execute("""
                    SELECT p.id, p.name, rgi.id as item_id
                    FROM run_group_items rgi
                    JOIN projects p ON p.id = rgi.project_id
                    WHERE rgi.run_group_id = ? AND p.deleted_at IS NULL
                """, (rgid,)).fetchall()
                proj_list = []
                for prow in projs:
                    pid = prow["id"]
                    # 项目在该时间段的分析数据
                    ad_rows = db.execute(
                        f"SELECT draw_number, value, cumulative_sum, result, date FROM analysis_daily WHERE project_id=? AND {date_filter} ORDER BY date",
                        [pid] + date_params
                    ).fetchall()
                    results = [r["result"] for r in ad_rows]
                    proj_list.append({
                        "name": prow["name"],
                        "id": pid,
                        "item_id": prow["item_id"],
                        "days": len(ad_rows),
                        "total_result": sum(results),
                        "pos_days": sum(1 for r in results if r > 0),
                        "neg_days": sum(1 for r in results if r < 0),
                        "daily": [{"date": r["date"], "draw": r["draw_number"],
                                   "value": r["value"], "cumulative": r["cumulative_sum"],
                                   "result": r["result"]} for r in ad_rows],
                    })
                if not proj_list: continue
                # 记录组汇总
                rg_results = [r for p in proj_list for r in [p["total_result"]]]
                rg_list.append({
                    "name": rgrow["name"],
                    "id": rgid,
                    "project_count": len(proj_list),
                    "days": proj_list[0]["days"] if proj_list else 0,
                    "total_result": sum(p["total_result"] for p in proj_list),
                    "pos_days": sum(p["pos_days"] for p in proj_list),
                    "neg_days": sum(p["neg_days"] for p in proj_list),
                    "projects": proj_list,
                })
            if not rg_list: continue
            result.append({
                "name": srow["name"],
                "id": sid,
                "type": "summary",
                "project_count": sum(r["project_count"] for r in rg_list),
                "days": rg_list[0]["days"] if rg_list else 0,
                "total_result": sum(r["total_result"] for r in rg_list),
                "pos_days": sum(r["pos_days"] for r in rg_list),
                "neg_days": sum(r["neg_days"] for r in rg_list),
                "run_groups": rg_list,
            })
        db.close()
        return {"trees": result, "is_range": True, "expand": True}

    # ==================== 第一层：集合 → 汇总列表 ====================
    if level == "summaries" and collection_id:
        value_map = get_count_map_dict(db)
        # 查该集合下所有汇总
        summaries = db.execute("""
            SELECT s.id, s.name, s.created_at
            FROM summaries s WHERE s.collection_id = ?
        """, (collection_id,)).fetchall()
        items = []
        for srow in summaries:
            sid = srow["id"]
            # 获取该汇总下所有 project_id
            pids_rows = db.execute("""
                SELECT DISTINCT rgi.project_id
                FROM run_group_items rgi
                JOIN run_groups rg ON rgi.run_group_id = rg.id
                WHERE rg.summary_id = ?
            """, (sid,)).fetchall()
            spids = [r["project_id"] for r in pids_rows]
            if not spids: continue

            spids_sql = ','.join('?' * len(spids))
            if is_range:
                # ===== 范围模式：按天分行 =====
                daily_rows = db.execute(
                    f"SELECT date, COUNT(*) as cnt, COALESCE(SUM(value),0) as tv, COALESCE(SUM(result),0) as tr FROM analysis_daily WHERE project_id IN ({spids_sql}) AND {date_filter} GROUP BY date ORDER BY date",
                    spids + date_params
                ).fetchall()
                for dr in daily_rows:
                    items.append({
                        "name": srow["name"],
                        "type": "summary",
                        "id": sid,
                        "date": dr["date"],
                        "project_count": len(spids),
                        "total_value": dr["tv"] or 0,
                        "total_result": dr["tr"] or 0,
                        "rank": None,
                        "created_at": srow["created_at"],
                    })
                continue

            # ===== 单日模式 =====
            # 取 draw_number
            dr = db.execute(
                f"SELECT draw_number FROM analysis_daily WHERE project_id IN ({spids_sql}) AND {date_filter} LIMIT 1",
                spids + date_params
            ).fetchone()
            draw = dr["draw_number"] if dr else None

            # 聚合 analysis_daily
            agg = db.execute(
                f"SELECT COUNT(*) as cnt, COALESCE(SUM(value),0) as tv, COALESCE(SUM(result),0) as tr FROM analysis_daily WHERE project_id IN ({spids_sql}) AND {date_filter}",
                spids + date_params
            ).fetchone()

            # 构建联合 49 格：汇总所有项目的 sim_results
            grid = {n: 0 for n in range(1, 50)}
            for pid in spids:
                rid_row = db.execute(
                    "SELECT id FROM sim_runs WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,)
                ).fetchone()
                if not rid_row: continue
                groups = db.execute(
                    f"SELECT numbers_json, count_n FROM sim_results WHERE run_id=? AND {date_filter}",
                    (rid_row["id"],) + tuple(date_params)
                ).fetchall()
                for g in groups:
                    nums = json.loads(g["numbers_json"])
                    val = value_map.get(g["count_n"], 0)
                    for n in nums:
                        grid[n] = grid.get(n, 0) + val

            # 抽签排位（按1-49全格，不剔零不剔重）
            draw_val = grid.get(draw, 0) if draw else 0
            rank = None
            if draw and grid and draw_val > 0:
                vals = sorted(grid.values(), reverse=True)
                if draw_val in vals:
                    rank = vals.index(draw_val) + 1

            items.append({
                "name": srow["name"],
                "type": "summary",
                "id": sid,
                "project_count": agg["cnt"] or 0,
                "draw": draw,
                "draw_value": draw_val,
                "total_value": agg["tv"] or 0,
                "total_result": agg["tr"] or 0,
                "rank": rank,
                "created_at": srow["created_at"],
            })
        # 按名称排序（汇总1, 汇总2, ...）
        import re
        def sort_key(x):
            m = re.search(r'(\d+)', x["name"])
            return int(m.group(1)) if m else 999
        items.sort(key=sort_key)
        db.close()
        return {"items": items, "total": len(items), "page": 1, "total_pages": 1, "level": level, "is_range": is_range}

    # ==================== 第二层：汇总 → 记录组列表 ====================
    if level == "run_groups" and summary_id:
        value_map = get_count_map_dict(db)
        # 查该汇总下所有记录组
        rgs = db.execute("""
            SELECT rg.id, rg.name FROM run_groups rg WHERE rg.summary_id = ?
        """, (summary_id,)).fetchall()
        items = []
        for rgrow in rgs:
            rgid = rgrow["id"]
            # 获取该记录组下所有 project_id
            pids_rows = db.execute("""
                SELECT project_id FROM run_group_items WHERE run_group_id = ?
            """, (rgid,)).fetchall()
            spids = [r["project_id"] for r in pids_rows]
            if not spids: continue

            spids_sql = ','.join('?' * len(spids))
            if is_range:
                daily_rows = db.execute(
                    f"SELECT date, COUNT(*) as cnt, COALESCE(SUM(value),0) as tv, COALESCE(SUM(result),0) as tr FROM analysis_daily WHERE project_id IN ({spids_sql}) AND {date_filter} GROUP BY date ORDER BY date",
                    spids + date_params
                ).fetchall()
                for dr in daily_rows:
                    items.append({
                        "name": rgrow["name"],
                        "type": "run_group",
                        "id": rgid,
                        "date": dr["date"],
                        "project_count": len(spids),
                        "total_value": dr["tv"] or 0,
                        "total_result": dr["tr"] or 0,
                        "rank": None,
                    })
                continue

            # 取 draw_number
            dr = db.execute(
                f"SELECT draw_number FROM analysis_daily WHERE project_id IN ({spids_sql}) AND {date_filter} LIMIT 1",
                spids + date_params
            ).fetchone()
            draw = dr["draw_number"] if dr else None

            # 聚合 analysis_daily
            agg = db.execute(
                f"SELECT COUNT(*) as cnt, COALESCE(SUM(value),0) as tv, COALESCE(SUM(result),0) as tr FROM analysis_daily WHERE project_id IN ({spids_sql}) AND {date_filter}",
                spids + date_params
            ).fetchone()

            # 构建联合 49 格
            grid = {n: 0 for n in range(1, 50)}
            for pid in spids:
                rid_row = db.execute(
                    "SELECT id FROM sim_runs WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,)
                ).fetchone()
                if not rid_row: continue
                groups = db.execute(
                    f"SELECT numbers_json, count_n FROM sim_results WHERE run_id=? AND {date_filter}",
                    (rid_row["id"],) + tuple(date_params)
                ).fetchall()
                for g in groups:
                    nums = json.loads(g["numbers_json"])
                    val = value_map.get(g["count_n"], 0)
                    for n in nums:
                        grid[n] = grid.get(n, 0) + val

            # 抽签排位（按1-49全格，不剔零不剔重）
            draw_val = grid.get(draw, 0) if draw else 0
            rank = None
            if draw and grid and draw_val > 0:
                vals = sorted(grid.values(), reverse=True)
                if draw_val in vals:
                    rank = vals.index(draw_val) + 1

            items.append({
                "name": rgrow["name"],
                "type": "run_group",
                "id": rgid,
                "project_count": agg["cnt"] or 0,
                "draw": draw,
                "draw_value": draw_val,
                "total_value": agg["tv"] or 0,
                "total_result": agg["tr"] or 0,
                "rank": rank,
            })
        # 按联合 49 格排位排序
        items.sort(key=lambda x: (x["rank"] or 999))
        db.close()
        return {"items": items, "total": len(items), "page": 1, "total_pages": 1, "level": level}

    # ==================== 第三层：项目明细（原有逻辑） ====================
    # 解析范围→project_ids
    if run_group_id:
        rows = db.execute("SELECT project_id FROM run_group_items WHERE run_group_id=?", (run_group_id,)).fetchall()
    elif summary_id:
        rows = db.execute(
            "SELECT DISTINCT rgi.project_id FROM run_group_items rgi JOIN run_groups rg ON rgi.run_group_id=rg.id WHERE rg.summary_id=?",
            (summary_id,)
        ).fetchall()
    elif collection_id:
        rows = db.execute(
            "SELECT DISTINCT rgi.project_id FROM run_group_items rgi JOIN run_groups rg ON rgi.run_group_id=rg.id JOIN summaries s ON rg.summary_id=s.id WHERE s.collection_id=?",
            (collection_id,)
        ).fetchall()
    else:
        rows = db.execute("SELECT id as project_id FROM projects WHERE deleted_at IS NULL").fetchall()
    pids = [r["project_id"] for r in rows]
    if not pids:
        db.close()
        return {"items": [], "total": 0, "page": 1, "total_pages": 0, "level": "projects", "is_range": is_range}

    # count→value 映射
    value_map = get_count_map_dict(db)

    # 每个项目取最新 sim_run
    pids_sql = ",".join("?" * len(pids))
    runs = db.execute(
        f"SELECT srn.id, srn.project_id FROM sim_runs srn WHERE srn.project_id IN ({pids_sql}) AND srn.id = (SELECT MAX(id) FROM sim_runs WHERE project_id=srn.project_id)",
        pids
    ).fetchall()
    run_by_pid = {r["project_id"]: r["id"] for r in runs}

    # 查 analysis_daily
    where = f"WHERE project_id IN ({pids_sql}) AND {date_filter}"
    total = db.execute(
        f"SELECT COUNT(*) FROM analysis_daily {where}", pids + date_params
    ).fetchone()[0]
    offset = (page - 1) * page_size
    daily_rows = db.execute(
        f"SELECT * FROM analysis_daily {where} ORDER BY date DESC, project_id LIMIT ? OFFSET ?",
        pids + date_params + [page_size, offset]
    ).fetchall()

    # 预加载本页需要用到的 sim_results（按 run_id + date 批量取，仅用于排位计算）
    items = []
    for r in daily_rows:
        pid = r["project_id"]
        rid = run_by_pid.get(pid)
        dt = r["date"]
        draw = r["draw_number"]
        # 构建 49 格（仅用于排位）
        grid = {n: 0 for n in range(1, 50)}
        if rid:
            groups = db.execute(
                "SELECT numbers_json, count_n FROM sim_results WHERE run_id=? AND date=?",
                (rid, dt)
            ).fetchall()
            for g in groups:
                nums = json.loads(g["numbers_json"])
                val = value_map.get(g["count_n"], 0)
                for n in nums:
                    grid[n] = grid.get(n, 0) + val
        # 抽签排位（按1-49全格，不剔零不剔重）
        draw_val = grid.get(draw, 0) if draw else 0
        rank = None
        if draw and grid and draw_val > 0:
            vals = sorted(grid.values(), reverse=True)
            if draw_val in vals:
                rank = vals.index(draw_val) + 1
        items.append({
            "name": r["project_name"],
            "type": "project",
            "id": pid,
            "date": dt,
            "draw": draw,
            "rank": rank,
            "draw_value": r["value"],
            "cumulative": r["cumulative_sum"],
            "result": r["result"],
        })
    db.close()
    # 计算当前范围的汇总（全量，不受分页影响）
    agg = {"total_result": 0, "total_value": 0, "project_count": 0}
    if pids:
        agg_db = get_db()
        agg_row = agg_db.execute(
            f"SELECT COUNT(DISTINCT project_id) as cnt, SUM(value) as tv, SUM(result) as tr FROM analysis_daily WHERE project_id IN ({pids_sql}) AND {date_filter}",
            pids + date_params
        ).fetchone()
        if agg_row:
            agg["project_count"] = agg_row["cnt"] or 0
            agg["total_value"] = agg_row["tv"] or 0
            agg["total_result"] = agg_row["tr"] or 0
        agg_db.close()
    return {
        "items": items,
        "total": total,
        "page": page,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "summary": agg,
        "level": "projects",
        "is_range": is_range,
    }


@app.get("/api/run-group-items/{item_id}/grid")
def get_item_grid(item_id: int, date: str = None):
    """单个项目的 49 格明细 — sim_run_id=0 时自动取该项目最新 sim_run"""
    db = get_db()
    item = db.execute("SELECT * FROM run_group_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        db.close()
        raise HTTPException(404, "项目不存在")

    run_id = item["sim_run_id"]
    # 检查当前 run_id 是否有数据，没有则回退到最新有数据的 sim_run
    has_data = run_id > 0 and db.execute("SELECT 1 FROM sim_results WHERE run_id=? LIMIT 1", (run_id,)).fetchone()
    if not has_data:
        latest = db.execute(
            "SELECT id FROM sim_runs WHERE project_id=? AND id IN (SELECT DISTINCT run_id FROM sim_results) ORDER BY id DESC LIMIT 1",
            (item["project_id"],)
        ).fetchone()
        if latest:
            run_id = latest["id"]
            db.execute("UPDATE run_group_items SET sim_run_id=? WHERE id=?", (run_id, item_id))
            db.commit()
        else:
            db.close()
            return {"project_name": item["project_name"], "last_date": "", "grid": [], "total": 0}

    value_map = get_count_map_dict(db)
    if date:
        use_date = date
    else:
        last = db.execute("SELECT MAX(date) as dt FROM sim_results WHERE run_id=?", (run_id,)).fetchone()
        use_date = last["dt"] or ""

    if not use_date:
        db.close()
        return {"project_name": item["project_name"], "last_date": "", "grid": []}

    # 获取该日所有组
    groups = db.execute(
        "SELECT group_name, count_n, numbers_json FROM sim_results WHERE run_id=? AND date=?",
        (run_id, use_date)
    ).fetchall()

    grid = {n: 0 for n in range(1, 50)}
    for g in groups:
        nums = json.loads(g["numbers_json"])
        val = value_map.get(g["count_n"], 0)
        for n in nums:
            grid[n] = grid.get(n, 0) + val

    grid_list = [{"n": n, "value": grid[n]} for n in range(1, 50)]
    total = sum(g["value"] for g in grid_list)
    rec = db.execute("SELECT draw_number FROM records WHERE date=?", (use_date,)).fetchone()

    db.close()
    return {
        "project_name": item["project_name"],
        "last_date": use_date,
        "grid": grid_list,
        "total": total,
        "draw_number": rec["draw_number"] if rec else None,
    }


# ==================== 数据导出 API ====================

def _compute_snapshot(db, collection_id: int, use_date: str):
    """从 analysis_daily 读当日快照。返回 (summaries, daily_amount, draw_number, project_details, grid_details)。
    project_details: [(summary_name, summary_id, project_id, project_name, result, grid_count), ...]
    grid_details: [(summary_name, project_id, project_name, count_n, value, value_x_47, cumulative_sum), ...]"""
    from collections import defaultdict

    summaries = db.execute(
        "SELECT id, name FROM summaries WHERE collection_id=? ORDER BY name",
        (collection_id,)
    ).fetchall()

    # 汇总→项目映射
    summary_projects = {}
    all_pids = set()
    pid_to_name = {}
    for s in summaries:
        rows = db.execute(
            "SELECT DISTINCT rgi.project_id, p.name FROM run_group_items rgi "
            "JOIN run_groups rg ON rg.id = rgi.run_group_id "
            "JOIN projects p ON p.id = rgi.project_id "
            "WHERE rg.summary_id=?", (s["id"],)
        ).fetchall()
        pids = [r[0] for r in rows]
        summary_projects[s["id"]] = pids
        all_pids.update(pids)
        for r in rows:
            pid_to_name[r[0]] = r[1]

    # 查 analysis_daily
    if not all_pids:
        return [], 0, None, [], []

    pids_str = ",".join("?" * len(all_pids))
    ad_rows = db.execute(
        f"SELECT project_id, project_name, count_n, value, value_x_47, cumulative_sum, result "
        f"FROM analysis_daily WHERE date=? AND project_id IN ({pids_str})",
        [use_date] + list(all_pids)
    ).fetchall()

    # project_id → {result, grids}
    proj_data = {}
    for r in ad_rows:
        pid = r["project_id"]
        if pid not in proj_data:
            proj_data[pid] = {"result": 0, "grids": []}
        proj_data[pid]["result"] = r["result"]  # 取最后一条的 result（同一项目多条时取最后）
        proj_data[pid]["grids"].append(r)
    
    # 汇总项目数重新从实际 analysis_daily 有数据的项目数取
    actual_pids = set(r["project_id"] for r in ad_rows)

    result_list = []
    daily_amount = 0
    project_details = []
    grid_details = []
    total_pid_count = 0

    # 次数→值映射
    cv_rows = db.execute("SELECT count_n, value FROM count_value_map").fetchall()
    cv_map = {r["count_n"]: r["value"] for r in cv_rows}

    for s in summaries:
        pids = summary_projects[s["id"]]
        proj_count = 0
        total_value = 0
        total_grids = 0
        
        for pid in pids:
            if pid not in proj_data:
                continue
            proj_count += 1
            pd = proj_data[pid]
            pname = pid_to_name.get(pid, f"项目{pid}")
            proj_val = pd["result"]
            total_value += proj_val
            total_grids += len(pd["grids"])
            
            project_details.append((s["name"], s["id"], pid, pname, proj_val, len(pd["grids"])))
            
            for g in pd["grids"]:
                grid_details.append((
                    s["name"], pid, pname,
                    g["count_n"], g["value"], g["value_x_47"], g["cumulative_sum"]
                ))
        
        total_pid_count += proj_count
        daily_amount += total_value
        
        # ── 1-49 排位：计算各位置累计值，抽签号排第几 ──
        draw_value_rank = None
        draw_rec_for_rank = db.execute("SELECT draw_number FROM records WHERE date=?", (use_date,)).fetchone()
        draw_num = draw_rec_for_rank["draw_number"] if draw_rec_for_rank else None
        
        if draw_num and pids:
            # 获取每个项目当天的 sim_results（组→次数→数字）
            pids_str = ",".join("?" * len(pids))
            sr_rows = db.execute(
                f"SELECT srn.project_id, sr.group_name, sr.count_n, sr.numbers_json "
                f"FROM sim_results sr "
                f"JOIN sim_runs srn ON sr.run_id = srn.id "
                f"WHERE srn.project_id IN ({pids_str}) AND sr.date=? "
                f"AND srn.id = (SELECT MAX(id) FROM sim_runs WHERE project_id = srn.project_id)",
                list(pids) + [use_date]
            ).fetchall()
            
            if sr_rows:
                # 累积 1-49 各位置的值
                pos_values = {n: 0 for n in range(1, 50)}
                for r in sr_rows:
                    nums = json.loads(r["numbers_json"])
                    val = cv_map.get(r["count_n"], 0)
                    for num in nums:
                        if 1 <= num <= 49:
                            pos_values[num] += val
                
                # 排序，找抽签号的排位（值高→排位小）
                sorted_pos = sorted(pos_values.items(), key=lambda x: x[1], reverse=True)
                for rank, (num, _) in enumerate(sorted_pos, 1):
                    if num == draw_num:
                        draw_value_rank = rank
                        break
        
        # 命中率
        stats = db.execute(
            "SELECT COALESCE(SUM(rgs.hit_count),0) as hc, "
            "COALESCE(SUM(rgs.total_days),0) as td "
            "FROM run_group_stats rgs "
            "WHERE rgs.run_group_id IN (SELECT id FROM run_groups WHERE summary_id=?)",
            (s["id"],)
        ).fetchone()
        hit_rate = round(stats["hc"] / stats["td"] * 100, 1) if stats["td"] else 0
        
        result_list.append({
            "name": s["name"], "projects": proj_count,
            "hit_rate": hit_rate, "total_value": round(total_value, 2),
            "draw_value_rank": draw_value_rank,
        })

    draw_rec = db.execute("SELECT draw_number FROM records WHERE date=?", (use_date,)).fetchone()
    return result_list, round(daily_amount, 2), draw_rec["draw_number"] if draw_rec else None, project_details, grid_details


@app.post("/api/export/save-daily")
def save_daily_snapshot(collection_id: int, date: str = None):
    """手动触发：计算当日49格数据并存入 daily_snapshots + daily_project_snapshots
    
    特殊集合 14/16：从 A级集合(19) 拉快照聚合，不需自己算项目
    """
    db = get_db()
    from datetime import date as dt

    if date:
        use_date = date
    else:
        rec = db.execute("SELECT MAX(date) as dt FROM records").fetchone()
        use_date = rec["dt"] or dt.today().isoformat()

    # ── 集合14/16：从集合19的 daily_snapshots 拉取当日值 ──
    if collection_id in (14, 16):
        max_n = 4 if collection_id == 14 else 6

        src_rows = db.execute(
            "SELECT summary_name, total_value, draw_value_rank "
            "FROM daily_snapshots WHERE date=? AND collection_id=19 ORDER BY summary_id",
            (use_date,)
        ).fetchall()

        if not src_rows:
            db.close()
            return {"ok": True, "date": use_date, "draw_number": None, "saved": 0,
                    "daily_amount": 0,
                    "message": "集合19当日无快照，请先采集"}

        draw_rec = db.execute(
            "SELECT draw_number FROM daily_snapshots WHERE date=? AND collection_id=19 LIMIT 1",
            (use_date,)
        ).fetchone()
        dn = draw_rec["draw_number"] if draw_rec else None

        # ── 存汇总（排位独立计算：聚合19的前max_n个汇总的sim_results → 算1-49排位）──
        saved = 0
        # daily_amount：直接从集合19的前max_n个汇总累加
        daily_amount = sum((r["total_value"] or 0) for i, r in enumerate(src_rows) if i < max_n)

        # 从集合19的前max_n个汇总的项目中拉sim_results，独立算排位
        src_names = [r["summary_name"] for i, r in enumerate(src_rows) if i < max_n]
        rank_collection = None
        if dn and src_names:
            src_sids = [r["summary_id"] if "summary_id" in r.keys() else
                        db.execute("SELECT id FROM summaries WHERE name=? AND collection_id=19",
                                   (r["summary_name"],)).fetchone()
                        for r in src_rows[:max_n]]
            src_sids = [s[0] if s else None for s in src_sids]
            src_sids = [s for s in src_sids if s]

            if src_sids:
                # 获取这些汇总下的所有项目ID
                sids_str = ",".join("?" * len(src_sids))
                pids = [r[0] for r in db.execute(
                    f"SELECT DISTINCT rgi.project_id FROM run_group_items rgi "
                    f"JOIN run_groups rg ON rgi.run_group_id = rg.id "
                    f"WHERE rg.summary_id IN ({sids_str})", src_sids
                ).fetchall()]

                if pids:
                    pids_str = ",".join("?" * len(pids))
                    sr_rows = db.execute(
                        f"SELECT sr.count_n, sr.numbers_json "
                        f"FROM sim_results sr "
                        f"JOIN sim_runs srn ON sr.run_id = srn.id "
                        f"WHERE srn.project_id IN ({pids_str}) AND sr.date=? "
                        f"AND srn.id = (SELECT MAX(id) FROM sim_runs WHERE project_id = srn.project_id)",
                        pids + [use_date]
                    ).fetchall()

                    if sr_rows:
                        cv_map = {}
                        cv_rows = db.execute(
                            "SELECT count_n, value FROM count_value_map"
                        ).fetchall()
                        for cv in cv_rows:
                            cv_map[cv["count_n"]] = cv["value"]

                        pos_values = {n: 0 for n in range(1, 50)}
                        for sr in sr_rows:
                            nums = json.loads(sr["numbers_json"])
                            val = cv_map.get(sr["count_n"], 0)
                            for num in nums:
                                if 1 <= num <= 49:
                                    pos_values[num] += val

                        sorted_pos = sorted(pos_values.items(), key=lambda x: x[1], reverse=True)
                        for rk_pos, (num, _) in enumerate(sorted_pos, 1):
                            if num == dn:
                                rank_collection = rk_pos
                                break

        for i, r in enumerate(src_rows):
            if i >= max_n:
                break
            tgt_name = f"当日汇总{i+1}"
            sid = db.execute(
                "SELECT id FROM summaries WHERE name=? AND collection_id=?",
                (tgt_name, collection_id)
            ).fetchone()
            if not sid:
                continue
            val = r["total_value"]
            rk = rank_collection  # 集合级统一排位
            db.execute(
                "INSERT OR REPLACE INTO daily_snapshots (date, collection_id, draw_number, summary_id, summary_name, projects, hit_rate, total_value, draw_value_rank) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (use_date, collection_id, dn, sid[0], tgt_name, 0, 0, val, rk)
            )
            saved += 1

        db.commit()

        # ── 同步写入 collection_meta ──
        db.execute(
            "INSERT OR REPLACE INTO collection_meta (collection_id, date, draw_number, result, rank) "
            "VALUES (?, ?, ?, ?, ?)",
            (collection_id, use_date, dn, round(daily_amount, 2), rank_collection)
        )
        db.commit()

        db.close()
        return {"ok": True, "date": use_date, "draw_number": dn, "saved": saved,
                "daily_amount": round(daily_amount, 2),
                "message": f"从A级集合累计 {max_n} 个汇总，存入 collection_meta"}

    # ── 正常集合：从项目计算 ──
    summaries_data, daily_amount, draw_number, project_details, grid_details = _compute_snapshot(db, collection_id, use_date)

    # 先清除当日旧数据，防止重复采集累积
    db.execute("DELETE FROM daily_project_snapshots WHERE date=? AND collection_id=?", (use_date, collection_id))
    db.execute("DELETE FROM daily_grid_snapshots WHERE date=? AND collection_id=?", (use_date, collection_id))

    saved = 0
    for s in summaries_data:
        sid = db.execute("SELECT id FROM summaries WHERE name=? AND collection_id=?", (s["name"], collection_id)).fetchone()
        if not sid:
            continue
        db.execute(
            "INSERT OR REPLACE INTO daily_snapshots (date, collection_id, draw_number, summary_id, summary_name, projects, hit_rate, total_value, draw_value_rank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (use_date, collection_id, draw_number, sid[0], s["name"], s["projects"], s["hit_rate"], s["total_value"], s.get("draw_value_rank"))
        )
        saved += 1

    # 项目明细
    proj_saved = 0
    for pname, sid, pid, pname_full, val, grid_cnt in project_details:
        db.execute(
            "INSERT OR REPLACE INTO daily_project_snapshots (date, collection_id, summary_id, summary_name, project_id, project_name, value) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (use_date, collection_id, sid, pname, pid, pname_full, val)
        )
        proj_saved += 1

    # 排位明细
    grid_saved = 0
    for sn, pid, pname, cn, val, v47, cum in grid_details:
        db.execute(
            "INSERT INTO daily_grid_snapshots (date, collection_id, summary_name, project_id, project_name, count_n, value, value_x_47, cumulative_sum) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (use_date, collection_id, sn, pid, pname, cn, val, v47, cum)
        )
        grid_saved += 1

    db.commit()
    db.close()
    return {"ok": True, "date": use_date, "draw_number": draw_number, "saved": saved, "proj_saved": proj_saved, "grid_saved": grid_saved, "daily_amount": daily_amount}


@app.post("/api/export/collect-today")
def collect_today(date: str = None):
    """一键采集当日：集合19 → 集合14 → 集合16"""
    steps = [19, 14, 16]
    results = {}
    for cid in steps:
        try:
            r = save_daily_snapshot(cid, date)
            results[str(cid)] = r
        except Exception as e:
            results[str(cid)] = {"ok": False, "error": str(e)}
    return {"ok": True, "results": results}


@app.get("/api/export/daily-summary")
def export_daily_summary(collection_id: int, date: str = None):
    """读取 daily_snapshots 快照表（极快）。无快照时回退实时计算"""
    db = get_db()
    from datetime import date as dt

    if date:
        use_date = date
    else:
        rec = db.execute("SELECT MAX(date) as dt FROM records").fetchone()
        use_date = rec["dt"] or dt.today().isoformat()

    # 先查快照表
    rows = db.execute(
        "SELECT summary_name, projects, hit_rate, total_value, draw_number, draw_value_rank "
        "FROM daily_snapshots WHERE date=? AND collection_id=? ORDER BY summary_id",
        (use_date, collection_id)
    ).fetchall()

    if rows:
        daily_amount = sum(r["total_value"] for r in rows)
        draw_number = rows[0]["draw_number"] if rows else None
        day_rec = db.execute("SELECT day_seq FROM records WHERE date=?", (use_date,)).fetchone()
        day_seq = day_rec["day_seq"] if day_rec else None
        db.close()
        return {
            "date": use_date, "draw_number": draw_number, "day_seq": day_seq,
            "summaries": [{"name": r["summary_name"], "projects": r["projects"], "hit_rate": r["hit_rate"], "total_value": r["total_value"], "draw_value_rank": r["draw_value_rank"]} for r in rows],
            "daily_amount": daily_amount,
            "source": "snapshot",
        }

    # 无快照 → 实时计算
    summaries_data, daily_amount, draw_number, _, _ = _compute_snapshot(db, collection_id, use_date)
    day_rec = db.execute("SELECT day_seq FROM records WHERE date=?", (use_date,)).fetchone()
    day_seq = day_rec["day_seq"] if day_rec else None
    db.close()
    return {
        "date": use_date, "draw_number": draw_number, "day_seq": day_seq,
        "summaries": summaries_data, "daily_amount": daily_amount,
        "source": "realtime",
    }


@app.get("/api/export/daily-detail")
def export_daily_detail(collection_id: int, date: str = None):
    """读取项目级快照：每个 summary 下的所有项目值"""
    db = get_db()
    from datetime import date as dt

    if date:
        use_date = date
    else:
        rec = db.execute("SELECT MAX(date) as dt FROM records").fetchone()
        use_date = rec["dt"] or dt.today().isoformat()

    # 先查快照表
    rows = db.execute(
        "SELECT summary_name, project_id, project_name, value "
        "FROM daily_project_snapshots WHERE date=? AND collection_id=? ORDER BY summary_id, project_id",
        (use_date, collection_id)
    ).fetchall()

    if rows:
        # 从排位快照表补充 grid_count
        grid_counts = {}
        grid_rows = db.execute(
            "SELECT summary_name, project_id, COUNT(*) as cnt "
            "FROM daily_grid_snapshots WHERE date=? AND collection_id=? "
            "GROUP BY summary_name, project_id",
            (use_date, collection_id)
        ).fetchall()
        for gr in grid_rows:
            grid_counts[(gr["summary_name"], gr["project_id"])] = gr["cnt"]
        db.close()
        from collections import defaultdict
        summaries = defaultdict(list)
        for r in rows:
            gc = grid_counts.get((r["summary_name"], r["project_id"]), 0)
            summaries[r["summary_name"]].append({
                "project_id": r["project_id"],
                "project_name": r["project_name"],
                "value": r["value"],
                "grid_count": gc
            })
        return {"date": use_date, "summaries": dict(summaries), "source": "snapshot"}

    # 无快照 → 实时计算
    _, _, _, project_details, grid_details = _compute_snapshot(db, collection_id, use_date)
    db.close()

    from collections import defaultdict
    summaries = defaultdict(list)
    for pname, sid, pid, pname_full, val, grid_cnt in project_details:
        summaries[pname].append({
            "project_id": pid,
            "project_name": pname_full,
            "value": val,
            "grid_count": grid_cnt
        })

    return {"date": use_date, "summaries": dict(summaries), "source": "computed"}


@app.get("/api/export/grid-detail")
def export_grid_detail(collection_id: int, date: str = None):
    """读取排位级快照：每个项目下的 count_n、value、value_x_47、cumulative_sum"""
    db = get_db()
    from datetime import date as dt

    if date:
        use_date = date
    else:
        rec = db.execute("SELECT MAX(date) as dt FROM records").fetchone()
        use_date = rec["dt"] or dt.today().isoformat()

    rows = db.execute(
        "SELECT summary_name, project_id, project_name, count_n, value, value_x_47, cumulative_sum "
        "FROM daily_grid_snapshots WHERE date=? AND collection_id=? ORDER BY summary_name, project_id, count_n",
        (use_date, collection_id)
    ).fetchall()

    if rows:
        db.close()
        from collections import defaultdict
        result = defaultdict(list)
        for r in rows:
            result[r["summary_name"]].append({
                "project_id": r["project_id"],
                "project_name": r["project_name"],
                "count_n": r["count_n"],
                "value": r["value"],
                "value_x_47": r["value_x_47"],
                "cumulative_sum": r["cumulative_sum"]
            })
        return {"date": use_date, "grids": dict(result), "source": "snapshot"}

    _, _, _, _, grid_details = _compute_snapshot(db, collection_id, use_date)
    db.close()

    from collections import defaultdict
    result = defaultdict(list)
    for sn, pid, pname, cn, val, v47, cum in grid_details:
        result[sn].append({
            "project_id": pid, "project_name": pname,
            "count_n": cn, "value": val, "value_x_47": v47, "cumulative_sum": cum
        })
    return {"date": use_date, "grids": dict(result), "source": "computed"}


@app.get("/api/export/collection-info")
def export_collection_info(collection_id: int):
    """返回集合信息和汇总列表"""
    db = get_db()
    
    # 集合14/16 是 A级集合(19) 的镜像
    if collection_id in (14, 16):
        coll = db.execute("SELECT id, name FROM collections WHERE id=19").fetchone()
        if not coll:
            db.close()
            raise HTTPException(status_code=404, detail="集合不存在")
        max_n = 4 if collection_id == 14 else 6
        # 用集合19的汇总，但只取前N个
        sums = db.execute(
            "SELECT id, name FROM summaries WHERE collection_id=19 ORDER BY id LIMIT ?",
            (max_n,)
        ).fetchall()
        db.close()
        return {
            "collection_id": collection_id,
            "collection_name": f"日汇总1-{max_n}" if collection_id == 16 else f"日汇总1-{max_n}",
            "summaries": [{"id": s["id"], "name": s["name"]} for s in sums]
        }
    
    coll = db.execute("SELECT id, name FROM collections WHERE id=?", (collection_id,)).fetchone()
    if not coll:
        db.close()
        raise HTTPException(status_code=404, detail="集合不存在")
    sums = db.execute(
        "SELECT id, name FROM summaries WHERE collection_id=? ORDER BY id",
        (collection_id,)
    ).fetchall()
    db.close()
    return {
        "collection_id": coll["id"],
        "collection_name": coll["name"],
        "summaries": [{"id": s["id"], "name": s["name"]} for s in sums]
    }


@app.get("/api/export/latest-snapshot-date")
def latest_snapshot_date(collection_id: int):
    """返回最新快照日期"""
    db = get_db()
    row = db.execute(
        "SELECT MAX(date) as dt FROM daily_snapshots WHERE collection_id=?",
        (collection_id,)
    ).fetchone()
    db.close()
    return {"date": row["dt"] if row and row["dt"] else None}


@app.get("/api/export/collection-meta")
def get_collection_meta(date: str):
    """读取集合14/16的collection_meta数据（纯读表，零计算）"""
    db = get_db()
    rows = db.execute(
        "SELECT collection_id, draw_number, result, rank FROM collection_meta WHERE date=? ORDER BY collection_id",
        (date,)
    ).fetchall()
    db.close()
    return {
        "date": date,
        "collections": [
            {"collection_id": r["collection_id"], "draw_number": r["draw_number"],
             "result": r["result"], "rank": r["rank"]}
            for r in rows
        ]
    }


# ── 门店同步 ──────────────────────────────────
STORE_SYNC_URL = "http://localhost:8009/api/external/push"
STORE_API_KEY = "funds-v2-ext-2026"
SYNC_CRON_FILE = os.path.join(os.path.dirname(__file__), "sync_cron.json")

def _load_sync_cron():
    if os.path.exists(SYNC_CRON_FILE):
        with open(SYNC_CRON_FILE) as f:
            return json.load(f)
    return {"hour": 2, "minute": 0}

def _save_sync_cron(cfg):
    with open(SYNC_CRON_FILE, "w") as f:
        json.dump(cfg, f)

@app.get("/api/export/sync-cron")
def get_sync_cron():
    return _load_sync_cron()

@app.put("/api/export/sync-cron")
async def update_sync_cron(request: Request):
    body = await request.json()
    hour = max(0, min(23, int(body.get("hour", 2))))
    minute = max(0, min(59, int(body.get("minute", 0))))
    cfg = {"hour": hour, "minute": minute}
    _save_sync_cron(cfg)
    # 同步更新 cron 调度
    import subprocess
    subprocess.run(
        ["/home/xiaolin/.local/bin/hermes", "cron", "edit", "e6796639506f",
         "--schedule", f"{minute} {hour} * * *"],
        capture_output=True, timeout=10
    )
    return {"ok": True, **cfg}

@app.post("/api/export/sync-store")
def sync_to_store(collection_id: int, date: str = None):
    """同步当日数据到门店。采集汇总 → 推送到 funds-v2"""
    import httpx
    from datetime import date as dt

    if date:
        use_date = date
    else:
        db_tmp = get_db()
        rec = db_tmp.execute("SELECT MAX(date) as dt FROM records").fetchone()
        use_date = rec["dt"] or dt.today().isoformat()
        db_tmp.close()

    # ── 抽签号校验：当日抽签数未出则不允许同步 ──
    db_chk = get_db()
    draw_chk = db_chk.execute("SELECT draw_number FROM records WHERE date=?", (use_date,)).fetchone()
    db_chk.close()
    if not draw_chk or draw_chk["draw_number"] is None:
        return {"ok": False, "error": f"{use_date} 抽签号尚未公布，禁止同步空数据"}

    # ── 集合14/16：从 collection_meta 表读取 ──
    if collection_id in (14, 16):
        db = get_db()
        meta = db.execute(
            "SELECT draw_number, result, rank FROM collection_meta WHERE collection_id=? AND date=?",
            (collection_id, use_date)
        ).fetchone()
        db.close()

        if not meta:
            return {"ok": True, "records": 0, "message": "该集合当日无数据，请先采集"}
    else:
        # 正常集合：从项目计算
        db = get_db()
        summaries_data, _, draw_number, _, _ = _compute_snapshot(db, collection_id, use_date)
        db.close()

    # 汇总名 → 门店
    STORE_MAP = {
        "B级汇总1": "一店", "B级汇总2": "二店", "B级汇总3": "三店",
        "B级汇总4": "四店", "B级汇总5": "五店", "B级汇总6": "六店",
        "当日汇总1": "一店", "当日汇总2": "二店", "当日汇总3": "三店",
        "当日汇总4": "四店", "当日汇总5": "五店", "当日汇总6": "六店",
    }

    # 集合14/16 → 各自独立门店
    DIR_STORE = {14: "集合14", 16: "集合16"}

    records = []
    if collection_id in DIR_STORE:
        # ── 集合级总计 → 独立门店，从 collection_meta 读 ──
        store = DIR_STORE[collection_id]
        total = meta["result"]
        rank = meta["rank"]
        records.append({
            "id": f"{use_date}-col{collection_id}-income",
            "store": store,
            "date": use_date,
            "category": "income",
            "amount": total,
            "note": f"集合{collection_id} 排位{rank}"
        })
        records.append({
            "id": f"{use_date}-col{collection_id}-cat",
            "store": store,
            "date": use_date,
            "category": "cat_1783487972049",
            "amount": rank or 0,
            "note": f"集合{collection_id} 排位{rank} ¥{total:,.0f}"
        })
    else:
        for s in (summaries_data or []):
            store = STORE_MAP.get(s.get("name", ""))
            if not store:
                continue
            amount = s.get("total_value") or 0
            rank = s.get("draw_value_rank") or 0
            records.append({
                "id": f"{use_date}-{s['name']}-income",
                "store": store,
                "date": use_date,
                "category": "income",
                "amount": amount,
                "note": f"排位 {rank}"
            })
            records.append({
                "id": f"{use_date}-{s['name']}-cat",
                "store": store,
                "date": use_date,
                "category": "cat_1783487972049",
                "amount": rank,
                "note": f"排位 {rank}  ·  ¥{amount:,.0f}"
            })

    if not records:
        return {"ok": True, "records": 0, "message": "无数据可推"}

    # 推送
    try:
        resp = httpx.post(
            STORE_SYNC_URL,
            json={"records": records},
            headers={"X-API-Key": STORE_API_KEY, "Content-Type": "application/json"},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            return {"ok": True, "records": data.get("records", len(records)), "date": use_date, "details": records}
        return {"ok": False, "error": f"推送失败 HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 归位：1-49 → A-L 组映射 ──────────────────
@app.get("/api/direct-mapping")
def get_direct_mapping():
    """返回 1-49 → 组(A-L) 映射，优先读 direct_mapping 表，否则用 BASE_GROUPS"""
    db = get_db()
    rows = db.execute("SELECT num, group_name FROM direct_mapping ORDER BY num").fetchall()
    db.close()
    if rows:
        return {"mapping": [{"num": r["num"], "group": r["group_name"]} for r in rows],
                "source": "direct"}
    # fallback to BASE_GROUPS
    result = []
    for g, nums in BASE_GROUPS.items():
        for n in nums:
            result.append({"num": n, "group": g})
    result.sort(key=lambda x: x["num"])
    return {"mapping": result, "source": "base"}


@app.put("/api/direct-mapping/{num}")
def update_direct_mapping(num: int, group_name: str = Query(...)):
    """更新某数字的归属组。同时重置该数字为默认值用 DELETE"""
    if num < 1 or num > 49:
        raise HTTPException(400, "num 需在 1-49 之间")
    if group_name not in GROUPS:
        raise HTTPException(400, f"组名需为 {'/'.join(GROUPS)} 之一")
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO direct_mapping (num, group_name, updated_at) VALUES (?,?,datetime('now','localtime'))",
        (num, group_name)
    )
    db.commit()
    db.close()
    return {"ok": True, "num": num, "group": group_name}


@app.delete("/api/direct-mapping/{num}")
def reset_direct_mapping(num: int):
    """重置某数字到默认底板归属"""
    db = get_db()
    db.execute("DELETE FROM direct_mapping WHERE num=?", (num,))
    db.commit()
    db.close()
    return {"ok": True, "num": num, "reset": True}


# ==================== 启动 ====================
init_db()
init_auth_db()

# 静态文件
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

# 认证中间件（在 no-cache 之后添加，会包裹它）
app.include_router(auth_router)
app.add_middleware(AuthMiddleware)

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    # HTML 响应强制不缓存
    ct = response.headers.get("content-type", "")
    if "text/html" in ct:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8016)
