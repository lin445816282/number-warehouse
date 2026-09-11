#!/usr/bin/env python3
"""
「最长跟踪」优化升级 — 数据验证脚本 v2
========================================

验证两个算法侧升级方向（在 67 算法「每期必下」基础上）：

  模型一：信号过滤下注（下注纪律）
    - 只在「信号强度 ≥ 阈值」时才下注，跳过弱信号期
    - 信号强度：遗漏降序类 = 最冷号遗漏期数(gap)；遗漏比类 = 最大遗漏比(gap/maxgap)
    - 阈值：gap 类 {10,15,20,25,30}；ratio 类 {0.5,0.6,0.7,0.8,0.9}
    - 核心问题：强冷号是否真的更容易回补（命中率 vs 随机基线 N/49）

  模型二：跟踪持有（冷号回补本义）
    - 锁定「最冷 1 号」，从 gap ≥ 阈值 进场，连续跟踪 K 期直到命中/止损
    - 参数：θ {10,15,20,25} × K {3,5,8,12}
    - 核心问题：冷号在 gap≥θ 后 K 期内回补概率 vs 随机基线 1-(48/49)^K

复用 tracking_engine.py 的分类字典 + load_records()。可重跑，输出 JSON + 报告。
"""
import sys, os, json, time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te

OUT_JSON = os.path.join(os.path.dirname(__file__), "tracking_v2_result.json")
OUT_MD   = os.path.join(os.path.dirname(__file__), "tracking_v2_report.md")


def _rand_sequence(seed=42):
    """预生成可复现随机对照用的 per-期 rand map（与 tracking_engine 一致）。"""
    import random
    random.seed(seed)
    return [{n: random.random() for n in range(1, 50)} for _ in range(10000)]


def _walk_stats(draws, warmup=100):
    """逐期增量维护统计，返回每期的 ctx（gap/freq/maxgap/ratio/分类gap）。仅算到每期预测前。"""
    M = len(draws)
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen_idx = {n: -1 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(te.ZODIAC.values())}
    element_last = {e: -1 for e in set(te.ELEMENT.values())}
    color_last = {c: -1 for c in set(te.COLOR.values())}

    ctxs = []   # ctxs[t] = 预测第 t 期时可用的统计
    for t in range(M):
        gap = {}
        for n in range(1, 50):
            ls = last_seen_idx[n]
            gap[n] = (t - ls) if ls >= 0 else t
        ratio = {n: gap[n] / max(maxgap[n], 1) for n in range(1, 50)}
        ctxs.append({
            "t": t, "gap": gap, "ratio": ratio, "freq": dict(freq),
            "maxgap": dict(maxgap), "last_seen_idx": dict(last_seen_idx),
        })
        # 更新（用第 t 期开奖号）
        if t < M - 1:
            d = draws[t]
            freq[d] += 1
            if last_seen_idx[d] >= 0:
                g = t - last_seen_idx[d] - 1
                if g > maxgap[d]:
                    maxgap[d] = g
            last_seen_idx[d] = t
            tail_last[te.TAIL[d]] = t
            zodiac_last[te.ZODIAC[d]] = t
            element_last[te.ELEMENT[d]] = t
            color_last[te.COLOR[d]] = t
    return ctxs


