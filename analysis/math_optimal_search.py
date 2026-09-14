#!/usr/bin/env python3
"""
数学最优方案穷尽搜索
====================
穷尽「信号 × 阈值 × 跟踪期数 K × 下注结构」全部组合，用真样本外(前段2020-2024)筛选稳健方案。
关键判据：前段(样本外)命中率必须超过随机基线 + z 显著性，才是「真信号」而非「后段过拟合」。

输出：
1. 前段也正期望的稳健方案（若有）→ 排名
2. 全量最优 vs 前段最优 的对比
用法：python3 analysis/math_optimal_search.py
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def zscore(hits, n, p0):
    """命中率 vs 随机基线 p0 的二项显著性 z 值"""
    if n <= 0 or p0 <= 0 or p0 >= 1:
        return 0.0
    p_hat = hits / n
    se = math.sqrt(p0 * (1 - p0) / n)
    return (p_hat - p0) / se if se > 0 else 0.0


def main():
    dates, draws = te.load_records()
    half = len(draws) // 2
    print(f"数据 {len(draws)} 期 | 前段(训练) {half} 期 | 后段(测试) {len(draws)-half} 期\n")

    # 信号配置：(signal, theta, min_votes)
    sigs = []
    for th in [10, 30, 50, 100, 150, 180]:
        sigs.append(("gap", th, 4))
    for th in [0.3, 0.5, 0.7, 0.9]:
        sigs.append(("ratio", th, 4))
    for mv in [2, 3, 4, 5, 6, 7]:
        sigs.append(("consensus", 10, mv))

    Ks = [3, 6, 9, 12, 18, 24, 30, 40]

    rows = []
    for signal, theta, mv in sigs:
        for K in Ks:
            # 全量
            full = te.run_tracking_hold(draws, theta=theta, K=K, signal=signal, min_votes=mv)
            # 前段（样本外训练）：重新 warmup
            front = te.run_tracking_hold(draws[:half], theta=theta, K=K, signal=signal, min_votes=mv)
            # 后段（样本外测试）：保留前段历史 warmup
            back = te.run_tracking_hold(draws, theta=theta, K=K, signal=signal, min_votes=mv, start_period=half)

            fr = front["rounds"]; br = back["rounds"]; fl = full["rounds"]
            front_hits = front["wins"]; back_hits = back["wins"]; full_hits = full["wins"]
            p0 = full["baseline"] / 100  # 随机基线命中率

            z_full = zscore(full_hits, fl, p0)
            z_front = zscore(front_hits, fr, p0)
            z_back = zscore(back_hits, br, p0)

            rows.append({
                "signal": signal, "theta": theta, "K": K,
                "full_rounds": fl, "full_rate": full["win_rate"], "full_pnl": full["total_pnl"], "full_mu": full["avg_pnl"],
                "front_rounds": fr, "front_rate": front["win_rate"], "front_pnl": front["total_pnl"], "front_mu": front["avg_pnl"],
                "back_rounds": br, "back_rate": back["win_rate"], "back_pnl": back["total_pnl"],
                "z_full": z_full, "z_front": z_front, "z_back": z_back,
                "baseline": full["baseline"],
            })

    # 筛选：前段(样本外)也正期望的稳健方案
    robust = [r for r in rows if r["front_mu"] > 0]
    robust.sort(key=lambda r: -(r["front_mu"] + r["full_mu"]))

    print("=" * 90)
    print(f"穷尽 {len(rows)} 个组合。其中【前段(样本外)也正期望】的稳健方案：{len(robust)} 个")
    print("=" * 90)
    if robust:
        print(f"{'信号':<10}{'阈值':>6}{'K':>4}{'前段命中':>9}{'前段期望':>9}{'全量命中':>9}{'全量期望':>9}{'前段z':>7}{'全量z':>7}")
        for r in robust[:30]:
            print(f"{r['signal']:<10}{r['theta']:>6}{r['K']:>4}{r['front_rate']:>8.1f}%{r['front_mu']:>+9.2f}"
                  f"{r['full_rate']:>8.1f}%{r['full_mu']:>+9.2f}{r['z_front']:>+7.2f}{r['z_full']:>+7.2f}")
    else:
        print("（无）—— 没有任何组合在前段(2020-2024)样本外正期望")

    print("\n" + "=" * 90)
    print("全量期望 TOP 15（但不看样本外，可能是过拟合）：")
    print("=" * 90)
    top = sorted(rows, key=lambda r: -r["full_mu"])[:15]
    print(f"{'信号':<10}{'阈值':>6}{'K':>4}{'全量命中':>9}{'全量期望':>9}{'前段期望':>9}{'前段z':>7}")
    for r in top:
        print(f"{r['signal']:<10}{r['theta']:>6}{r['K']:>4}{r['full_rate']:>8.1f}%{r['full_mu']:>+9.2f}"
              f"{r['front_mu']:>+9.2f}{r['z_front']:>+7.2f}")

    # 显著性统计
    sig_full = [r for r in rows if r["z_full"] > 1.96]
    sig_front = [r for r in rows if r["z_front"] > 1.96]
    print(f"\n全量 z>1.96(显著) 的组合：{len(sig_full)} 个；前段 z>1.96(显著) 的组合：{len(sig_front)} 个")


if __name__ == "__main__":
    main()
