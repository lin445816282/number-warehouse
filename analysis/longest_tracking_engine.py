#!/usr/bin/env python3
"""
「最长跟踪」演算引擎 — 冷号回补策略回测
从最长未出号码(冷号)中按不同算法拆分 3~25 个号，回测历史，找出盈利方案。

核心逻辑（walk-forward 无未来函数）：
  - 预测第 t 期：只用第 1..t-1 期的数据计算各号码遗漏期数
  - 按算法从 49 个号里选 N 个（3~25）
  - 判断第 t 期开奖号是否命中 → 累计盈亏

盈利口径（双口径都算）：
  1. 等额：每号 1 元，命中赔 47 倍。命中 +47-N，未命中 -N
  2. 倍投：按 count_value_map（遗漏越久 value 越大），命中 value×47-总成本，未命中 -总成本

用法：python3 longest_tracking_engine.py [--min-n 3] [--max-n 25] [--warmup 100]
输出：analysis/longest_tracking_result.json + 控制台盈利排名
"""
import json
import sqlite3
import os
import sys
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "backend", "data", "warehouse.db")

# ── 号码分类（静态，来自 numtool_classes）──
ZODIAC = {1:"马",2:"蛇",3:"龙",4:"兔",5:"虎",6:"牛",7:"鼠",8:"猪",9:"狗",10:"鸡",11:"猴",12:"羊",
          13:"马",14:"蛇",15:"龙",16:"兔",17:"虎",18:"牛",19:"鼠",20:"猪",21:"狗",22:"鸡",23:"猴",24:"羊",
          25:"马",26:"蛇",27:"龙",28:"兔",29:"虎",30:"牛",31:"鼠",32:"猪",33:"狗",34:"鸡",35:"猴",36:"羊",
          37:"马",38:"蛇",39:"龙",40:"兔",41:"虎",42:"牛",43:"鼠",44:"猪",45:"狗",46:"鸡",47:"猴",48:"羊",49:"马"}
ELEMENT = {1:"水",2:"火",3:"火",4:"金",5:"金",6:"土",7:"土",8:"木",9:"木",10:"火",11:"火",12:"金",13:"金",14:"水",15:"水",
           16:"木",17:"木",18:"火",19:"火",20:"土",21:"土",22:"水",23:"水",24:"木",25:"木",26:"金",27:"金",28:"土",29:"土",30:"水",
           31:"水",32:"火",33:"火",34:"金",35:"金",36:"土",37:"土",38:"木",39:"木",40:"火",41:"火",42:"金",43:"金",44:"水",45:"水",
           46:"木",47:"木",48:"火",49:"火"}
COLOR = {1:"红波",2:"红波",3:"蓝波",4:"蓝波",5:"绿波",6:"绿波",7:"红波",8:"红波",9:"蓝波",10:"蓝波",11:"绿波",12:"红波",
         13:"红波",14:"蓝波",15:"蓝波",16:"绿波",17:"绿波",18:"红波",19:"红波",20:"蓝波",21:"绿波",22:"绿波",23:"红波",24:"红波",
         25:"蓝波",26:"蓝波",27:"绿波",28:"绿波",29:"红波",30:"红波",31:"蓝波",32:"绿波",33:"绿波",34:"红波",35:"红波",36:"蓝波",
         37:"蓝波",38:"绿波",39:"绿波",40:"红波",41:"蓝波",42:"蓝波",43:"绿波",44:"绿波",45:"红波",46:"红波",47:"蓝波",48:"蓝波",49:"绿波"}