# ─────────────────────────────────────────────────────────────
# 模型一：信号过滤下注
# ─────────────────────────────────────────────────────────────
def backtest_signal_filter(draws, warmup=100):
    """只在信号≥阈值时下注。返回 (结果列表, 基线)。"""
    M = len(draws)
    ctxs = _walk_stats(draws, warmup)

    # 挑选信号过滤的算法子集：
    #   gap 类 = 排序键是遗漏降序（_sort_gap_desc 相关，信号 = max gap）
    #   ratio 类 = 遗漏比（_sort_ratio_desc，信号 = max ratio）
    gap_algos = []   # (id, name, sort_fn, filter)
    ratio_algos = []
    for (aid, name, desc, sort_fn, flt) in te.ALGORITHMS:
        if sort_fn is te._sort_gap_desc:
            gap_algos.append((aid, name, flt))
        elif sort_fn is te._sort_ratio_desc:
            ratio_algos.append((aid, name, flt))

    GAP_THRESH = [10, 15, 20, 25, 30]
    RATIO_THRESH = [0.5, 0.6, 0.7, 0.8, 0.9]
    N_LIST = [3, 4, 5]   # 聚焦小 N（历史结论：N=3~4 唯一正期望区）

    rows = []
    rand_maps = _rand_sequence()

    for (aid, name, flt) in gap_algos + ratio_algos:
        is_ratio = (aid, name, flt) in ratio_algos
        thresh_list = RATIO_THRESH if is_ratio else GAP_THRESH
        sig_key = "ratio" if is_ratio else "gap"

        for theta in thresh_list:
            for n in N_LIST:
                bets = hits = 0
                eq_pnl = 0
                for t in range(warmup, M):
                    ctx = ctxs[t]
                    # 信号强度 = 该算法排序第 1 名的排序键值
                    # 简化：gap 类信号 = max gap；ratio 类信号 = max ratio
                    sig = max(ctx[sig_key].values())
                    if sig < theta:
                        continue  # 信号不足，跳过不下注
                    # 选号：用算法的过滤器 + 排序
                    picks = te._select_numbers(aid, te._sort_gap_desc if not is_ratio else te._sort_ratio_desc,
                                               flt, ctx, n, draws[t-1], rand_maps[t])
                    bets += 1
                    actual = draws[t]
                    if actual in picks:
                        hits += 1
                        eq_pnl += (47 - n)
                    else:
                        eq_pnl += (-n)
                if bets == 0:
                    continue
                hit_rate = hits / bets * 100
                baseline = n / 49 * 100
                rows.append({
                    "model": "signal_filter",
                    "type": "ratio" if is_ratio else "gap",
                    "algo_id": aid, "algo": name, "theta": theta,
                    "n": n, "bets": bets, "hits": hits,
                    "hit_rate": round(hit_rate, 2), "baseline": round(baseline, 2),
                    "edge": round(hit_rate - baseline, 2),
                    "eq_pnl": eq_pnl, "eq_avg": round(eq_pnl / bets, 3),
                })
    return rows


# ─────────────────────────────────────────────────────────────
# 模型二：跟踪持有（最冷 1 号）
# ─────────────────────────────────────────────────────────────
def backtest_tracking_hold(draws, warmup=100):
    """锁定最冷 1 号，gap≥θ 进场，跟踪 K 期直到命中/止损。"""
    M = len(draws)
    ctxs = _walk_stats(draws, warmup)

    THETA = [10, 15, 20, 25]
    K_LIST = [3, 5, 8, 12]

    rows = []
    for theta in THETA:
        for K in K_LIST:
            rounds = wins = 0
            total_pnl = 0
            hit_delay_sum = 0
            # 状态：tracking_num / entered_t / held 期数
            tracking = None
            entered_t = None
            held = 0
            for t in range(warmup, M):
                if tracking is None:
                    # 空闲：检查是否进场（最冷号 gap ≥ θ）
                    gap = ctxs[t]["gap"]
                    coldest = max(range(1, 50), key=lambda x: gap[x])
                    if gap[coldest] >= theta:
                        tracking = coldest
                        entered_t = t
                        held = 0
                    else:
                        continue
                # 跟踪中：第 t 期开奖是否命中
                held += 1
                actual = draws[t]
                if actual == tracking:
                    rounds += 1
                    wins += 1
                    hit_delay_sum += held
                    total_pnl += (47 - held)   # 投入 held 元，命中得 47
                    tracking = None
                elif held >= K:
                    rounds += 1
                    total_pnl += (-K)          # K 期全未命中，亏 K 元
                    tracking = None
                # 否则继续跟踪
            if rounds == 0:
                continue
            win_rate = wins / rounds * 100
            # 随机基线：单号 K 期内至少命中一次 = 1 - (48/49)^K
            base = (1 - (48/49) ** K) * 100
            rows.append({
                "model": "tracking_hold",
                "theta": theta, "K": K,
                "rounds": rounds, "wins": wins,
                "win_rate": round(win_rate, 2), "baseline": round(base, 2),
                "edge": round(win_rate - base, 2),
                "avg_hit_delay": round(hit_delay_sum / wins, 2) if wins else None,
                "total_pnl": total_pnl,
                "avg_pnl": round(total_pnl / rounds, 3),
            })
    return rows


def _track_hold_range(ctxs, draws, t0, t1, warmup=100, theta=10, K=12):
    """在 [t0,t1) 期范围跑跟踪持有，返回 (rounds, wins, pnl, hit_delay_sum)。"""
    rounds = wins = pnl = 0
    hd = 0
    tracking = None
    held = 0
    for t in range(max(t0, warmup), t1):
        if tracking is None:
            gap = ctxs[t]["gap"]
            coldest = max(range(1, 50), key=lambda x: gap[x])
            if gap[coldest] >= theta:
                tracking = coldest
                held = 0
            else:
                continue
        held += 1
        if draws[t] == tracking:
            rounds += 1
            wins += 1
            hd += held
            pnl += (47 - held)
            tracking = None
        elif held >= K:
            rounds += 1
            pnl += (-K)
            tracking = None
    return rounds, wins, pnl, hd


