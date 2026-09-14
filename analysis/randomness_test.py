#!/usr/bin/env python3
"""
开奖数据随机性检验 —— 最后一块拼图
====================================
前面穷尽了「选号信号 × 下注结构 × 参数」全部方案，样本外都不显著。
还差一个方向：验证数据源本身是否真随机（是否存在号码频率物理偏差）。

卡方检验：49 个号码频率是否显著偏离均匀分布。
若显著偏离 → 存在可交易的频率偏差（真实 edge）；若符合均匀 → 数据干净，任何策略都翻不了 −4% 抽水。
用法：python3 analysis/randomness_test.py
"""
import sys, os, math
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def chi2_pvalue(chi2, df):
    """卡方分布上尾概率（近似，df 为自由度）"""
    # 用不完全伽马函数的连分式近似
    def igf(s, x):
        if x < 0:
            return 0
        # 连分式（下不完全伽马函数 / 伽马函数）
        a = s
        gln = math.lgamma(s)
        b = x + 1.0 - s
        c = 1.0 / 1e-30
        d = 1.0 / b
        h = d
        for i in range(1, 200):
            an = -i * (i - s)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            dl = d * c
            h *= dl
            if abs(dl - 1.0) < 1e-12:
                break
        return math.exp(-x + s * math.log(x) - gln) * h

    # 上尾 Q = 1 - P(a/2, x/2)
    return 1.0 - igf(df / 2.0, chi2 / 2.0)


def main():
    dates, draws = te.load_records()
    n = len(draws)
    cnt = Counter(draws)
    expect = n / 49.0

    print(f"数据 {n} 期 ({dates[0]} ~ {dates[-1]})")
    print(f"均匀分布下每号期望出现 {expect:.1f} 次\n")

    # 频率排名
    print("=== 频率最高/最低的号 ===")
    print(f"{'号码':>4}{'出现次数':>8}{'偏离期望':>10}{'z值':>8}")
    rows = []
    sd = math.sqrt(expect * (1 - 1 / 49))
    for num in range(1, 50):
        c = cnt.get(num, 0)
        z = (c - expect) / sd
        rows.append((num, c, z))
    rows.sort(key=lambda x: -x[1])
    for num, c, z in rows[:5] + rows[-5:]:
        flag = "🔴热" if z > 0 else ("🔵冷" if z < 0 else "  ")
        print(f"{num:>4}{c:>8}{c-expect:>+10.1f}{z:>+8.2f}  {flag}")

    # 卡方检验
    chi2 = sum((cnt.get(n_, 0) - expect) ** 2 / expect for n_ in range(1, 50))
    df = 48
    p = chi2_pvalue(chi2, df)
    print(f"\n=== 卡方检验 ===")
    print(f"卡方统计量 χ² = {chi2:.2f}，自由度 = {df}，p 值 = {p:.4f}")

    if p < 0.05:
        print("⚠️ p < 0.05：频率分布显著偏离均匀 → 存在潜在频率偏差（值得深挖）")
    else:
        print("✅ p ≥ 0.05：频率分布符合均匀随机 → 数据干净，无频率偏差可利用")

    # 最大偏差号的可交易性检验
    print(f"\n=== 最热号 vs 最冷号的期望检验 ===")
    hottest = max(range(1, 50), key=lambda x: cnt.get(x, 0))
    coldest = min(range(1, 50), key=lambda x: cnt.get(x, 0))
    for label, num in [("最热号", hottest), ("最冷号", coldest)]:
        c = cnt.get(num, 0)
        rate = c / n * 100
        # 单号命中盈亏平衡 = 1/47 = 2.13%
        print(f"  {label} {num}: 出现 {c} 次，频率 {rate:.2f}% vs 随机 {100/49:.2f}% vs 盈亏平衡 2.13%")


if __name__ == "__main__":
    main()
