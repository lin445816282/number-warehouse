#!/usr/bin/env python3
"""
「最长跟踪」演算引擎（后端模块版）
冷号回补策略回测：从最长未出号码(冷号)按不同算法拆分 3~25 个号，回测历史找盈利方案。

供 main.py import 使用，也可独立运行。
"""
import json
import sqlite3
import os
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BACKEND_DIR, "data", "warehouse.db")

# ── 号码分类（静态）──
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
JIAQIN = {"牛","马","羊","鸡","狗","猪"}
YESHOU = {"鼠","虎","兔","龙","蛇","猴"}


def _sort_gap_desc(num, ctx):      return ctx["gap"][num]
def _sort_ratio_desc(num, ctx):    return ctx["gap"][num] / max(ctx["maxgap"][num], 1)
def _sort_freq_asc(num, ctx):      return -ctx["freq"][num]
def _sort_maxgap_desc(num, ctx):   return ctx["maxgap"][num]
def _sort_last_asc(num, ctx):      return -ctx["last_seen_idx"][num]
def _sort_gap_tail(num, ctx):      return ctx["gap"][num] + ctx["tail_gap"][TAIL[num]] * 3
def _sort_gap_zodiac(num, ctx):    return ctx["gap"][num] + ctx["zodiac_gap"][ZODIAC[num]] * 3
def _sort_gap_element(num, ctx):   return ctx["gap"][num] + ctx["element_gap"][ELEMENT[num]] * 3
def _sort_gap_color(num, ctx):     return ctx["gap"][num] + ctx["color_gap"][COLOR[num]] * 3
def _sort_gap_freq(num, ctx):      return ctx["gap"][num] * 2 - ctx["freq"][num]
def _sort_random(num, ctx):        return ctx["_rand"][num]
# ── 扩展排序键（2026-09-10 新增：热号 / 独立分类遗漏 / 相对冷度）──
def _sort_last_desc(num, ctx):     return ctx["last_seen_idx"][num]                       # 热号：最近出现优先
def _sort_freq_desc(num, ctx):     return ctx["freq"][num]                                # 热号：历史频率最高
def _sort_gap_over_freq(num, ctx): return ctx["gap"][num] / max(ctx["freq"][num], 1)      # 相对冷度：遗漏/频率
def _sort_zodiac_gap(num, ctx):    return ctx["zodiac_gap"][ZODIAC[num]]                  # 生肖遗漏降序
def _sort_element_gap(num, ctx):   return ctx["element_gap"][ELEMENT[num]]                # 五行遗漏降序
def _sort_color_gap(num, ctx):     return ctx["color_gap"][COLOR[num]]                    # 波色遗漏降序
def _sort_tail_gap(num, ctx):      return ctx["tail_gap"][TAIL[num]]                      # 尾数遗漏降序


def _f_none(num): return True
def _f_tail_0_4(num): return TAIL[num] <= 4
def _f_tail_5_9(num): return TAIL[num] >= 5
def _f_odd(num): return ODD_EVEN[num] == "单"
def _f_even(num): return ODD_EVEN[num] == "双"
def _f_big(num): return BIG_SMALL[num] == "大"
def _f_small(num): return BIG_SMALL[num] == "小"
def _f_sum_odd(num): return SUM_PARITY[num] == "合单"
def _f_sum_even(num): return SUM_PARITY[num] == "合双"
def _f_jiaqin(num): return ZODIAC[num] in JIAQIN
def _f_yeshou(num): return ZODIAC[num] in YESHOU
def _f_el_jin(num): return ELEMENT[num] == "金"
def _f_el_mu(num): return ELEMENT[num] == "木"
def _f_el_shui(num): return ELEMENT[num] == "水"
def _f_el_huo(num): return ELEMENT[num] == "火"
def _f_el_tu(num): return ELEMENT[num] == "土"
def _f_color_hong(num): return COLOR[num] == "红波"
def _f_color_lan(num): return COLOR[num] == "蓝波"
def _f_color_lv(num): return COLOR[num] == "绿波"
def _f_tail_single(num): return TAIL[num] % 2 == 1
def _f_tail_double(num): return TAIL[num] % 2 == 0
PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47}
def _f_prime(num): return num in PRIMES
def _f_composite(num): return num > 1 and num not in PRIMES


FILTER_FUNCS = {
    "none": _f_none, "tail_0_4": _f_tail_0_4, "tail_5_9": _f_tail_5_9,
    "odd": _f_odd, "even": _f_even, "big": _f_big, "small": _f_small,
    "sum_odd": _f_sum_odd, "sum_even": _f_sum_even,
    "jiaqin": _f_jiaqin, "yeshou": _f_yeshou,
    "el_jin": _f_el_jin, "el_mu": _f_el_mu, "el_shui": _f_el_shui,
    "el_huo": _f_el_huo, "el_tu": _f_el_tu,
    "color_hong": _f_color_hong, "color_lan": _f_color_lan, "color_lv": _f_color_lv,
    "tail_single": _f_tail_single, "tail_double": _f_tail_double,
    "prime": _f_prime, "composite": _f_composite,
}

