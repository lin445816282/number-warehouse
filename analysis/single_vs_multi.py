#!/usr/bin/env python3
"""
「买单个 vs 买多个」盈利对比验证
================================
问题：跟踪持有模型，买 1 个号 vs 买 N 个号，哪个盈利最高？

模型：锁定最冷 k 号（k=1..5，按遗漏降序），每期 1 元跟踪 12 期，
      命中赚 47-d（d=命中延迟），12 期未中亏 12。
      「买 N 个号」= 同时跟踪最冷 N 个号，每号独立同模型。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def track_kth_cold(draws, k, K=12, warmup=100):
    """锁定「第 k 冷号」（按遗漏降序第 k 名），跟踪 K 期。返回 (rounds, wins, pnl, delays)。"""
    M = len(draws)
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen = {n: -1 for n in range(1, 50)}
    # warmup
    for t in range(min(warmup, M)):
        d = draws[t]
        freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t

    rounds = wins = pnl = 0
    delays = []
    tracking = None
    held = 0
    for t in range(warmup, M):
        if tracking is None:
            gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
            ordered = sorted(range(1, 50), key=lambda x: -gap[x])
            tracking = ordered[k - 1]   # 第 k 冷号
            held = 0
        held += 1
        if draws[t] == tracking:
            rounds += 1
            wins += 1
            delays.append(held)
            pnl += (47 - held)
            tracking = None
        elif held >= K:
            rounds += 1
            pnl += (-K)
            tracking = None
        d = draws[t]
        freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t
    return rounds, wins, pnl, delays


def main():
    dates, draws = te.load_records()
    M = len(draws)
    K = 12
    print(f"数据 {M} 期，跟踪 K={K} 期\n")
    print(f"{'冷度排名':<10}{'轮数':>6}{'命中率':>10}{'总盈亏':>10}{'单轮期望':>10}")
    print("-" * 50)
    rows = []
    for k in range(1, 6):
        rounds, wins, pnl, delays = track_kth_cold(draws, k, K)
        rate = wins / rounds * 100 if rounds else 0
        avg = pnl / rounds if rounds else 0
        rows.append((k, rounds, rate, pnl, avg))
        print(f"第{k}冷号{'':<4}{rounds:>6}{rate:>9.1f}%{pnl:>10}{avg:>+10.2f}")

    # 买 N 个号 = 同时跟踪前 N 冷号，总期望 = 各号期望之和（每号独立）
    print("\n「买 N 个号」的每期总投入 = N 元，总期望 = 前 N 冷号单轮期望之和：")
    print(f"{'买 N 个':<10}{'每期投入':>10}{'总单轮期望':>12}{'期望/投入':>12}")
    print("-" * 50)
    for N in range(1, 6):
        total_avg = sum(r[4] for r in rows[:N])
        total_cost = N  # 每期 N 元
        print(f"买 {N} 个{'':<5}{N:>8} 元{total_avg:>+12.2f}{total_avg/total_cost:>+12.3f}")

    print("\n关键：期望/投入（每元投入的期望收益）才是「盈利能力」的正确口径。")


if __name__ == "__main__":
    main()