def _binomial_pvalue(n, k, p0):
    """二项分布单尾 p 值（正态近似 z 检验）。"""
    import math
    mu = n * p0
    sigma = math.sqrt(n * p0 * (1 - p0))
    z = (k - mu) / sigma if sigma > 0 else 0
    pval = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return z, pval


def analyze_oos(draws, warmup=100):
    """真样本外验证（前段训练 vs 后段测试）+ 滚动窗口 + 显著性。"""
    ctxs = _walk_stats(draws, warmup)
    M = len(draws)
    half = M // 2
    out = {"oos": [], "rolling": [], "significance": []}
    K_LIST = [3, 5, 8, 12]
    for K in K_LIST:
        base = (1 - (48 / 49) ** K) * 100
        r1, w1, p1, h1 = _track_hold_range(ctxs, draws, 0, half, warmup, K=K)
        r2, w2, p2, h2 = _track_hold_range(ctxs, draws, half, M, warmup, K=K)
        out["oos"].append({
            "K": K, "base": round(base, 2),
            "front": {"rounds": r1, "wins": w1, "rate": round(w1 / r1 * 100, 2) if r1 else 0, "pnl": p1},
            "back": {"rounds": r2, "wins": w2, "rate": round(w2 / r2 * 100, 2) if r2 else 0, "pnl": p2},
        })
    # 滚动窗口（每 200 期，窗宽 400）
    for K in [8, 12]:
        base = (1 - (48 / 49) ** K) * 100
        for start in range(0, M - 400, 200):
            r, w, p, h = _track_hold_range(ctxs, draws, start, start + 400, warmup, K=K)
            if r == 0:
                continue
            out["rolling"].append({
                "K": K, "start": start, "end": start + 400,
                "rounds": r, "wins": w,
                "rate": round(w / r * 100, 2), "base": round(base, 2),
                "edge": round(w / r * 100 - base, 2), "pnl": p,
            })
    # 显著性（全量）
    for K in K_LIST:
        r, w, p, h = _track_hold_range(ctxs, draws, 0, M, warmup, K=K)
        p0 = (1 - (48 / 49) ** K)
        z, pval = _binomial_pvalue(r, w, p0)
        out["significance"].append({
            "K": K, "n": r, "wins": w,
            "rate": round(w / r * 100, 2), "base": round(p0 * 100, 2),
            "z": round(z, 3), "p": round(pval, 4),
        })
    return out