DYNAMIC_FILTERS = {"zodiac_prev", "zodiac_not_prev", "tail_prev", "tail_not_prev",
                   "prev_neighbor_1", "prev_neighbor_2"}
TAIL_SETS = {37: {0,5}, 38: {1,6}, 39: {2,7}, 40: {3,8}, 41: {4,9}}


def _make_dynamic_filter(name, prev_draw):
    def f(num):
        if name == "zodiac_prev": return ZODIAC[num] == ZODIAC.get(prev_draw, "")
        if name == "zodiac_not_prev": return ZODIAC[num] != ZODIAC.get(prev_draw, "")
        if name == "tail_prev": return TAIL[num] == TAIL.get(prev_draw, -1)
        if name == "tail_not_prev": return TAIL[num] != TAIL.get(prev_draw, -1)
        if name == "prev_neighbor_1": return abs(num - prev_draw) == 1
        if name == "prev_neighbor_2": return 1 <= abs(num - prev_draw) <= 2
        return True
    return f


# 50 种算法：id, 名称, 描述, 排序键, 过滤器
ALGORITHMS = [
    (1,  "遗漏降序",           "当前遗漏期数最长的号",               _sort_gap_desc,   "none"),
    (2,  "遗漏·尾0-4",         "遗漏降序 ∩ 尾数0-4",                _sort_gap_desc,   "tail_0_4"),
    (3,  "遗漏·尾5-9",         "遗漏降序 ∩ 尾数5-9",                _sort_gap_desc,   "tail_5_9"),
    (4,  "遗漏·单号",          "遗漏降序 ∩ 单号",                   _sort_gap_desc,   "odd"),
    (5,  "遗漏·双号",          "遗漏降序 ∩ 双号",                   _sort_gap_desc,   "even"),
    (6,  "遗漏·大号",          "遗漏降序 ∩ 大号(25-49)",            _sort_gap_desc,   "big"),
    (7,  "遗漏·小号",          "遗漏降序 ∩ 小号(1-24)",             _sort_gap_desc,   "small"),
    (8,  "遗漏·合单",          "遗漏降序 ∩ 合单",                   _sort_gap_desc,   "sum_odd"),
    (9,  "遗漏·合双",          "遗漏降序 ∩ 合双",                   _sort_gap_desc,   "sum_even"),
    (10, "遗漏·家禽",          "遗漏降序 ∩ 家禽(牛马羊鸡狗猪)",     _sort_gap_desc,   "jiaqin"),
    (11, "遗漏·野兽",          "遗漏降序 ∩ 野兽(鼠虎兔龙蛇猴)",     _sort_gap_desc,   "yeshou"),
    (12, "遗漏·上期生肖",      "遗漏降序 ∩ 上期生肖",               _sort_gap_desc,   "zodiac_prev"),
    (13, "遗漏·避开上期生肖",  "遗漏降序 ∩ 避开上期生肖",           _sort_gap_desc,   "zodiac_not_prev"),
    (14, "遗漏·五行金",        "遗漏降序 ∩ 五行金",                 _sort_gap_desc,   "el_jin"),
    (15, "遗漏·五行木",        "遗漏降序 ∩ 五行木",                 _sort_gap_desc,   "el_mu"),
    (16, "遗漏·五行水",        "遗漏降序 ∩ 五行水",                 _sort_gap_desc,   "el_shui"),
    (17, "遗漏·五行火",        "遗漏降序 ∩ 五行火",                 _sort_gap_desc,   "el_huo"),
    (18, "遗漏·五行土",        "遗漏降序 ∩ 五行土",                 _sort_gap_desc,   "el_tu"),
    (19, "遗漏·红波",          "遗漏降序 ∩ 红波",                   _sort_gap_desc,   "color_hong"),
    (20, "遗漏·蓝波",          "遗漏降序 ∩ 蓝波",                   _sort_gap_desc,   "color_lan"),
    (21, "遗漏·绿波",          "遗漏降序 ∩ 绿波",                   _sort_gap_desc,   "color_lv"),
    (22, "遗漏比·全号",        "遗漏/历史最长 比例降序",            _sort_ratio_desc, "none"),
    (23, "遗漏比·单号",        "遗漏/历史最长 比例降序 ∩ 单号",     _sort_ratio_desc, "odd"),
    (24, "遗漏比·双号",        "遗漏/历史最长 比例降序 ∩ 双号",     _sort_ratio_desc, "even"),
    (25, "遗漏比·大号",        "遗漏/历史最长 比例降序 ∩ 大号",     _sort_ratio_desc, "big"),
    (26, "遗漏比·小号",        "遗漏/历史最长 比例降序 ∩ 小号",     _sort_ratio_desc, "small"),
    (27, "频率冷号",           "历史出现次数最少的号",               _sort_freq_asc,   "none"),
    (28, "频率冷·单号",        "历史出现次数最少 ∩ 单号",           _sort_freq_asc,   "odd"),
    (29, "频率冷·大号",        "历史出现次数最少 ∩ 大号",           _sort_freq_asc,   "big"),
    (30, "历史最长遗漏",       "历史最大遗漏期数最长的号",           _sort_maxgap_desc,"none"),
    (31, "历史最长·单号",      "历史最大遗漏 ∩ 单号",               _sort_maxgap_desc,"odd"),
    (32, "最久未出现",         "距上次出现最久的号(同遗漏降序)",     _sort_last_asc,   "none"),
    (33, "遗漏·上期尾数",      "遗漏降序 ∩ 上期尾数",               _sort_gap_desc,   "tail_prev"),
    (34, "遗漏·避开上期尾数",  "遗漏降序 ∩ 避开上期尾数",           _sort_gap_desc,   "tail_not_prev"),
    (35, "遗漏·尾单",          "遗漏降序 ∩ 尾数单(1,3,5,7,9)",     _sort_gap_desc,   "tail_single"),
    (36, "遗漏·尾双",          "遗漏降序 ∩ 尾数双(0,2,4,6,8)",     _sort_gap_desc,   "tail_double"),
    (37, "遗漏·尾0/5",         "遗漏降序 ∩ 尾数0或5",               _sort_gap_desc,   None),
    (38, "遗漏·尾1/6",         "遗漏降序 ∩ 尾数1或6",               _sort_gap_desc,   None),
    (39, "遗漏·尾2/7",         "遗漏降序 ∩ 尾数2或7",               _sort_gap_desc,   None),
    (40, "遗漏·尾3/8",         "遗漏降序 ∩ 尾数3或8",               _sort_gap_desc,   None),
    (41, "遗漏·尾4/9",         "遗漏降序 ∩ 尾数4或9",               _sort_gap_desc,   None),
    (42, "遗漏×尾数加权",      "遗漏 + 尾数遗漏×3 加权",            _sort_gap_tail,   "none"),
    (43, "遗漏×生肖加权",      "遗漏 + 生肖遗漏×3 加权",            _sort_gap_zodiac, "none"),
    (44, "遗漏×五行加权",      "遗漏 + 五行遗漏×3 加权",            _sort_gap_element,"none"),
    (45, "遗漏×波色加权",      "遗漏 + 波色遗漏×3 加权",            _sort_gap_color,  "none"),
    (46, "遗漏×频率综合",      "遗漏×2 - 频率 综合评分",            _sort_gap_freq,   "none"),
    (47, "全维度冷号投票",     "遗漏+尾数+生肖+五行 多维冷号",       None,            None),
    (48, "遗漏·去极值",        "遗漏降序 但跳过最冷1个",            _sort_gap_desc,   "skip_coldest_1"),
    (49, "遗漏·去极值3",       "遗漏降序 但跳过最冷3个",            _sort_gap_desc,   "skip_coldest_3"),
    (50, "随机对照",           "从49号随机选(基线对照)",            _sort_random,     "none"),

    # ── 扩展算法 51-67（2026-09-10 新增：热号 / 质数合数 / 独立分类遗漏 / 相对冷度 / 邻号）──
    (51, "热号·最近出现",      "距上次出现最近(上期号优先)",        _sort_last_desc,  "none"),
    (52, "热号·频率最高",      "历史出现次数最多的号",               _sort_freq_desc,  "none"),
    (53, "热号·单号",          "最近出现优先 ∩ 单号",               _sort_last_desc,  "odd"),
    (54, "热号·双号",          "最近出现优先 ∩ 双号",               _sort_last_desc,  "even"),
    (55, "热号·大号",          "最近出现优先 ∩ 大号",               _sort_last_desc,  "big"),
    (56, "热号·小号",          "最近出现优先 ∩ 小号",               _sort_last_desc,  "small"),
    (57, "遗漏·质数",          "遗漏降序 ∩ 质数(2,3,5,7,...47)",    _sort_gap_desc,   "prime"),
    (58, "遗漏·合数",          "遗漏降序 ∩ 合数",                   _sort_gap_desc,   "composite"),
    (59, "生肖遗漏降序",       "生肖整体遗漏最久 → 选该生肖号",     _sort_zodiac_gap, "none"),
    (60, "五行遗漏降序",       "五行整体遗漏最久 → 选该五行号",     _sort_element_gap,"none"),
    (61, "波色遗漏降序",       "波色整体遗漏最久 → 选该波色号",     _sort_color_gap,  "none"),
    (62, "尾数遗漏降序",       "尾数整体遗漏最久 → 选该尾数号",     _sort_tail_gap,   "none"),
    (63, "遗漏/频率比",        "遗漏÷(频率+1) 降序(相对冷度)",      _sort_gap_over_freq, "none"),
    (64, "上期邻号±1",         "上期开奖号前后邻号 ∩ 遗漏降序",     _sort_gap_desc,   "prev_neighbor_1"),
    (65, "上期邻号±2",         "上期开奖号前后2邻号 ∩ 遗漏降序",    _sort_gap_desc,   "prev_neighbor_2"),
    (66, "遗漏比·质数",        "遗漏/历史最长 比例降序 ∩ 质数",     _sort_ratio_desc, "prime"),
    (67, "热号·上期生肖",      "最近出现优先 ∩ 上期生肖",           _sort_last_desc,  "zodiac_prev"),
]


