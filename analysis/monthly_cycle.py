#!/usr/bin/env python3
"""
「30天周期」策略演算
====================
用户方案：买最冷号，按月 30 天连续买；30 天没出就停手空仓，等这个号开出后再买 30 天，循环。

状态机：
  BUY（买）：锁定最冷号，连续买，命中赚 47-d；买满 30 天没出 → 亏 30 元，进 WAIT
  WAIT（停）：空仓等该号开出 → 开出后回 BUY 重新选最冷号

用法：python3 analysis/monthly_cycle.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def run_cycle(draws, K=30, warmup=100, record_from=None):
    """30天周期策略 walk-forward"""
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
    tracking = None
    held = 0
    wait_num = None
    rounds = []
    wait_days = 0  # 空仓总天数
    start = record_from if record_from is not None else warmup

    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}

        if state == "WAIT":
            wait_days += 1
            if draws[t] == wait_num:
                state = "BUY"
                wait_num = None
                tracking = None
                held = 0
        else:  # BUY
            if tracking is None:
                tracking = max(range(1, 50), key=lambda x: gap[x])
                held = 0
            held += 1
            if draws[t] == tracking:
                if t >= start:
                    rounds.append({"result": "hit", "pnl": 47 - held, "held": held, "num": tracking})
                tracking = None
            elif held >= K:
                if t >= start:
                    rounds.append({"result": "stop", "pnl": -K, "held": held, "num": tracking})
                wait_num = tracking
                tracking = None
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
    K = 30
    print(f"数据 {len(draws)} 期 | K=30 天 | 每期 1 元\n")

    for label, dr, rec in [("全量", draws, None), ("前段(2020-24)", draws[:half], None),
                            ("后段(2024-26)", draws, half)]:
        rounds, wait_days = run_cycle(dr, K, record_from=rec)
        s = stat(rounds)
        # 盈亏平衡线 p = K/(47+K-d_bar)
        be = K / (47 + K - s["d_bar"]) * 100 if s["d_bar"] else 0
        flag = "🟢" if s["mu"] > 0 else "🔴"
        print(f"{flag} {label}: {s['n']}轮 命中{s['rate']}% 盈亏平衡{be:.1f}% 单轮期望{s['mu']:+.2f} 总盈亏{s['pnl']:+} 空仓{wait_days}天")

    # 对比：跟踪持有 K=30（无空仓等待）
    print("\n对比：跟踪持有 K=30（无空仓，止损立即重选）")
    for label, dr, rec in [("全量", draws, None), ("前段(2020-24)", draws[:half], None)]:
        rounds, _ = run_cycle(dr, K, record_from=rec)  # 复用，但需无空仓版
    # 直接调 tracking_engine 的 run_tracking_hold
    for label, dr in [("全量", draws), ("前段", draws[:half])]:
        res = te.run_tracking_hold(dr, theta=10, K=K, signal="gap", min_votes=4)
        print(f"  {label}: {res['rounds']}轮 命中{res['win_rate']:.1f}% 总盈亏{res['total_pnl']:+}")


if __name__ == "__main__":
    main()