def build_report(sf_rows, th_rows, n_draws, oos=None):
    L = []
    L.append("# 最长跟踪优化升级 — 数据验证报告 v2")
    L.append("")
    L.append(f"> 生成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 数据 {n_draws} 期 · 预热 100 期")
    L.append("> 对比基准：命中率 vs 随机基线（信号过滤 = N/49；跟踪持有 = 1-(48/49)^K）")
    L.append("")
    L.append("## 一、信号过滤下注（只在强信号时下注）")
    L.append("")
    L.append("| 算法 | 信号阈值 | N | 下注次数 | 命中率 | 随机基线 | 超基线 | 等额盈亏 | 单期均值 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    # 按超基线幅度排序展示 TOP
    sf_sorted = sorted(sf_rows, key=lambda r: -r["edge"])
    for r in sf_sorted:
        flag = "🟢" if r["eq_pnl"] > 0 else ("🟡" if r["edge"] > 0 else "🔴")
        L.append(f"| {r['algo']} | {r['theta']} | {r['n']} | {r['bets']} | {r['hit_rate']}% | {r['baseline']}% | {r['edge']:+.2f} | {r['eq_pnl']:>6} | {r['eq_avg']} |")
    L.append("")
    L.append("## 二、跟踪持有（锁定最冷 1 号，跟踪 K 期）")
    L.append("")
    L.append("| 进场阈值θ | K期 | 跟踪轮数 | 命中率 | 随机基线 | 超基线 | 平均命中期 | 总盈亏 | 单轮均值 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    th_sorted = sorted(th_rows, key=lambda r: -r["edge"])
    for r in th_sorted:
        flag = "🟢" if r["total_pnl"] > 0 else ("🟡" if r["edge"] > 0 else "🔴")
        L.append(f"| {r['theta']} | {r['K']} | {r['rounds']} | {r['win_rate']}% | {r['baseline']}% | {r['edge']:+.2f} | {r['avg_hit_delay']} | {r['total_pnl']:>6} | {r['avg_pnl']} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 结论判读")
    L.append("")
    L.append("- **信号过滤**：若超基线幅度（edge）在信号阈值提高后单调上升 → 冷号回补有真实信号；若 edge 始终≈0 → 无信号。")
    L.append("- **跟踪持有**：若命中率随 θ 提高而上升且显著超随机基线 → 「越冷越该出」成立；否则冷号回补仅是随机波动。")
    L.append("- 等额盈亏 > 0 才算可交易（命中率 > N/47 或单轮期望 > 0）。")
    L.append("")
    if oos:
        L.append("## 三、真样本外验证（前段训练 → 后段测试，无重叠）")
        L.append("")
        L.append("| K期 | 随机基线 | 前段命中率 | 前段盈亏 | 后段命中率 | 后段盈亏 |")
        L.append("|---|---|---|---|---|---|")
        for o in oos["oos"]:
            fr, bk = o["front"], o["back"]
            fflag = "🟢" if fr["pnl"] > 0 else "🔴"
            bflag = "🟢" if bk["pnl"] > 0 else "🔴"
            L.append(f"| {o['K']} | {o['base']}% | {fr['rate']}% {fflag} | {fr['pnl']} | {bk['rate']}% {bflag} | {bk['pnl']} |")
        L.append("")
        L.append("## 四、滚动窗口验证（每 200 期，窗宽 400）")
        L.append("")
        L.append("| K | 窗口 | 轮数 | 命中率 | 基线 | 超基线 | 盈亏 |")
        L.append("|---|---|---|---|---|---|---|")
        for r in oos["rolling"]:
            flag = "🟢" if r["edge"] > 0 else "🔴"
            L.append(f"| {r['K']} | {r['start']}~{r['end']} | {r['rounds']} | {r['rate']}% | {r['base']}% | {r['edge']:+.2f}% {flag} | {r['pnl']} |")
        L.append("")
        L.append("## 五、显著性检验（二项分布单尾）")
        L.append("")
        L.append("| K期 | 样本 | 命中 | 命中率 | 基线 | z | p值 | 判定 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for s in oos["significance"]:
            verdict = "显著" if s["p"] < 0.05 else "不显著"
            L.append(f"| {s['K']} | {s['n']} | {s['wins']} | {s['rate']}% | {s['base']}% | {s['z']} | {s['p']} | {verdict} |")
        L.append("")
    L.append(f"> 本报告由 `analysis/tracking_v2_backtest.py` 生成，可重跑。结构化数据见 `tracking_v2_result.json`。")
    return "\n".join(L)


if __name__ == "__main__":
    dates, draws = te.load_records()
    print(f"数据：{len(draws)} 期 ({dates[0]} ~ {dates[-1]})")
    st = time.time()

    print("跑信号过滤回测...")
    sf = backtest_signal_filter(draws)
    print(f"  信号过滤方案 {len(sf)} 个，耗时 {time.time()-st:.1f}s")

    st2 = time.time()
    print("跑跟踪持有回测...")
    th = backtest_tracking_hold(draws)
    print(f"  跟踪持有方案 {len(th)} 个，耗时 {time.time()-st2:.1f}s")

    # 汇总关键指标
    sf_positive = [r for r in sf if r["eq_pnl"] > 0]
    th_positive = [r for r in th if r["total_pnl"] > 0]
    sf_best = max(sf, key=lambda r: r["edge"]) if sf else None
    th_best = max(th, key=lambda r: r["edge"]) if th else None

    print(f"\n信号过滤：{len(sf_positive)}/{len(sf)} 等额盈利；最佳超基线 {sf_best['edge'] if sf_best else 0}%")
    print(f"跟踪持有：{len(th_positive)}/{len(th)} 总盈亏为正；最佳超基线 {th_best['edge'] if th_best else 0}%")

    print("样本外验证 + 滚动 + 显著性...")
    oos = analyze_oos(draws)
    for o in oos["oos"]:
        print(f"  K={o['K']}: 前段 {o['front']['rate']}% (pnl{o['front']['pnl']}) / 后段 {o['back']['rate']}% (pnl{o['back']['pnl']})")
    for s in oos["significance"]:
        print(f"  显著性 K={s['K']}: z={s['z']}, p={s['p']}")

    data = {"signal_filter": sf, "tracking_hold": th, "oos": oos, "n_draws": len(draws)}
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    report = build_report(sf, th, len(draws), oos)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n已输出：{OUT_JSON} / {OUT_MD}")
