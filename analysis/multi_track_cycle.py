#!/usr/bin/env python3
"""
「前8最冷号 + 6期周期」策略演算
================================
用户方案：买「前 8 个最冷最长的号」，逻辑：
  - 锁定最冷 8 个号，连续买（每号 1 元，每期 8 元）
  - 6 期内任一命中 → 赚 47 元，重新选 8 个号重算 6 期
  - 6 期全没中 → 停手空仓，等这 8 个号里某个开出 → 再买 6 期

一轮盈亏：命中(第d期)=47-8d；止损(6期没中)=-48
用法：python3 analysis/multi_track_cycle.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def run(draws, N=8, K=6, warmup=100, record_from=None):
    M = len(draws)
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen = {n: -1 for n in range(1, 50)}
    for t in range(min(warmup, M)):
        d = draws[t]
        freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t

    state = "BUY"
    tracking = set()
    held = 0
    wait_set = set()
    rounds = []
    wait_days = 0
    start = record_from if record_from is not None else warmup

    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}

        if state == "WAIT":
            wait_days += 1
            if draws[t] in wait_set:
                state = "BUY"
                wait_set = set()
                tracking = set()
                held = 0
        else:  # BUY
            if not tracking:
                tracking = set(sorted(range(1, 50), key=lambda x: gap[x], reverse=True)[:N])
                held = 0
            held += 1
            if draws[t] in tracking:
                if t >= start:
                    rounds.append({"result": "hit", "pnl": 47 - N * held, "held": held})
                tracking = set()
                held = 0
            elif held >= K:
                if t >= start:
                    rounds.append({"result": "stop", "pnl": -N * K, "held": held})
                wait_set = set(tracking)
                tracking = set()
                held = 0
                state = "WAIT"

        d = draws[t]
        freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t

    return rounds, wait_days


def stat(rounds):
    if not rounds:
        return {"n": 0, "hit": 0, "rate": 0.0, "pnl": 0, "mu": 0.0, "d_bar": 0.0}
    hits = [r for r in rounds if r["result"] == "hit"]
    pnl = sum(r["pnl"] for r in rounds)
    n = len(rounds)
    d_bar = sum(r["held"] for r in hits) / len(hits) if hits else 0
    return {"n": n, "hit": len(hits), "rate": round(len(hits) / n * 100, 2),
            "pnl": pnl, "mu": round(pnl / n, 3), "d_bar": round(d_bar, 2)}


def main():
    dates, draws = te.load_records()
    half = len(draws) // 2
    N, K = 8, 6
    # 随机基线：8个号6期至少一开
    import math
    base = (1 - (41 / 49) ** K) * 100
    print(f"数据 {len(draws)} 期 | 买前{N}最冷号 | K={K}期 | 每期{N}元")
    print(f"随机基线命中率 = {base:.1f}%\n")

    for label, dr, rec in [("全量", draws, None), ("前段(2020-24)", draws[:half], None),
                            ("后段(2024-26)", draws, half)]:
        rounds, wait_days = run(dr, N, K, record_from=rec)
        s = stat(rounds)
        # 盈亏平衡：p*(47-8*d_bar) = (1-p)*48
        win = 47 - N * s["d_bar"] if s["d_bar"] else 0
        be = 48 / (win + 48) * 100 if win else 0
        flag = "🟢" if s["mu"] > 0 else "🔴"
        print(f"{flag} {label}: {s['n']}轮 命中{s['rate']}% 盈亏平衡{be:.1f}% 单轮期望{s['mu']:+.2f} 总盈亏{s['pnl']:+} 空仓{wait_days}天")


if __name__ == "__main__":
    main()