def load_records():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT date, draw_number FROM records ORDER BY date").fetchall()
    db.close()
    return [r["date"] for r in rows], [r["draw_number"] for r in rows]


def load_count_value_map():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT count_n, value FROM count_value_map ORDER BY count_n").fetchall()
    db.close()
    return {r["count_n"]: r["value"] for r in rows}


def _select_numbers(algo_id, algo_sort, algo_filter, ctx, n, prev_draw, rand_map):
    nums = list(range(1, 50))

    if algo_id == 47:
        scores = []
        for num in nums:
            s = ctx["gap"][num] + ctx["tail_gap"][TAIL[num]] + ctx["zodiac_gap"][ZODIAC[num]] + ctx["element_gap"][ELEMENT[num]]
            scores.append((s, num))
        scores.sort(key=lambda x: -x[0])
        return [x[1] for x in scores[:n]]

    if algo_id == 50:
        ctx["_rand"] = rand_map
        order = sorted(nums, key=lambda x: -ctx["_rand"][x])
        return order[:n]

    if algo_filter is not None and algo_filter not in ("skip_coldest_1", "skip_coldest_3"):
        if algo_filter in DYNAMIC_FILTERS:
            f = _make_dynamic_filter(algo_filter, prev_draw)
        else:
            f = FILTER_FUNCS[algo_filter]
        nums = [x for x in nums if f(x)]
    elif algo_id in TAIL_SETS:
        ts = TAIL_SETS[algo_id]
        nums = [x for x in nums if TAIL[x] in ts]

    ctx["_rand"] = rand_map
    order = sorted(nums, key=lambda x: -algo_sort(x, ctx))

    if algo_filter == "skip_coldest_1":
        order = order[1:]
    elif algo_filter == "skip_coldest_3":
        order = order[3:]

    return order[:n]


