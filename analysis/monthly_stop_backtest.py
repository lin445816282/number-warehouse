#!/usr/bin/env python3
"""
按月约束回测 —— 买最冷1号(跟踪持有) + 月度止损
==============================================
验证：月度亏损达阈值就停手（下月恢复），能否避免大亏、保住盈利。
方案：gap 信号（买最冷号），K=12 跟踪，每期 1 元。
用法：python3 analysis/monthly_stop_backtest.py
"""
import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def backtest(draws, dates, K=12, limit=50, warmup=100):
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

    monthly = defaultdict(float)  # month -> pnl
    stopped_months = []            # 触发停手的月份
    cur_month = None
    stopped = False
    tracking = None
    held = 0

    for t in range(warmup, M):
        month = dates[t][:7]
        if month != cur_month:
            cur_month = month
            monthly[cur_month] = 0.0
            stopped = False

        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}

        # 本月已停手 → 只更新统计，不下注
        if stopped:
            d = draws[t]
            freq[d] += 1
            if last_seen[d] >= 0:
                g = t - last_seen[d] - 1
                if g > maxgap[d]:
                    maxgap[d] = g
            last_seen[d] = t
            continue

        if tracking is None:
            num = max(range(1, 50), key=lambda x: gap[x])
            tracking = num
            held = 0

        held += 1
        if draws[t] == tracking:
            pnl = 47 - held
            monthly[cur_month] += pnl
            tracking = None
        elif held >= K:
            pnl = -K
            monthly[cur_month] += pnl
            tracking = None
            if monthly[cur_month] <= -limit:
                stopped = True
                stopped_months.append(cur_month)

        d = draws[t]
        freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t

    return monthly, stopped_months


def main():
    dates, draws = te.load_records()
    print(f"数据 {len(draws)} 期 ({dates[0]} ~ {dates[-1]}) | gap 信号 K=12 每期1元\n")

    # 无约束基准
    base_monthly, _ = backtest(draws, dates, K=12, limit=999999)
    base_total = sum(base_monthly.values())
    base_worst = min(base_monthly.values())
    print(f"【无约束基准】总盈亏 {base_total:+.0f} | 最差单月 {base_worst:+.0f}")
    print()

    print(f"{'月度止损':>8} | {'总盈亏':>8} {'最差单月':>8} {'盈利月':>5} {'亏损月':>5} {'停手月数':>6}")
    print("-" * 56)
    for limit in [20, 30, 50, 80, 120, 200]:
        monthly, stopped = backtest(draws, dates, K=12, limit=limit)
        total = sum(monthly.values())
        worst = min(monthly.values()) if monthly else 0
        win_m = sum(1 for v in monthly.values() if v > 0)
        loss_m = sum(1 for v in monthly.values() if v < 0)
        print(f"{limit:>8} | {total:>+8.0f} {worst:>+8.0f} {win_m:>5} {loss_m:>5} {len(stopped):>6}")

    # 推荐阈值：按月明细
    print("\n=== 月度止损 50 元的逐月明细（后段 2023-03 起）===")
    monthly, stopped = backtest(draws, dates, K=12, limit=50)
    for m in sorted(monthly.keys()):
        if m >= "2023-03":
            mark = "⛔停手" if m in stopped else ""
            bar = "█" * max(0, int(monthly[m] / 5)) if monthly[m] > 0 else "░" * max(1, int(-monthly[m] / 10))
            print(f"  {m}: {monthly[m]:>+7.0f}  {bar} {mark}")


if __name__ == "__main__":
    main()
