"""
次数映射与数字仓库轮换系统 — FastAPI 后端
"""
import os, json, copy
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3

app = FastAPI(title="数字仓库轮换系统")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "warehouse.db")

BASE_DATE = date(2026, 1, 1)  # 基准日
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
    db = sqlite3.connect(DB_PATH)
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

def days_since_base(target_date: date) -> int:
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


def get_groups_for_date(target_date: date, db) -> dict:
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


def compute_snapshot(target_date: date, draw_number: int, db) -> dict:
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
    target = date.fromisoformat(req.date)
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
    today_str = date.today().isoformat()
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


def calc_day_seq(d: date) -> int:
    """计算日期序号：每年1月1日=1，逐日+1"""
    year_start = date(d.year, 1, 1)
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
    target = date.fromisoformat(r.date)
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
    day_seq = calc_day_seq(date.fromisoformat(new_date))
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


class ProjectUpdate(BaseModel):
    name: Optional[str] = None


class GroupIn(BaseModel):
    project_id: int
    group_name: str
    numbers: list


class GroupUpdate(BaseModel):
    group_name: Optional[str] = None
    numbers: Optional[list] = None


@app.get("/api/projects")
def list_projects():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY id"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/api/projects")
def create_project(p: ProjectIn):
    db = get_db()
    db.execute("INSERT INTO projects (name) VALUES (?)", (p.name,))
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
        "SELECT * FROM sim_runs WHERE rule_id=? AND project_id=? ORDER BY end_date DESC LIMIT 1",
        (rule_id, pid)
    ).fetchone()

    groups = {g: list(base[g]) for g in GROUPS}
    counts = {g: 1 for g in GROUPS}
    day_offset = 0  # 已运行天数

    if existing:
        existing_end = existing["end_date"]
        if end_date <= existing_end:
            return {
                "ok": True, "run_id": existing["id"], "skipped": True,
                "total_days": existing["total_days"], "hit_count": existing["hit_count"],
                "start_date": existing["start_date"], "end_date": existing_end,
                "project_id": pid, "project_name": proj_name,
                "message": f"已有 {existing_end} 前数据，跳过"
            }
        # 从已有最后一天接续
        real_start = (date.fromisoformat(existing_end) + timedelta(days=1)).isoformat()
        # 加载最后一天的状态
        last_results = db.execute(
            "SELECT group_name, numbers_json, count_n FROM sim_results "
            "WHERE run_id=? AND date=? ORDER BY group_name",
            (existing["id"], existing_end)
        ).fetchall()
        if last_results:
            for r in last_results:
                groups[r["group_name"]] = json.loads(r["numbers_json"])
                counts[r["group_name"]] = r["count_n"]
        day_offset = existing["total_days"]
        run_id = existing["id"]
        is_new_run = False
    else:
        real_start = start_date
        is_new_run = True

    # 加载实际日期范围的抽签记录
    records = db.execute(
        "SELECT date, draw_number FROM records WHERE date BETWEEN ? AND ? ORDER BY date",
        (real_start, end_date)
    ).fetchall()
    if not records:
        if existing:
            return {
                "ok": True, "run_id": run_id, "skipped": True,
                "total_days": existing["total_days"], "hit_count": existing["hit_count"],
                "project_id": pid, "project_name": proj_name,
                "message": f"已有 {existing['end_date']} 前数据，新范围内无抽签数据"
            }
        raise HTTPException(400, f"{real_start}~{end_date} 无抽签数据")

    # 检查空抽签
    valid = []
    for rec in records:
        if rec["draw_number"] is None or rec["draw_number"] == 0:
            break
        valid.append(rec)
    if not valid:
        raise HTTPException(400, "无有效抽签数据")

    # 创建/获取运行记录
    if is_new_run:
        db.execute(
            "INSERT INTO sim_runs (rule_id, start_date, end_date, total_days, project_id, project_name) VALUES (?,?,?,?,?,?)",
            (rule_id, valid[0]["date"], valid[-1]["date"], 0, pid, proj_name)
        )
        run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    hit_count = 0

    for day_idx, rec in enumerate(valid):
        dt, draw = rec["date"], rec["draw_number"]

        # 左移：day_offset=0 (首日)不移动，之后每次移动
        if day_offset + day_idx >= 1:
            groups = rotate_left_n(groups, shift)

        hit_group = None
        for g in GROUPS:
            if draw in groups[g]:
                hit_group = g
                hit_count += 1
                break

        # 首日初始化次数
        if day_offset + day_idx == 0:
            counts = {g: 1 for g in GROUPS}

        # === 写入 sim_results：用当天起始的 counts（命中组显示累积次数，次日才重置） ===
        pre_hit = counts.get(hit_group) if hit_group else None
        for g in GROUPS:
            db.execute(
                "INSERT OR REPLACE INTO sim_results (run_id, date, draw_number, hit_group, group_name, numbers_json, count_n, pre_hit_count_n) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (run_id, dt, draw, hit_group, g,
                 json.dumps(groups[g]), counts[g],
                 pre_hit if g == hit_group else None)
            )

        # === 更新次数供次日使用：命中组重置为1，其余+1 ===
        new_counts = {}
        for g in GROUPS:
            if g == hit_group:
                new_counts[g] = 1
            else:
                new_counts[g] = counts.get(g, 1) + 1
        counts = new_counts

    total_days = day_offset + len(valid)
    # 更新运行记录
    db.execute(
        "UPDATE sim_runs SET end_date=?, total_days=?, hit_count=hit_count+? WHERE id=?",
        (valid[-1]["date"], total_days, hit_count, run_id)
    )
    db.commit()

    return {
        "ok": True, "run_id": run_id, "skipped": False,
        "total_days": total_days, "hit_count": db.execute(
            "SELECT hit_count FROM sim_runs WHERE id=?", (run_id,)).fetchone()["hit_count"],
        "start_date": db.execute("SELECT start_date FROM sim_runs WHERE id=?", (run_id,)).fetchone()["start_date"],
        "end_date": valid[-1]["date"],
        "new_days": len(valid),
        "project_id": pid, "project_name": proj_name,
        "continued": not is_new_run
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
def get_sim_run(run_id: int):
    db = get_db()
    run = db.execute(
        "SELECT r.*, s.name as rule_name, s.shift_amount FROM sim_runs r "
        "JOIN sim_rules s ON r.rule_id=s.id WHERE r.id=?",
        (run_id,)
    ).fetchone()
    if not run:
        db.close()
        raise HTTPException(404, "运行不存在")

    # 按日期分组结果
    results = db.execute(
        "SELECT * FROM sim_results WHERE run_id=? ORDER BY date, group_name",
        (run_id,)
    ).fetchall()

    # 按天组织
    daily = {}
    for r in results:
        dt = r["date"]
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
            "value": get_count_value(r["count_n"], db)
        }

    db.close()
    return {
        "run": dict(run),
        "daily": [daily[k] for k in sorted(daily.keys(), reverse=True)]
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
    try:
        for i, pid in enumerate(body.project_ids):
            rid = body.rule_ids[min(i, len(body.rule_ids) - 1)]
            r = run_simulation(db, rid, body.start_date, body.end_date, pid)
            results.append(r)
        # 模拟完成后刷新分析数据
        refresh_analysis(db)
        # 返回最后一条的run_id给前端默认展示
        last = results[-1] if results else None
        return {"ok": True, "runs": results, "last_run_id": last["run_id"] if last else None}
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 模拟结果查询 ====================

@app.get("/api/sim/results/query")
def query_sim_results(
    project_id: Optional[int] = None,
    rule_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 30
):
    """查询模拟运行记录（支持多条件筛选）"""
    db = get_db()
    wheres = ["1=1"]
    params = []

    if project_id:
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
                 page: int = 1, page_size: int = 50, project_id: int = None):
    """数据分析：从 analysis_daily 读，支持按项目筛选"""
    db = get_db()

    cnt = db.execute("SELECT COUNT(*) FROM analysis_daily").fetchone()[0]
    if cnt == 0:
        return {"items": [], "total": 0, "page": 1, "page_size": page_size,
                "total_pages": 0, "cumulative_sum": 0, "message": "请先运行规则模拟生成数据"}

    where = "WHERE date BETWEEN ? AND ?"
    params = [start_date, end_date]
    if project_id:
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


# ==================== 启动 ====================
init_db()

# 静态文件
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)
