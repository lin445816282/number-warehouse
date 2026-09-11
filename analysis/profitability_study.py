#!/usr/bin/env python3
"""
「持续盈利」可行性研究 — 数据推演脚本
======================================
核心问题：在 47 赔率 < 49 号码 的规则下，跟踪持有模型能否「持续盈利」？

回答方式（穷尽数学方案，不做判决）：
  1. 精确盈亏平衡门槛（不是简单 N/47，而是跟踪结构的 breakeven 命中率）
  2. 期望 / 标准差 / 凯利最优仓位
  3. 最长连亏、最大回撤（资金管理视角）
  4. 样本外（前段/后段）+ 滚动窗口稳定性
  5. 结构突变（2026-05）前后的表现对比

复用 tracking_engine.tracking_hold_rounds 逐轮明细。
"""
import sys, os, json, math
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te

OUT_JSON = os.path.join(os.path.dirname(__file__), "profitability_result.json")
OUT_MD   = os.path.join(os.path.dirname(__file__), "profitability_report.md")


def run_rounds(draws, warmup=100, theta=10, K=12, signal="consensus", min_votes=4):
    """直接调用 tracking_hold_rounds 拿逐轮明细。"""
    return te.tracking_hold_rounds(draws, theta=theta, K=K, warmup=warmup,
                                   signal=signal, min_votes=min_votes)


def compute_breakeven(rounds, K):
    """跟踪持有模型的精确盈亏平衡命中率。

    单轮：命中 → 赚 (47 - d)（d=命中延迟）；止损 → 亏 K。
    E = p*(47 - d_bar) + (1-p)*(-K) = 0
    => p_breakeven = K / (47 + K - d_bar)
    """
    hits = [r for r in rounds if r["result"] == "hit"]
    stops = [r for r in rounds if r["result"] == "stop"]
    if not hits:
        return None
    d_bar = sum(r["held"] for r in hits) / len(hits)
    p_breakeven = K / (47 + K - d_bar)
    return {"d_bar": round(d_bar, 2), "p_breakeven": round(p_breakeven * 100, 2)}


def compute_stats(rounds, K):
    """单轮盈亏分布统计 + 凯利仓位。"""
    if not rounds:
        return None
    pnls = [r["pnl"] for r in rounds]
    n = len(pnls)
    mu = sum(pnls) / n
    var = sum((x - mu) ** 2 for x in pnls) / n
    sigma = math.sqrt(var)
    hits = [r for r in rounds if r["result"] == "hit"]
    stops = [r for r in rounds if r["result"] == "stop"]
    p_hit = len(hits) / n

    # 凯利仓位（单轮最大投入 = K，回报率口径）
    # 回报率 r = pnl / K（投入以最大 K 计，保守）
    r_mu = mu / K
    r_var = var / (K * K)
    kelly = r_mu / r_var if r_var > 0 else 0

    # 最长连亏
    max_loss_streak = cur = 0
    for r in rounds:
        if r["pnl"] < 0:
            cur += 1
            max_loss_streak = max(max_loss_streak, cur)
        else:
            cur = 0

    # 最大回撤（等额累计）
    eq = 0
    peak = 0
    max_dd = 0
    for r in rounds:
        eq += r["pnl"]
        peak = max(peak, eq)
        max_dd = min(max_dd, eq - peak)

    # 命中延迟分布
    delay_dist = {}
    for r in hits:
        delay_dist[r["held"]] = delay_dist.get(r["held"], 0) + 1

    return {
        "rounds": n, "hits": len(hits), "stops": len(stops),
        "p_hit": round(p_hit * 100, 2),
        "mu": round(mu, 3), "sigma": round(sigma, 2),
        "sharpe_like": round(mu / sigma, 3) if sigma > 0 else None,
        "kelly": round(kelly, 4),
        "max_loss_streak": max_loss_streak,
        "max_drawdown": max_dd,
        "total_pnl": sum(pnls),
        "delay_dist": {str(k): v for k, v in sorted(delay_dist.items())},
    }