def run_backtest(draws, dates, count_map, min_n=3, max_n=25, warmup=100):
    """跑全部 50 算法 × N 回测，返回 {algo_id: {n: {...}}}"""
    M = len(draws)
    import random as _random
    _random.seed(42)

    rand_maps = []
    for _ in range(M):
        rand_maps.append({n: _random.random() for n in range(1, 50)})

    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen_idx = {n: -1 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(ZODIAC.values())}
    element_last = {e: -1 for e in set(ELEMENT.values())}
    color_last = {c: -1 for c in set(COLOR.values())}

    results = {}

    for t in range(warmup, M):
        prev_draw = draws[t - 1]

        tail_gap = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
        zodiac_gap = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
        element_gap = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
        color_gap = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}

        gap = {}
        for n in range(1, 50):
            ls = last_seen_idx[n]
            gap[n] = (t - ls) if ls >= 0 else t
        ctx = {
            "gap": gap, "maxgap": maxgap, "freq": freq,
            "last_seen_idx": last_seen_idx,
            "tail_gap": tail_gap, "zodiac_gap": zodiac_gap,
            "element_gap": element_gap, "color_gap": color_gap,
            "_rand": None,
        }

        actual = draws[t]

        for (aid, name, desc, sort_fn, flt) in ALGORITHMS:
            if aid not in results:
                results[aid] = {}
            for n in range(min_n, max_n + 1):
                picks = _select_numbers(aid, sort_fn, flt, ctx, n, prev_draw, rand_maps[t])
                hit = actual in picks
                eq_pnl = (47 - n) if hit else (-n)
                bt_cost = sum(count_map.get(ctx["gap"][p], 0) for p in picks)
                if hit:
                    hv = count_map.get(ctx["gap"][actual], 0)
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
                if eq_pnl < 0:
                    r["cur_drawdown"] += eq_pnl
                    r["max_drawdown"] = min(r["max_drawdown"], r["cur_drawdown"])
                else:
                    r["cur_drawdown"] = 0

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