ODD_EVEN = {n: ("单" if n % 2 == 1 else "双") for n in range(1, 50)}
BIG_SMALL = {n: ("大" if n >= 25 else "小") for n in range(1, 50)}
TAIL = {n: n % 10 for n in range(1, 50)}
SUM_PARITY = {n: ("合单" if (n // 10 + n % 10) % 2 == 1 else "合双") for n in range(1, 50)}

JIAQIN = {"牛","马","羊","鸡","狗","猪"}   # 家禽
YESHOU = {"鼠","虎","兔","龙","蛇","猴"}   # 野兽


def load_records():
    """读全部开奖记录，按日期升序返回 draw 序列 + 日期序列"""
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT date, draw_number FROM records ORDER BY date").fetchall()
    db.close()
    dates = [r["date"] for r in rows]
    draws = [r["draw_number"] for r in rows]
    return dates, draws


def load_count_value_map():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT count_n, value FROM count_value_map ORDER BY count_n").fetchall()
    db.close()
    return {r["count_n"]: r["value"] for r in rows}


# ══════════════════════════════════════════════════════════
# 50 种算法定义：每个算法 = (id, 名称, 描述, 排序键, 过滤器列表)
# 排序键决定候选号码的优先级，过滤器限制候选池
# ══════════════════════════════════════════════════════════

# 排序键函数：输入 (num, ctx) -> 排序值（越大越优先）
def sort_gap_desc(num, ctx):      return ctx["gap"][num]                      # 遗漏期数降序
def sort_ratio_desc(num, ctx):    return ctx["gap"][num] / max(ctx["maxgap"][num], 1)  # 遗漏/历史最长
def sort_freq_asc(num, ctx):      return -ctx["freq"][num]                    # 出现次数升序(冷号)
def sort_maxgap_desc(num, ctx):   return ctx["maxgap"][num]                   # 历史最大遗漏降序
def sort_last_asc(num, ctx):      return -ctx["last_seen_idx"][num]           # 最近出现距今最久
def sort_gap_tail(num, ctx):      return ctx["gap"][num] + ctx["tail_gap"][TAIL[num]] * 3
def sort_gap_zodiac(num, ctx):    return ctx["gap"][num] + ctx["zodiac_gap"][ZODIAC[num]] * 3
def sort_gap_element(num, ctx):   return ctx["gap"][num] + ctx["element_gap"][ELEMENT[num]] * 3
def sort_gap_color(num, ctx):     return ctx["gap"][num] + ctx["color_gap"][COLOR[num]] * 3
def sort_gap_freq(num, ctx):      return ctx["gap"][num] * 2 - ctx["freq"][num]          # 遗漏×2 - 频率
def sort_random(num, ctx):        return ctx["_rand"][num]                    # 随机对照

# 过滤器函数：输入 num -> True/False
def f_none(num): return True
def f_tail_0_4(num): return TAIL[num] <= 4
def f_tail_5_9(num): return TAIL[num] >= 5
def f_odd(num): return ODD_EVEN[num] == "单"
def f_even(num): return ODD_EVEN[num] == "双"
def f_big(num): return BIG_SMALL[num] == "大"
def f_small(num): return BIG_SMALL[num] == "小"
def f_sum_odd(num): return SUM_PARITY[num] == "合单"
def f_sum_even(num): return SUM_PARITY[num] == "合双"
def f_jiaqin(num): return ZODIAC[num] in JIAQIN
def f_yeshou(num): return ZODIAC[num] in YESHOU
def f_el_jin(num): return ELEMENT[num] == "金"
def f_el_mu(num): return ELEMENT[num] == "木"
def f_el_shui(num): return ELEMENT[num] == "水"
def f_el_huo(num): return ELEMENT[num] == "火"
def f_el_tu(num): return ELEMENT[num] == "土"
def f_color_hong(num): return COLOR[num] == "红波"
def f_color_lan(num): return COLOR[num] == "蓝波"
def f_color_lv(num): return COLOR[num] == "绿波"
def f_tail_single(num): return TAIL[num] % 2 == 1
def f_tail_double(num): return TAIL[num] % 2 == 0


# 需要动态上下文（上期生肖/尾数）的过滤器，用特殊标记
DYNAMIC_FILTERS = {"zodiac_prev", "zodiac_not_prev", "tail_prev", "tail_not_prev"}

def make_dynamic_filter(name, prev_draw):
    def f(num):
        if name == "zodiac_prev": return ZODIAC[num] == ZODIAC.get(prev_draw, "")
        if name == "zodiac_not_prev": return ZODIAC[num] != ZODIAC.get(prev_draw, "")
        if name == "tail_prev": return TAIL[num] == TAIL.get(prev_draw, -1)
        if name == "tail_not_prev": return TAIL[num] != TAIL.get(prev_draw, -1)
        return True
    return f


# 50 种算法：id, 名称, 描述, 排序键, 过滤器(静态名)
ALGORITHMS = [
    (1,  "遗漏降序",           "当前遗漏期数最长的号",               sort_gap_desc,   "none"),
    (2,  "遗漏·尾0-4",         "遗漏降序 ∩ 尾数0-4",                sort_gap_desc,   "tail_0_4"),
    (3,  "遗漏·尾5-9",         "遗漏降序 ∩ 尾数5-9",                sort_gap_desc,   "tail_5_9"),
    (4,  "遗漏·单号",          "遗漏降序 ∩ 单号",                   sort_gap_desc,   "odd"),
    (5,  "遗漏·双号",          "遗漏降序 ∩ 双号",                   sort_gap_desc,   "even"),
    (6,  "遗漏·大号",          "遗漏降序 ∩ 大号(25-49)",            sort_gap_desc,   "big"),
    (7,  "遗漏·小号",          "遗漏降序 ∩ 小号(1-24)",             sort_gap_desc,   "small"),
    (8,  "遗漏·合单",          "遗漏降序 ∩ 合单",                   sort_gap_desc,   "sum_odd"),
    (9,  "遗漏·合双",          "遗漏降序 ∩ 合双",                   sort_gap_desc,   "sum_even"),
    (10, "遗漏·家禽",          "遗漏降序 ∩ 家禽(牛马羊鸡狗猪)",     sort_gap_desc,   "jiaqin"),
    (11, "遗漏·野兽",          "遗漏降序 ∩ 野兽(鼠虎兔龙蛇猴)",     sort_gap_desc,   "yeshou"),
    (12, "遗漏·上期生肖",      "遗漏降序 ∩ 上期生肖",               sort_gap_desc,   "zodiac_prev"),
    (13, "遗漏·避开上期生肖",  "遗漏降序 ∩ 避开上期生肖",           sort_gap_desc,   "zodiac_not_prev"),
    (14, "遗漏·五行金",        "遗漏降序 ∩ 五行金",                 sort_gap_desc,   "el_jin"),
    (15, "遗漏·五行木",        "遗漏降序 ∩ 五行木",                 sort_gap_desc,   "el_mu"),
    (16, "遗漏·五行水",        "遗漏降序 ∩ 五行水",                 sort_gap_desc,   "el_shui"),
    (17, "遗漏·五行火",        "遗漏降序 ∩ 五行火",                 sort_gap_desc,   "el_huo"),
    (18, "遗漏·五行土",        "遗漏降序 ∩ 五行土",                 sort_gap_desc,   "el_tu"),
    (19, "遗漏·红波",          "遗漏降序 ∩ 红波",                   sort_gap_desc,   "color_hong"),
    (20, "遗漏·蓝波",          "遗漏降序 ∩ 蓝波",                   sort_gap_desc,   "color_lan"),
    (21, "遗漏·绿波",          "遗漏降序 ∩ 绿波",                   sort_gap_desc,   "color_lv"),
    (22, "遗漏比·全号",        "遗漏/历史最长 比例降序",            sort_ratio_desc, "none"),
    (23, "遗漏比·单号",        "遗漏/历史最长 比例降序 ∩ 单号",     sort_ratio_desc, "odd"),
    (24, "遗漏比·双号",        "遗漏/历史最长 比例降序 ∩ 双号",     sort_ratio_desc, "even"),
    (25, "遗漏比·大号",        "遗漏/历史最长 比例降序 ∩ 大号",     sort_ratio_desc, "big"),
    (26, "遗漏比·小号",        "遗漏/历史最长 比例降序 ∩ 小号",     sort_ratio_desc, "small"),
    (27, "频率冷号",           "历史出现次数最少的号",               sort_freq_asc,   "none"),
    (28, "频率冷·单号",        "历史出现次数最少 ∩ 单号",           sort_freq_asc,   "odd"),
    (29, "频率冷·大号",        "历史出现次数最少 ∩ 大号",           sort_freq_asc,   "big"),
    (30, "历史最长遗漏",       "历史最大遗漏期数最长的号",           sort_maxgap_desc,"none"),
    (31, "历史最长·单号",      "历史最大遗漏 ∩ 单号",               sort_maxgap_desc,"odd"),
    (32, "最久未出现",         "距上次出现最久的号(同遗漏降序)",     sort_last_asc,   "none"),
    (33, "遗漏·上期尾数",      "遗漏降序 ∩ 上期尾数",               sort_gap_desc,   "tail_prev"),
    (34, "遗漏·避开上期尾数",  "遗漏降序 ∩ 避开上期尾数",           sort_gap_desc,   "tail_not_prev"),
    (35, "遗漏·尾单",          "遗漏降序 ∩ 尾数单(1,3,5,7,9)",     sort_gap_desc,   "tail_single"),
    (36, "遗漏·尾双",          "遗漏降序 ∩ 尾数双(0,2,4,6,8)",     sort_gap_desc,   "tail_double"),
    (37, "遗漏·尾0/5",         "遗漏降序 ∩ 尾数0或5",               sort_gap_desc,   None),
    (38, "遗漏·尾1/6",         "遗漏降序 ∩ 尾数1或6",               sort_gap_desc,   None),
    (39, "遗漏·尾2/7",         "遗漏降序 ∩ 尾数2或7",               sort_gap_desc,   None),
    (40, "遗漏·尾3/8",         "遗漏降序 ∩ 尾数3或8",               sort_gap_desc,   None),
    (41, "遗漏·尾4/9",         "遗漏降序 ∩ 尾数4或9",               sort_gap_desc,   None),
    (42, "遗漏×尾数加权",      "遗漏 + 尾数遗漏×3 加权",            sort_gap_tail,   "none"),
    (43, "遗漏×生肖加权",      "遗漏 + 生肖遗漏×3 加权",            sort_gap_zodiac, "none"),
    (44, "遗漏×五行加权",      "遗漏 + 五行遗漏×3 加权",            sort_gap_element,"none"),
    (45, "遗漏×波色加权",      "遗漏 + 波色遗漏×3 加权",            sort_gap_color,  "none"),
    (46, "遗漏×频率综合",      "遗漏×2 - 频率 综合评分",            sort_gap_freq,   "none"),
    (47, "全维度冷号投票",     "遗漏+尾数+生肖+五行 多维冷号",       None,            None),
    (48, "遗漏·去极值",        "遗漏降序 但跳过最冷1个",            sort_gap_desc,   "skip_coldest_1"),
    (49, "遗漏·去极值3",       "遗漏降序 但跳过最冷3个",            sort_gap_desc,   "skip_coldest_3"),
    (50, "随机对照",           "从49号随机选(基线对照)",            sort_random,     "none"),
]

# 尾数组合过滤（37-41 用自定义尾数集合）
TAIL_SETS = {37: {0,5}, 38: {1,6}, 39: {2,7}, 40: {3,8}, 41: {4,9}}


def compute_context(draws, t, freq, maxgap, last_seen_idx, tail_gap, zodiac_gap, element_gap, color_gap):
    """构建第 t 期预测用的上下文（用 0..t-1 的数据）"""
    gap = {}
    for n in range(1, 50):
        ls = last_seen_idx[n]
        gap[n] = (t - ls) if ls >= 0 else t  # 从未出现则遗漏=t期
    return {
        "gap": gap, "maxgap": maxgap, "freq": freq,
        "last_seen_idx": last_seen_idx,
        "tail_gap": tail_gap, "zodiac_gap": zodiac_gap,
        "element_gap": element_gap, "color_gap": color_gap,
        "_rand": None,  # 随机对照时填充
    }


def select_numbers(algo_id, algo_sort, algo_filter, ctx, n, prev_draw, rand_map):
    """按算法选 n 个号，返回列表"""
    nums = list(range(1, 50))

    # 特殊算法：多维冷号投票
    if algo_id == 47:
        # 每个号算多维冷度分：遗漏 + 尾数遗漏 + 生肖遗漏 + 五行遗漏
        scores = []
        for num in nums:
            s = ctx["gap"][num] + ctx["tail_gap"][TAIL[num]] + ctx["zodiac_gap"][ZODIAC[num]] + ctx["element_gap"][ELEMENT[num]]
            scores.append((s, num))
        scores.sort(key=lambda x: -x[0])
        return [x[1] for x in scores[:n]]

    # 随机对照
    if algo_id == 50:
        ctx["_rand"] = rand_map
        order = sorted(nums, key=lambda x: -ctx["_rand"][x])
        return order[:n]

    # 过滤
    if algo_filter is not None:
        if algo_filter in DYNAMIC_FILTERS:
            f = make_dynamic_filter(algo_filter, prev_draw)
            nums = [x for x in nums if f(x)]
        elif algo_filter in ("skip_coldest_1", "skip_coldest_3"):
            pass  # 特殊处理：排序后跳过
        elif algo_filter is None:
            pass
        else:
            f = FILTER_FUNCS[algo_filter]
            nums = [x for x in nums if f(x)]
    elif algo_id in TAIL_SETS:
        ts = TAIL_SETS[algo_id]
        nums = [x for x in nums if TAIL[x] in ts]

    # 排序
    ctx["_rand"] = rand_map
    order = sorted(nums, key=lambda x: -algo_sort(x, ctx))

    # 去极值
    if algo_filter == "skip_coldest_1":
        order = order[1:]
    elif algo_filter == "skip_coldest_3":
        order = order[3:]

    return order[:n]


FILTER_FUNCS = {
    "none": f_none, "tail_0_4": f_tail_0_4, "tail_5_9": f_tail_5_9,
    "odd": f_odd, "even": f_even, "big": f_big, "small": f_small,
    "sum_odd": f_sum_odd, "sum_even": f_sum_even,
    "jiaqin": f_jiaqin, "yeshou": f_yeshou,
    "el_jin": f_el_jin, "el_mu": f_el_mu, "el_shui": f_el_shui,
    "el_huo": f_el_huo, "el_tu": f_el_tu,
    "color_hong": f_color_hong, "color_lan": f_color_lan, "color_lv": f_color_lv,
    "tail_single": f_tail_single, "tail_double": f_tail_double,
}


def run_backtest(draws, dates, count_map, min_n=3, max_n=25, warmup=100):
    """跑全部 50 算法 × (min_n..max_n) 的回测，返回结果列表"""
    M = len(draws)
    import random as _random
    _random.seed(42)

    # 预生成每期的随机映射（用于随机对照算法，保证可复现）
    rand_maps = []
    for _ in range(M):
        m = {n: _random.random() for n in range(1, 50)}
        rand_maps.append(m)

    # 增量维护的统计量
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen_idx = {n: -1 for n in range(1, 50)}
    # 分类的最近出现期（用于 tail_gap/zodiac_gap 等）
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(ZODIAC.values())}
    element_last = {e: -1 for e in set(ELEMENT.values())}
    color_last = {c: -1 for c in set(COLOR.values())}

    # 结果：{algo_id: {n: 累计数据}}
    results = {}

    # 遍历每一期 t（从 warmup 开始，保证有足够历史）
    for t in range(warmup, M):
        prev_draw = draws[t - 1]

        # 计算分类遗漏（距最近出现期数）
        tail_gap = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
        zodiac_gap = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
        element_gap = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
        color_gap = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}

        ctx = compute_context(draws, t, freq, maxgap, last_seen_idx,
                              tail_gap, zodiac_gap, element_gap, color_gap)

        actual = draws[t]  # 第 t 期实际开奖号

        for (aid, name, desc, sort_fn, flt) in ALGORITHMS:
            if aid not in results:
                results[aid] = {}
            for n in range(min_n, max_n + 1):
                picks = select_numbers(aid, sort_fn, flt, ctx, n, prev_draw, rand_maps[t])
                hit = actual in picks
                # 等额口径
                eq_pnl = (47 - n) if hit else (-n)
                # 倍投口径
                bt_cost = 0
                bt_pnl = 0
                for p in picks:
                    g = ctx["gap"][p]
                    v = count_map.get(g, 0)
                    bt_cost += v
                if hit:
                    hg = ctx["gap"][actual]
                    hv = count_map.get(hg, 0)
                    bt_pnl = hv * 47 - bt_cost
                else:
                    bt_pnl = -bt_cost

                r = results[aid].setdefault(n, {
                    "hits": 0, "total": 0, "eq_pnl": 0, "bt_pnl": 0,
                    "eq_days_pos": 0, "max_drawdown": 0, "cur_drawdown": 0,
                })
                r["hits"] += 1 if hit else 0
                r["total"] += 1
                r["eq_pnl"] += eq_pnl
                r["bt_pnl"] += bt_pnl
                if eq_pnl > 0:
                    r["eq_days_pos"] += 1
                # 回撤（等额口径）
                if eq_pnl < 0:
                    r["cur_drawdown"] += eq_pnl
                    r["max_drawdown"] = min(r["max_drawdown"], r["cur_drawdown"])
                else:
                    r["cur_drawdown"] = 0

        # 更新增量统计（把第 t 期开奖号计入历史）
        d = draws[t]
        freq[d] += 1
        if last_seen_idx[d] >= 0:
            g = t - last_seen_idx[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen_idx[d] = t
        tail_last[TAIL[d]] = t
        zodiac_last[ZODIAC[d]] = t
        element_last[ELEMENT[d]] = t
        color_last[COLOR[d]] = t

    return results


def build_report(results, min_n, max_n, dates):
    """把回测结果整理成报告，每个 (算法, n) 一行"""
    rows = []
    for aid, name, desc, _, _ in ALGORITHMS:
        for n in range(min_n, max_n + 1):
            r = results.get(aid, {}).get(n)
            if not r:
                continue
            total = r["total"]
            hit_rate = r["hits"] / total * 100 if total else 0
            rows.append({
                "algo_id": aid, "algo_name": name, "desc": desc, "n": n,
                "hits": r["hits"], "total": total,
                "hit_rate": round(hit_rate, 2),
                "eq_pnl": r["eq_pnl"],
                "eq_avg": round(r["eq_pnl"] / total, 3) if total else 0,
                "eq_days_pos": r["eq_days_pos"],
                "eq_win_rate": round(r["eq_days_pos"] / total * 100, 2) if total else 0,
                "bt_pnl": r["bt_pnl"],
                "max_drawdown": r["max_drawdown"],
            })
    return rows


def main():
    min_n = 3
    max_n = 25
    warmup = 100
    for i, a in enumerate(sys.argv[1:]):
        if a == "--min-n" and i + 1 < len(sys.argv) - 1:
            min_n = int(sys.argv[i + 2])
        if a == "--max-n" and i + 1 < len(sys.argv) - 1:
            max_n = int(sys.argv[i + 2])
        if a == "--warmup" and i + 1 < len(sys.argv) - 1:
            warmup = int(sys.argv[i + 2])

    print(f"读取记录...")
    dates, draws = load_records()
    print(f"共 {len(draws)} 期 ({dates[0]} ~ {dates[-1]})")

    count_map = load_count_value_map()
    print(f"count_value_map: {len(count_map)} 条")

    print(f"回测中：{len(ALGORITHMS)} 算法 × N={min_n}~{max_n}，warmup={warmup}...")
    import time
    st = time.time()
    results = run_backtest(draws, dates, count_map, min_n, max_n, warmup)
    print(f"回测完成，耗时 {time.time() - st:.1f}s")

    rows = build_report(results, min_n, max_n, dates)

    # 等额口径盈利排名
    eq_rank = sorted(rows, key=lambda x: -x["eq_pnl"])
    print(f"\n{'='*80}")
    print(f"【等额口径】盈利 TOP 20（每号1元，命中赔47倍）")
    print(f"{'='*80}")
    print(f"{'算法':<18}{'N':>4}{'命中率':>8}{'盈利天数%':>9}{'累计盈利':>10}{'单期均值':>9}{'最大回撤':>10}")
    for r in eq_rank[:20]:
        print(f"{r['algo_name']:<18}{r['n']:>4}{r['hit_rate']:>7.1f}%{r['eq_win_rate']:>8.1f}%{r['eq_pnl']:>10}{r['eq_avg']:>9}{r['max_drawdown']:>10}")

    print(f"\n【等额口径】亏损 BOTTOM 10")
    for r in eq_rank[-10:]:
        print(f"{r['algo_name']:<18}{r['n']:>4}{r['hit_rate']:>7.1f}%{r['eq_win_rate']:>8.1f}%{r['eq_pnl']:>10}{r['eq_avg']:>9}")

    # 倍投口径盈利排名
    bt_rank = sorted(rows, key=lambda x: -x["bt_pnl"])
    print(f"\n{'='*80}")
    print(f"【倍投口径】盈利 TOP 20（count_value_map 倍投）")
    print(f"{'='*80}")
    print(f"{'算法':<18}{'N':>4}{'命中率':>8}{'累计盈利':>12}")
    for r in bt_rank[:20]:
        print(f"{r['algo_name']:<18}{r['n']:>4}{r['hit_rate']:>7.1f}%{r['bt_pnl']:>12}")

    # 盈利方案统计
    eq_profitable = [r for r in rows if r["eq_pnl"] > 0]
    bt_profitable = [r for r in rows if r["bt_pnl"] > 0]
    print(f"\n总计 {len(rows)} 个方案")
    print(f"等额口径盈利方案：{len(eq_profitable)} 个（{len(eq_profitable)/len(rows)*100:.1f}%）")
    print(f"倍投口径盈利方案：{len(bt_profitable)} 个（{len(bt_profitable)/len(rows)*100:.1f}%）")

    # 命中率基线：随机选 N 个号的期望命中率 = N/49
    print(f"\n命中率基线（随机选 N 个号）:")
    for n in [3, 5, 10, 15, 20, 25]:
        print(f"  N={n}: 期望命中率 {n/49*100:.1f}%")

    # 保存结果
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "longest_tracking_result.json")
    payload = {
        "generated_at": datetime.now().isoformat(),
        "min_n": min_n, "max_n": max_n, "warmup": warmup,
        "total_records": len(draws),
        "date_range": [dates[0], dates[-1]],
        "eq_rank": eq_rank,
        "bt_rank": bt_rank,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
