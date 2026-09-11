#!/usr/bin/env python3
"""
冷度排名 1~16 号盈利全景 + 分组对比
====================================
回答：第 8~16 冷号是否也盈利？对比「只买第 1 冷号」的盈利情况。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def track_kth_cold(draws, k, K=12, warmup=100):
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
    rounds = wins = pnl = 0
    tracking = None
    held = 0
    for t in range(warmup, M):
        if tracking is None:
            gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
            ordered = sorted(range(1, 50), key=lambda x: -gap[x])
            tracking = ordered[k - 1]
            held = 0
        held += 1
        if draws[t] == tracking:
            rounds += 1
            wins += 1
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
    return rounds, wins, pnl


def main():
    dates, draws = te.load_records()
    K = 12
    print(f"数据 {len(draws)} 期，跟踪 K={K} 期\n")
    print(f"{'冷度排名':<10}{'轮数':>6}{'命中率':>9}{'单轮期望':>10}  状态")
    print("-" * 52)
    rows = []
    for k in range(1, 17):
        rounds, wins, pnl = track_kth_cold(draws, k, K)
        rate = wins / rounds * 100 if rounds else 0
        avg = pnl / rounds if rounds else 0
        flag = "🟢 盈利" if avg > 0 else ("🔴 亏损" if avg < 0 else "⚪ 打平")
        rows.append((k, rounds, rate, avg))
        print(f"第{k:>2}冷号{'':<3}{rounds:>6}{rate:>8.1f}%{avg:>+10.2f}  {flag}")

    # 分组汇总
    def seg(a, b):
        s = sum(r[3] for r in rows[a-1:b])
        n = b - a + 1
        return s, n

    print("\n=== 分组对比（每元投入期望 = 盈利能力）===")
    print(f"{'方案':<16}{'每期投入':>8}{'总单轮期望':>12}{'每元期望':>10}")
    print("-" * 52)
    only1 = rows[0][3]
    print(f"只买第1冷号{'':<5}{'1 元':>8}{only1:>+12.2f}{only1:>+10.3f}")
    for a, b in [(2, 4), (5, 7), (8, 10), (11, 13), (14, 16)]:
        s, n = seg(a, b)
        print(f"买第{a}~{b}冷号{'':<5}{f'{n} 元':>8}{s:>+12.2f}{s/n:>+10.3f}")
    s_8_16, n = seg(8, 16)
    print("-" * 52)
    print(f"第8~16冷号合计（9个号）每元期望：{s_8_16/n:+.3f}  总期望 {s_8_16:+.2f}")


if __name__ == "__main__":
    main()