def build_report(results, min_n, max_n):
    rows = []
    for aid, name, desc, _, _ in ALGORITHMS:
        for n in range(min_n, max_n + 1):
            r = results.get(aid, {}).get(n)
            if not r:
                continue
            total = r["total"]
            rows.append({
                "algo_id": aid, "algo_name": name, "desc": desc, "n": n,
                "hits": r["hits"], "total": total,
                "hit_rate": round(r["hits"] / total * 100, 2) if total else 0,
                "eq_pnl": r["eq_pnl"],
                "eq_avg": round(r["eq_pnl"] / total, 3) if total else 0,
                "eq_days_pos": r["eq_days_pos"],
                "eq_win_rate": round(r["eq_days_pos"] / total * 100, 2) if total else 0,
                "bt_pnl": r["bt_pnl"],
                "max_drawdown": r["max_drawdown"],
            })
    return rows


def run_tracking_hold(draws, theta=10, K=12, warmup=100, signal="gap", start_period=None, min_votes=4):
    """跟踪持有回测：锁定最冷 1 号，进场信号≥theta 时进场，跟踪 K 期直到命中/止损。

    signal="gap"：进场信号 = 遗漏期数（theta 默认 10，遗漏 ≥ theta 进场）。
    signal="ratio"：进场信号 = 遗漏比 gap/历史最大遗漏（theta 默认 0.8，比例 ≥ theta 进场）。
    signal="consensus"：7 度量投票取共识号（得票 ≥ min_votes 才进场，默认 4），更稳健。

    start_period：从第几期开始跟踪统计（默认 warmup）。gap 始终用完整历史（第 0 期累计），
    用于真样本外验证：后段测试传 start_period=half，gap 含前段历史但只统计后段。

    返回 dict：rounds/wins/win_rate/baseline/edge/avg_hit_delay/total_pnl/avg_pnl/max_drawdown/equity_curve
    """
    M = len(draws)
    start = start_period if start_period is not None else warmup
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen_idx = {n: -1 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(ZODIAC.values())}
    element_last = {e: -1 for e in set(ELEMENT.values())}
    color_last = {c: -1 for c in set(COLOR.values())}

    rounds = wins = total_pnl = 0
    hit_delay_sum = 0
    cur_equity = 0
    max_equity = 0
    max_drawdown = 0
    equity = []
    tracking = None
    held = 0

    # 阶段1：第 0..start-1 期，只维护遗漏统计（完整历史预热）
    for t in range(min(start, M)):
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

    for t in range(start, M):
        gap = {}
        for n in range(1, 50):
            ls = last_seen_idx[n]
            gap[n] = (t - ls) if ls >= 0 else t

        if tracking is None:
            if signal == "consensus":
                tg = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
                zg = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
                eg = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
                cg = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}
                ms = {
                    "gap": lambda n: gap[n],
                    "ratio": lambda n: gap[n] / max(maxgap[n], 1),
                    "tail": lambda n: gap[n] + tg[TAIL[n]] * 3,
                    "zodiac": lambda n: gap[n] + zg[ZODIAC[n]] * 3,
                    "element": lambda n: gap[n] + eg[ELEMENT[n]] * 3,
                    "color": lambda n: gap[n] + cg[COLOR[n]] * 3,
                    "alldim": lambda n: gap[n] + tg[TAIL[n]] + zg[ZODIAC[n]] + eg[ELEMENT[n]],
                }
                votes = {}
                for _name, _fn in ms.items():
                    _c = max(range(1, 50), key=_fn)
                    votes[_c] = votes.get(_c, 0) + 1
                top = max(votes.values())
                if top >= min_votes:
                    tracking = max([n for n, c in votes.items() if c == top], key=lambda x: gap[x])
                    held = 0
            else:
                if signal == "ratio":
                    coldest = max(range(1, 50), key=lambda x: gap[x] / max(maxgap[x], 1))
                    sig_val = gap[coldest] / max(maxgap[coldest], 1)
                else:
                    coldest = max(range(1, 50), key=lambda x: gap[x])
                    sig_val = gap[coldest]
                if sig_val >= theta:
                    tracking = coldest
                    held = 0

        if tracking is not None:
            held += 1
            actual = draws[t]
            if actual == tracking:
                rounds += 1
                wins += 1
                hit_delay_sum += held
                pnl = 47 - held
                total_pnl += pnl
                cur_equity += pnl
                tracking = None
            elif held >= K:
                rounds += 1
                pnl = -K
                total_pnl += pnl
                cur_equity += pnl
                tracking = None

        if cur_equity > max_equity:
            max_equity = cur_equity
        dd = cur_equity - max_equity
        if dd < max_drawdown:
            max_drawdown = dd
        equity.append(cur_equity)

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

    win_rate = wins / rounds * 100 if rounds else 0
    baseline = (1 - (48 / 49) ** K) * 100
    return {
        "theta": theta, "K": K, "signal": signal,
        "rounds": rounds, "wins": wins,
        "win_rate": round(win_rate, 2),
        "baseline": round(baseline, 2),
        "edge": round(win_rate - baseline, 2),
        "avg_hit_delay": round(hit_delay_sum / wins, 2) if wins else None,
        "total_pnl": total_pnl,
        "avg_pnl": round(total_pnl / rounds, 3) if rounds else 0,
        "max_drawdown": max_drawdown,
        "equity_curve": equity,
    }


