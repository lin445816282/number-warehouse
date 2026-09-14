#!/usr/bin/env python3
"""
全部方案逐一演算记录（纯数据，不下结论）
========================================
对用户讨论过的所有方案逐一真实演算，输出统一口径的数据表：
命中率、盈亏平衡线、单轮期望、总盈亏、前段/后段盈亏。

用法：python3 analysis/scheme_records.py
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def stat(rounds):
    if not rounds:
        return {"n": 0, "hits": 0, "rate": 0.0, "pnl": 0, "mu": 0.0, "d_bar": 0.0}
    hits = [r for r in rounds if r["result"] == "hit"]
    pnl = sum(r["pnl"] for r in rounds)
    n = len(rounds)
    d_bar = sum(r["held"] for r in hits) / len(hits) if hits else 0
    return {"n": n, "hits": len(hits), "rate": round(len(hits) / n * 100, 2),
            "pnl": pnl, "mu": round(pnl / n, 3), "d_bar": round(d_bar, 2)}


# ---- 通用 walk-forward：跟踪持有（买1号追K期）----
def track_hold(draws, signal="gap", theta=10, mv=4, K=12, warmup=100, record_from=None):
    M = len(draws)
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen = {n: -1 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(te.ZODIAC.values())}
    element_last = {e: -1 for e in set(te.ELEMENT.values())}
    color_last = {c: -1 for c in set(te.COLOR.values())}
    for t in range(min(warmup, M)):
        d = draws[t]; freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]: maxgap[d] = g
        last_seen[d] = t
        tail_last[te.TAIL[d]] = t; zodiac_last[te.ZODIAC[d]] = t
        element_last[te.ELEMENT[d]] = t; color_last[te.COLOR[d]] = t

    rounds = []
    tracking = None; held = 0
    start = record_from if record_from is not None else warmup
    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
        if tracking is None:
            if signal == "consensus":
                tg = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
                zg = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
                eg = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
                cg = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}
                num = te._consensus_pick(gap, maxgap, tg, zg, eg, cg, mv)[0]
            elif signal == "ratio":
                num = max(range(1, 50), key=lambda x: gap[x] / max(maxgap[x], 1))
                if gap[num] / max(maxgap[num], 1) < theta: num = None
            else:
                num = max(range(1, 50), key=lambda x: gap[x])
                if gap[num] < theta: num = None
            if num is not None:
                tracking = num; held = 0
        if tracking is not None:
            held += 1
            if draws[t] == tracking:
                if t >= start:
                    rounds.append({"result": "hit", "pnl": 47 - held, "held": held})
                tracking = None
            elif held >= K:
                if t >= start:
                    rounds.append({"result": "stop", "pnl": -K, "held": held})
                tracking = None
        d = draws[t]; freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]: maxgap[d] = g
        last_seen[d] = t
        tail_last[te.TAIL[d]] = t; zodiac_last[te.ZODIAC[d]] = t
        element_last[te.ELEMENT[d]] = t; color_last[te.COLOR[d]] = t
    return rounds


# ---- 等额选号（每期买N个最冷号，动态重选）----
def equal_n(draws, N, warmup=100, record_from=None):
    M = len(draws)
    last_seen = {n: -1 for n in range(1, 50)}
    for t in range(min(warmup, M)):
        last_seen[draws[t]] = t
    rounds = []
    start = record_from if record_from is not None else warmup
    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
        coldest = set(sorted(range(1, 50), key=lambda x: gap[x], reverse=True)[:N])
        if t >= start:
            if draws[t] in coldest:
                rounds.append({"result": "hit", "pnl": 47 - N, "held": 1})
            else:
                rounds.append({"result": "stop", "pnl": -N, "held": 1})
        last_seen[draws[t]] = t
    return rounds


# ---- 周期空仓（买N号，K期没出停，等开出再买）----
def cycle(draws, N=1, K=30, warmup=100, record_from=None):
    M = len(draws)
    last_seen = {n: -1 for n in range(1, 50)}
    for t in range(min(warmup, M)):
        last_seen[draws[t]] = t
    state = "BUY"; tracking = set(); held = 0; wait_set = set()
    rounds = []
    start = record_from if record_from is not None else warmup
    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
        if state == "WAIT":
            if draws[t] in wait_set:
                state = "BUY"; wait_set = set(); tracking = set(); held = 0
        else:
            if not tracking:
                tracking = set(sorted(range(1, 50), key=lambda x: gap[x], reverse=True)[:N])
                held = 0
            held += 1
            if draws[t] in tracking:
                if t >= start:
                    rounds.append({"result": "hit", "pnl": 47 - N * held, "held": held})
                tracking = set(); held = 0
            elif held >= K:
                if t >= start:
                    rounds.append({"result": "stop", "pnl": -N * K, "held": held})
                wait_set = set(tracking); tracking = set(); held = 0; state = "WAIT"
        last_seen[draws[t]] = t
    return rounds


# ---- 热号（反向）----
def hot(draws, mode="gap", K=12, warmup=100, record_from=None):
    M = len(draws)
    freq = {n: 0 for n in range(1, 50)}
    last_seen = {n: -1 for n in range(1, 50)}
    for t in range(min(warmup, M)):
        freq[draws[t]] += 1; last_seen[draws[t]] = t
    tracking = None; held = 0
    rounds = []
    start = record_from if record_from is not None else warmup
    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
        if tracking is None:
            if mode == "gap":
                tracking = min(range(1, 50), key=lambda x: gap[x])
            else:
                tracking = max(range(1, 50), key=lambda x: freq[x])
            held = 0
        held += 1
        if draws[t] == tracking:
            if t >= start:
                rounds.append({"result": "hit", "pnl": 47 - held, "held": held})
            tracking = None
        elif held >= K:
            if t >= start:
                rounds.append({"result": "stop", "pnl": -K, "held": held})
            tracking = None
        freq[draws[t]] += 1; last_seen[draws[t]] = t
    return rounds


def breakeven_hold(K, d_bar):
    return K / (47 + K - d_bar) * 100 if d_bar else 0


def main():
    dates, draws = te.load_records()
    half = len(draws) // 2
    print(f"数据 {len(draws)} 期（{dates[0]} ~ {dates[-1]}）| 前段 {half} 期 | 后段 {len(draws)-half} 期\n")

    # 方案清单：(名称, 函数, 参数dict)
    schemes = []
    for K in [3, 6, 12, 18, 24, 30]:
        schemes.append((f"跟踪持有·gap·K={K}", track_hold, dict(signal="gap", theta=10, K=K)))
    schemes.append(("跟踪持有·consensus·K=12", track_hold, dict(signal="consensus", theta=10, mv=4, K=12)))
    schemes.append(("跟踪持有·consensus·K=24", track_hold, dict(signal="consensus", theta=10, mv=4, K=24)))
    schemes.append(("跟踪持有·ratio·K=12", track_hold, dict(signal="ratio", theta=0.8, K=12)))
    for N in [1, 2, 4, 8]:
        schemes.append((f"等额·买最冷{N}号·每期重选", equal_n, dict(N=N)))
    schemes.append(("周期空仓·买1号·K=12", cycle, dict(N=1, K=12)))
    schemes.append(("周期空仓·买1号·K=30", cycle, dict(N=1, K=30)))
    schemes.append(("周期空仓·买8号·K=6", cycle, dict(N=8, K=6)))
    schemes.append(("反向·热号gap·K=12", hot, dict(mode="gap", K=12)))
    schemes.append(("反向·热号freq·K=12", hot, dict(mode="freq", K=12)))

    print(f"{'方案':<26}{'全量轮':>6}{'命中率':>7}{'盈亏平衡':>8}{'单轮期望':>8}{'总盈亏':>8} | {'前段盈亏':>8}{'后段盈亏':>8}")
    print("-" * 100)
    records = []
    for name, fn, kw in schemes:
        full = stat(fn(draws, **kw))
        front = stat(fn(draws[:half], **kw))
        # 后段：用 record_from=half（保留前段 warmup）
        kw_back = dict(kw); kw_back["record_from"] = half
        back = stat(fn(draws, **kw_back))
        K = kw.get("K", 1)
        d_bar = full["d_bar"]
        if "等额" in name:
            be = kw.get("N", 1) / 47 * 100
        elif "周期空仓" in name:
            N = kw.get("N", 1); Kk = kw.get("K", 1)
            be = N * Kk / (47 + N * Kk - N * d_bar) * 100 if d_bar else 0
        else:
            be = breakeven_hold(K, d_bar)
        print(f"{name:<26}{full['n']:>6}{full['rate']:>6.1f}%{be:>7.1f}%{full['mu']:>+8.2f}{full['pnl']:>+8} | {front['pnl']:>+8}{back['pnl']:>+8}")
        records.append({"方案": name, "全量轮数": full["n"], "命中率%": full["rate"],
                        "盈亏平衡%": round(be, 1), "单轮期望": full["mu"], "总盈亏": full["pnl"],
                        "前段盈亏": front["pnl"], "后段盈亏": back["pnl"]})

    import json
    out = os.path.join(os.path.dirname(__file__), "scheme_records.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\n记录已保存: {out}")


if __name__ == "__main__":
    main()