def split_rounds(rounds, M, warmup):
    """按进场时间切前段/后段/结构突变前后。"""
    half = M // 2
    # 结构突变点：2026-05 对应的期号需从数据反推
    front = [r for r in rounds if r["enter_idx"] < half]
    back = [r for r in rounds if r["enter_idx"] >= half]
    return front, back


def main():
    dates, draws = te.load_records()
    M = len(draws)
    print(f"数据：{M} 期 ({dates[0]} ~ {dates[-1]})")

    K = 12
    signals = [
        ("consensus_mv4", dict(signal="consensus", min_votes=4)),
        ("ratio_t10", dict(signal="ratio", theta=10)),
        ("gap_t10", dict(signal="gap", theta=10)),
    ]

    result = {"n_draws": M, "K": K, "signals": {}}
    report = []
    report.append("# 「持续盈利」可行性研究")
    report.append("")
    report.append(f"> 生成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 数据 {M} 期 ({dates[0]} ~ {dates[-1]}) · 跟踪 K={K} 期")
    report.append("")
    report.append("## 一、盈亏平衡门槛（跟踪持有结构）")
    report.append("")
    report.append("跟踪持有单轮：命中赚 `47-d`（d=命中延迟），止损亏 `K`。")
    report.append("盈亏平衡命中率 `p = K/(47+K-d̄)`，其中 d̄ = 平均命中延迟。")
    report.append("")
    report.append("| 信号 | 平均命中延迟 d̄ | 盈亏平衡命中率 | 实际命中率 | 判定 |")
    report.append("|---|---|---|---|---|")

    for name, kw in signals:
        rounds = run_rounds(draws, K=K, **kw)
        be = compute_breakeven(rounds, K)
        stats = compute_stats(rounds, K)
        if not be or not stats:
            continue
        base = (1 - (48 / 49) ** K) * 100
        actual = stats["p_hit"]
        verdict = "✅ 越过门槛" if actual > be["p_breakeven"] else "❌ 未越门槛"
        report.append(f"| {name} | {be['d_bar']} | {be['p_breakeven']}% | {actual}% (基线 {base:.1f}%) | {verdict} |")
        result["signals"][name] = {
            "breakeven": be, "stats": stats,
            "base": round(base, 2),
        }
        print(f"  {name}: d̄={be['d_bar']} 盈亏平衡={be['p_breakeven']}% 实际={actual}% 期望={stats['mu']} 凯利={stats['kelly']} 连亏={stats['max_loss_streak']} 回撤={stats['max_drawdown']}")

    report.append("")
    report.append("## 二、期望 / 波动 / 凯利仓位 / 连亏")
    report.append("")
    report.append("| 信号 | 轮数 | 命中率 | 单轮期望 | 单轮σ | 期望/σ | 凯利仓位 | 最长连亏 | 最大回撤 | 总盈亏 |")
    report.append("|---|---|---|---|---|---|---|---|---|---|")
    for name, kw in signals:
        rounds = run_rounds(draws, K=K, **kw)
        stats = compute_stats(rounds, K)
        if not stats:
            continue
        report.append(f"| {name} | {stats['rounds']} | {stats['p_hit']}% | {stats['mu']} | {stats['sigma']} | {stats['sharpe_like']} | {stats['kelly']} | {stats['max_loss_streak']} | {stats['max_drawdown']} | {stats['total_pnl']} |")
    report.append("")
    report.append("> 凯利仓位 = 单轮回报率期望 / 方差。>0 表示有正期望，数值越大可下注比例越高；<0 表示负期望不该下注。")
    report.append("")

    # 命中延迟分布
    report.append("## 三、命中延迟分布（命中时已投入几期）")
    report.append("")
    for name, kw in signals:
        rounds = run_rounds(draws, K=K, **kw)
        stats = compute_stats(rounds, K)
        if not stats:
            continue
        dist = stats["delay_dist"]
        report.append(f"**{name}**：`" + ", ".join(f"d={k}:{v}轮" for k, v in dist.items()) + "`")
    report.append("")

    # 样本外
    report.append("## 四、样本外稳定性（前段 vs 后段）")
    report.append("")
    report.append("| 信号 | 前段轮数 | 前段命中率 | 前段盈亏 | 后段轮数 | 后段命中率 | 后段盈亏 |")
    report.append("|---|---|---|---|---|---|---|")
    half = M // 2
    oos_data = {}
    for name, kw in signals:
        rounds = run_rounds(draws, K=K, **kw)
        front = [r for r in rounds if r["enter_idx"] < half]
        back = [r for r in rounds if r["enter_idx"] >= half]
        f_rate = sum(1 for r in front if r["result"] == "hit") / len(front) * 100 if front else 0
        b_rate = sum(1 for r in back if r["result"] == "hit") / len(back) * 100 if back else 0
        f_pnl = sum(r["pnl"] for r in front)
        b_pnl = sum(r["pnl"] for r in back)
        fflag = "🟢" if f_pnl > 0 else "🔴"
        bflag = "🟢" if b_pnl > 0 else "🔴"
        report.append(f"| {name} | {len(front)} | {f_rate:.1f}% | {f_pnl} {fflag} | {len(back)} | {b_rate:.1f}% | {b_pnl} {bflag} |")
        oos_data[name] = {"front": {"rounds": len(front), "rate": round(f_rate, 2), "pnl": f_pnl},
                          "back": {"rounds": len(back), "rate": round(b_rate, 2), "pnl": b_pnl}}
    report.append("")
    result["oos"] = oos_data

    # 滚动窗口
    report.append("## 五、滚动窗口（每 200 期，窗宽 400，consensus_mv4）")
    report.append("")
    rounds = run_rounds(draws, K=K, signal="consensus", min_votes=4)
    report.append("| 窗口(进场期号) | 轮数 | 命中率 | 盈亏 |")
    report.append("|---|---|---|---|")
    rolling = []
    for start in range(100, M - 400, 200):
        seg = [r for r in rounds if start <= r["enter_idx"] < start + 400]
        if not seg:
            continue
        rate = sum(1 for r in seg if r["result"] == "hit") / len(seg) * 100
        pnl = sum(r["pnl"] for r in seg)
        flag = "🟢" if pnl > 0 else "🔴"
        report.append(f"| {start}~{start+400} | {len(seg)} | {rate:.1f}% | {pnl} {flag} |")
        rolling.append({"start": start, "rounds": len(seg), "rate": round(rate, 2), "pnl": pnl})
    report.append("")
    result["rolling"] = rolling

    # 结构突变前后（2026-05 附近）
    report.append("## 六、2026-05 结构突变前后（consensus_mv4）")
    report.append("")
    # 找 2026-05 对应的期号
    mut_idx = None
    for i, d in enumerate(dates):
        if d >= "2026-05-01":
            mut_idx = i
            break
    if mut_idx:
        pre = [r for r in rounds if r["enter_idx"] < mut_idx]
        post = [r for r in rounds if r["enter_idx"] >= mut_idx]
        pre_rate = sum(1 for r in pre if r["result"] == "hit") / len(pre) * 100 if pre else 0
        post_rate = sum(1 for r in post if r["result"] == "hit") / len(post) * 100 if post else 0
        report.append(f"| 时段 | 轮数 | 命中率 | 盈亏 |")
        report.append(f"|---|---|---|---|")
        report.append(f"| 2026-05 前 | {len(pre)} | {pre_rate:.1f}% | {sum(r['pnl'] for r in pre)} |")
        report.append(f"| 2026-05 后 | {len(post)} | {post_rate:.1f}% | {sum(r['pnl'] for r in post)} |")
        report.append("")
        result["mutation"] = {"idx": mut_idx, "pre": {"rounds": len(pre), "rate": round(pre_rate, 2), "pnl": sum(r['pnl'] for r in pre)},
                              "post": {"rounds": len(post), "rate": round(post_rate, 2), "pnl": sum(r['pnl'] for r in post)}}

    report.append("## 七、结论（诚实 + 务实路径）")
    report.append("")
    report.append("（由下方主逻辑填充）")
    report.append("")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\n已输出：{OUT_JSON} / {OUT_MD}")


if __name__ == "__main__":
    main()