def _consensus_pick(gap, maxgap, tg, zg, eg, cg, min_votes=4):
    """7 度量投票取共识号。返回 (共识号, 得票数)；得票不足返回 (None, top)。"""
    ms = {
        "gap": lambda n: gap[n],
        "ratio": lambda n: gap[n] / max(maxgap[n], 1),
        "tail": lambda n: gap[n] + tg[TAIL[n]] * 3,
        "zodiac": lambda n: gap[n] + zg[ZODIAC[n]] * 3,
        "element": lambda n: gap[n] + eg[ELEMENT[n]] * 3,
        "color": lambda n: gap[n] + cg[COLOR[n]] * 3,
        "alldim": lambda n: gap[n] + tg[TAIL[n]] + zg[ZODIAC[n]] + eg[ELEMENT[n]],
    }
    votes = {}
    for _name, _fn in ms.items():
        _c = max(range(1, 50), key=_fn)
        votes[_c] = votes.get(_c, 0) + 1
    top = max(votes.values())
    if top >= min_votes:
        num = max([n for n, c in votes.items() if c == top], key=lambda x: gap[x])
        return num, top
    return None, top


def tracking_hold_current(draws, theta=10, signal="gap", min_votes=4):
    """基于最新数据，计算当前最冷号 + 遗漏期数 + 是否建议进场。

    signal="gap"：按遗漏期数排序；signal="ratio"：按遗漏比(gap/历史最大遗漏)排序。
    返回 {coldest_num, coldest_gap, coldest_ratio, signal(布尔), top_cold}。
    """
    M = len(draws)
    last_seen = {}
    maxgap = {n: 0 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(ZODIAC.values())}
    element_last = {e: -1 for e in set(ELEMENT.values())}
    color_last = {c: -1 for c in set(COLOR.values())}
    for t, d in enumerate(draws):
        if d in last_seen:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t
        tail_last[TAIL[d]] = t
        zodiac_last[ZODIAC[d]] = t
        element_last[ELEMENT[d]] = t
        color_last[COLOR[d]] = t
    gaps = {}
    ratios = {}
    for n in range(1, 50):
        ls = last_seen.get(n, -1)
        gaps[n] = (M - ls) if ls >= 0 else M
        ratios[n] = gaps[n] / max(maxgap[n], 1)
    tg = {x: (M - tail_last[x]) if tail_last[x] >= 0 else M for x in range(10)}
    zg = {z: (M - zodiac_last[z]) if zodiac_last[z] >= 0 else M for z in zodiac_last}
    eg = {e: (M - element_last[e]) if element_last[e] >= 0 else M for e in element_last}
    cg = {c: (M - color_last[c]) if color_last[c] >= 0 else M for c in color_last}
    if signal == "consensus":
        num, top = _consensus_pick(gaps, maxgap, tg, zg, eg, cg, min_votes)
        return {
            "coldest_num": num,
            "coldest_gap": gaps[num] if num else None,
            "coldest_ratio": round(ratios[num], 3) if num else None,
            "signal": num is not None,
            "votes": top,
            "min_votes": min_votes,
            "top_cold": [{"num": n, "gap": gaps[n], "ratio": round(ratios[n], 3)}
                         for n in sorted(range(1, 50), key=lambda x: -gaps[x])[:5]],
        }
    if signal == "ratio":
        ordered = sorted(range(1, 50), key=lambda x: -ratios[x])
    else:
        ordered = sorted(range(1, 50), key=lambda x: -gaps[x])
    top_cold = [{"num": n, "gap": gaps[n], "ratio": round(ratios[n], 3)} for n in ordered[:5]]
    coldest_num = ordered[0]
    sig_val = ratios[coldest_num] if signal == "ratio" else gaps[coldest_num]
    return {
        "coldest_num": coldest_num,
        "coldest_gap": gaps[coldest_num],
        "coldest_ratio": round(ratios[coldest_num], 3),
        "signal": sig_val >= theta,
        "top_cold": top_cold,
    }


