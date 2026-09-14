#!/usr/bin/env python3
"""
反向跟踪验证 —— 冷号回补失效后，反向买热号能否提升？
====================================================
逐一验证（全量 / 前段样本外 / 后段）：
  1. 冷号(正向)：买最冷号 gap 最大，跟踪 K 期
  2. 热号 gap(反向)：买最近开出号 gap 最小
  3. 热号 freq(反向)：买历史出现频率最高号
  4. 连续止损 N 轮后反向：cold → hot_gap 切换（N 扫描）
用法：python3 analysis/reverse_tracking.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def run(draws, mode="cold", K=12, switch_after=0, warmup=100, record_from=None):
    """
    mode: 'cold' / 'hot_gap' / 'hot_freq'
    switch_after: 连续止损 N 轮后从 cold 切换到 hot_gap（0=禁用切换）
    """
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

    rounds = []
    tracking = None
    held = 0
    consec_stops = 0
    switched = False
    cur_mode = mode
    start = record_from if record_from is not None else warmup

    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}

        if tracking is None:
            # 切换判定：连续止损 N 轮后反向
            if switch_after and not switched and consec_stops >= switch_after:
                cur_mode = "hot_gap"
                switched = True
            # 选号
            if cur_mode == "cold":
                num = max(range(1, 50), key=lambda x: gap[x])
            elif cur_mode == "hot_gap":
                num = min(range(1, 50), key=lambda x: gap[x])
            else:  # hot_freq
                num = max(range(1, 50), key=lambda x: freq[x])
            tracking = num
            held = 0

        if tracking is not None:
            held += 1
            if draws[t] == tracking:
                if t >= start:
                    rounds.append({"result": "hit", "pnl": 47 - held, "held": held, "num": tracking})
                consec_stops = 0
                tracking = None
            elif held >= K:
                if t >= start:
                    rounds.append({"result": "stop", "pnl": -K, "held": held, "num": tracking})
                consec_stops += 1
                tracking = None

        d = draws[t]
        freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t

    return rounds


def stat(rounds):
    if not rounds:
        return {"n": 0, "hit": 0, "rate": 0.0, "pnl": 0, "mu": 0.0}
    hits = sum(1 for r in rounds if r["result"] == "hit")
    pnl = sum(r["pnl"] for r in rounds)
    n = len(rounds)
    return {"n": n, "hit": hits, "rate": round(hits / n * 100, 2), "pnl": pnl, "mu": round(pnl / n, 3)}


def report(draws, half, mode, K, switch_after):
    full = stat(run(draws, mode, K, switch_after))
    front = stat(run(draws[:half], mode, K, switch_after))
    back = stat(run(draws, mode, K, switch_after, record_from=half))
    tag = "🟢" if full["mu"] > 0 and front["mu"] > 0 else ("🟡" if full["mu"] > 0 else "🔴")
    print(f"  {tag} 全量 {full['n']:>3}轮 命中{full['rate']:>5}% 期望{full['mu']:>+7.3f} 盈亏{full['pnl']:>+6} | "
          f"前段 {front['n']:>3}轮 {front['rate']:>5}% 期望{front['mu']:>+7.3f} 盈亏{front['pnl']:>+6} | "
          f"后段 {back['n']:>3}轮 {back['rate']:>5}% 盈亏{back['pnl']:>+6}")


def main():
    dates, draws = te.load_records()
    half = len(draws) // 2
    K = 12
    print(f"数据 {len(draws)} 期 | 前段(2020-24) {half}期 | 后段(2024-26) {len(draws)-half}期 | K={K}\n")

    print("【1】冷号 正向（买最冷号 gap 最大）—— 基准")
    report(draws, half, "cold", K, 0)

    print("\n【2】热号 gap 反向（买最近开出号）")
    report(draws, half, "hot_gap", K, 0)

    print("\n【3】热号 freq 反向（买历史频率最高号）")
    report(draws, half, "hot_freq", K, 0)

    print("\n【4】连续止损 N 轮后反向（cold → hot_gap 切换）")
    for N in [3, 5, 8, 10]:
        print(f"  --- 切换阈值 N={N} ---")
        report(draws, half, "cold", K, N)


if __name__ == "__main__":
    main()
