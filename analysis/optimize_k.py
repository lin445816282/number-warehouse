#!/usr/bin/env python3
"""
跟踪持有「跟踪期数 K」优化扫描
==============================
问题：当前固定 K=12，是否存在更优 K 使期望翻正/最大化？
方法：扫描 K=1~40，对每个 K 跑 tracking_hold_rounds（walk-forward 无未来函数），
      算命中率/盈亏平衡线/单轮期望/总盈亏/最长连亏/最大回撤，并做前段/后段样本外。

用法：python3 analysis/optimize_k.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def scan(draws, signal, min_votes, label, K_range=range(3, 41)):
    print(f"\n===== 信号 {signal} | {label} =====")
    print(f"{'K':>3} {'轮数':>6} {'命中率':>8} {'盈亏平衡':>8} {'单轮期望':>9} {'总盈亏':>8} {'最长连亏':>8} {'最大回撤':>8}")
    best = None
    for K in K_range:
        rounds = te.tracking_hold_rounds(draws, K=K, signal=signal, min_votes=min_votes)
        if not rounds:
            continue
        m = te.tracking_hold_metrics(rounds, K)
        res = te.run_tracking_hold(draws, K=K, signal=signal, min_votes=min_votes)
        hit_rate = sum(1 for r in rounds if r["result"] == "hit") / len(rounds) * 100
        mu = sum(r["pnl"] for r in rounds) / len(rounds)
        total = sum(r["pnl"] for r in rounds)
        be = m["breakeven"]
        flag = "✅" if mu > 0 else ""
        print(f"{K:>3} {len(rounds):>6} {hit_rate:>7.1f}% {be:>7.1f}% {mu:>+9.2f} {total:>+8} {m['max_loss_streak']:>8} {res['max_drawdown']:>8}  {flag}")
        if best is None or mu > best[1]:
            best = (K, mu, hit_rate, total, m["max_loss_streak"], res["max_drawdown"])
    print(f"  >> 最优 K={best[0]}  单轮期望={best[1]:+.2f}  命中率={best[2]:.1f}%  总盈亏={best[3]:+}  最长连亏={best[4]}  最大回撤={best[5]}")
    return best


def main():
    dates, draws = te.load_records()
    half = len(draws) // 2
    print(f"数据 {len(draws)} 期 ({dates[0]} ~ {dates[-1]})")
    print(f"前段(训练) {half} 期 | 后段(测试) {len(draws)-half} 期")

    for sig in ["consensus", "gap", "ratio"]:
        scan(draws, sig, 4, "全量")
        scan(draws[:half], sig, 4, "前段 2020-2024")
        scan(draws, sig, 4, "后段 2024-2026(完整历史warmup)")


if __name__ == "__main__":
    main()