def tracking_hold_trail(draws, theta=10, K=12, warmup=100, tail=30, signal="gap", min_votes=4):
    """最近 tail 期的实盘模拟轨迹：逐期输出（跟踪号/命中/止损/累计盈亏），供前端展示。"""
    M = len(draws)
    # 复用 run_tracking_hold 的 walk-forward，但只记录最后 tail 期的轨迹
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen_idx = {n: -1 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(ZODIAC.values())}
    element_last = {e: -1 for e in set(ELEMENT.values())}
    color_last = {c: -1 for c in set(COLOR.values())}
    for t in range(min(warmup, M)):
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

    tracking = None
    held = 0
    cur_equity = 0
    trail = []          # 记录最近 tail 期
    trail_start = M - tail
    for t in range(warmup, M):
        gap = {n: (t - last_seen_idx[n]) if last_seen_idx[n] >= 0 else t for n in range(1, 50)}
        event = None
        if tracking is None:
            if signal == "consensus":
                tg = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
                zg = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
                eg = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
                cg = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}
                num, top = _consensus_pick(gap, maxgap, tg, zg, eg, cg, min_votes)
                if num is not None:
                    tracking = num
                    held = 0
            elif signal == "ratio":
                coldest = max(range(1, 50), key=lambda x: gap[x] / max(maxgap[x], 1))
                sig_val = gap[coldest] / max(maxgap[coldest], 1)
                if sig_val >= theta:
                    tracking = coldest
                    held = 0
            else:
                coldest = max(range(1, 50), key=lambda x: gap[x])
                sig_val = gap[coldest]
                if sig_val >= theta:
                    tracking = coldest
                    held = 0
        if tracking is not None:
            held += 1
            actual = draws[t]
            if actual == tracking:
                pnl = 47 - held
                cur_equity += pnl
                event = {"type": "hit", "num": tracking, "delay": held, "pnl": pnl}
                tracking = None
            elif held >= K:
                pnl = -K
                cur_equity += pnl
                event = {"type": "stop", "num": tracking, "delay": held, "pnl": pnl}
                tracking = None
            elif t >= trail_start:
                event = {"type": "hold", "num": tracking, "delay": held}
        if t >= trail_start:
            trail.append({"date": t, "num": tracking, "held": held,
                          "event": event, "equity": cur_equity})
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
    return trail


def tracking_hold_rounds(draws, theta=10, K=12, warmup=100, signal="gap", min_votes=4):
    """完整历史的每轮跟踪明细（实盘纸面跟踪）。

    返回 [{num, enter_idx, enter_gap, held, result, pnl, end_idx}]，按进场时间排序。
    result = "hit"（命中，pnl=47-held）/"stop"（止损，pnl=-K）。
    """
    M = len(draws)
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen_idx = {n: -1 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(ZODIAC.values())}
    element_last = {e: -1 for e in set(ELEMENT.values())}
    color_last = {c: -1 for c in set(COLOR.values())}
    for t in range(min(warmup, M)):
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

    rounds = []
    tracking = None
    held = 0
    enter_idx = None
    enter_gap = None
    for t in range(warmup, M):
        gap = {n: (t - last_seen_idx[n]) if last_seen_idx[n] >= 0 else t for n in range(1, 50)}
        if tracking is None:
            if signal == "consensus":
                tg = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
                zg = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
                eg = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
                cg = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}
                num, top = _consensus_pick(gap, maxgap, tg, zg, eg, cg, min_votes)
                if num is not None:
                    tracking = num
                    held = 0
                    enter_idx = t
                    enter_gap = gap[num]
            elif signal == "ratio":
                coldest = max(range(1, 50), key=lambda x: gap[x] / max(maxgap[x], 1))
                sig_val = gap[coldest] / max(maxgap[coldest], 1)
                if sig_val >= theta:
                    tracking = coldest
                    held = 0
                    enter_idx = t
                    enter_gap = gap[coldest]
            else:
                coldest = max(range(1, 50), key=lambda x: gap[x])
                sig_val = gap[coldest]
                if sig_val >= theta:
                    tracking = coldest
                    held = 0
                    enter_idx = t
                    enter_gap = gap[coldest]
        if tracking is not None:
            held += 1
            actual = draws[t]
            if actual == tracking:
                pnl = 47 - held
                rounds.append({"num": tracking, "enter_idx": enter_idx, "enter_gap": enter_gap,
                               "held": held, "result": "hit", "pnl": pnl, "end_idx": t})
                tracking = None
            elif held >= K:
                pnl = -K
                rounds.append({"num": tracking, "enter_idx": enter_idx, "enter_gap": enter_gap,
                               "held": held, "result": "stop", "pnl": pnl, "end_idx": t})
                tracking = None
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
    return rounds


# ── 算法文档 ──
# 分类映射：algo_id 区间 → (类别名, 说明)
ALGO_CATEGORIES = [
    ((1, 21),   "一、遗漏降序 × 属性过滤",   "当前遗漏期数最长的冷号，叠加 21 种属性过滤（尾数/单双/大小/合单双/家禽野兽/生肖/五行/波色）"),
    ((22, 26),  "二、遗漏比（遗漏÷历史最长）", "当前遗漏占该号历史最长遗漏的比例，比例越接近 1 说明逼近历史极限"),
    ((27, 29),  "三、频率冷号",             "历史出现次数最少的号（长期冷号）"),
    ((30, 31),  "四、历史最长遗漏",         "历史最大遗漏期数最长的号"),
    ((32, 32),  "五、最久未出现",           "距上次出现最久的号（等价遗漏降序）"),
    ((33, 41),  "六、遗漏 × 尾数",          "遗漏降序叠加尾数维度（上期尾/避开上期尾/尾单双/尾数两两组合 0-9）"),
    ((42, 46),  "七、多维加权",             "遗漏为主，叠加尾数/生肖/五行/波色/频率的加权评分"),
    ((47, 47),  "八、全维度冷号投票",       "遗漏 + 尾数 + 生肖 + 五行 四维冷度求和投票"),
    ((48, 49),  "九、去极值",               "遗漏降序但跳过最冷 1 或 3 个（避免极端冷号陷阱）"),
    ((50, 50),  "十、随机对照（基线）",     "从 49 号随机选，作为命中率基线对照"),
    ((51, 56),  "十一、热号（反向假设）",   "反向验证「热号延续」：最近出现 / 历史频率最高的号"),
    ((57, 58),  "十二、质数 / 合数",        "遗漏降序叠加质数/合数过滤"),
    ((59, 62),  "十三、独立分类遗漏",       "不看号码自身遗漏，只看生肖/五行/波色/尾数整体遗漏最久"),
    ((63, 63),  "十四、相对冷度",           "遗漏 ÷ (频率+1)，剔除高频率干扰后的相对冷度"),
    ((64, 65),  "十五、邻号",               "上期开奖号前后 ±1 / ±2 的邻号"),
    ((66, 66),  "十六、遗漏比 × 质数",      "遗漏比叠加质数过滤"),
    ((67, 67),  "十七、热号 × 上期生肖",    "最近出现优先叠加「与上期同生肖」过滤"),
]


def build_algorithm_doc():
    """生成算法文档（markdown），供前端「算法文档」按钮展示。"""
    lines = []
    lines.append("# 最长跟踪演算 — 算法文档")
    lines.append("")
    lines.append(f"> 共 {len(ALGORITHMS)} 种算法。每个算法对 49 个号码排序，取前 N 个（3~25）作为当期预测号。")
    lines.append("> 回测采用 walk-forward（无未来函数）：预测第 t 期只用第 1..t-1 期数据。")
    lines.append("> 双盈利口径：等额（每号 1 元，命中赔 47 倍）+ 倍投（按 count_value_map 遗漏倍投）。")
    lines.append("")
    for (lo, hi), cat, note in ALGO_CATEGORIES:
        lines.append(f"## {cat}")
        lines.append("")
        lines.append(f"> {note}")
        lines.append("")
        lines.append("| ID | 算法 | 说明 |")
        lines.append("|----|------|------|")
        for aid, name, desc, _, _ in ALGORITHMS:
            if lo <= aid <= hi:
                lines.append(f"| {aid} | {name} | {desc} |")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 命中率与盈亏基线")
    lines.append("")
    lines.append("- 随机选 N 个号的期望命中率 = N/49。")
    lines.append("- 等额口径盈亏平衡点命中率 = N/47（47 倍赔率 × 命中 N/47 = 收回 N 成本）。")
    lines.append("- 倍投口径盈利随遗漏指数放大，是杠杆假象，不可与等额口径直接比较。")
    lines.append("- ⚠️ 47 赔率 < 49 号码，等额口径长期负期望；冷号回补信号在历史数据上偏弱。")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import time
    dates, draws = load_records()
    count_map = load_count_value_map()
    print(f"{len(draws)} 期 ({dates[0]} ~ {dates[-1]})")
    st = time.time()
    results = run_backtest(draws, dates, count_map, 3, 25, 100)
    print(f"回测 {time.time()-st:.1f}s")
    rows = build_report(results, 3, 25)
    eq_rank = sorted(rows, key=lambda x: -x["eq_pnl"])
    for r in eq_rank[:10]:
        print(f"{r['algo_name']:<16} N={r['n']:<3} 命中率{r['hit_rate']:>6.1f}% 等额{r['eq_pnl']:>8} 倍投{r['bt_pnl']:>10}")