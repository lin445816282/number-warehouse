#!/usr/bin/env python3
"""
尾数预测信号分析脚本 — 全量数据验证各维度是否存在可预测信号
数据源：backend/data/warehouse.db 的 records 表
可重复运行：python3 analysis/tail_signal_analysis.py

结论摘要（2026-09-09，2366 期，2020-03-18 ~ 2026-09-08）：
  1. 两分类(0-4/5-9)、具体尾数(0-9)、单双 全部接近真随机
  2. "连续越长越容易反转"(均值回归) 假设不成立，反转概率恒 ~50%
  3. 唯一略超基线的微弱信号：号码遗漏 >150 期，命中率 2.36%~2.55% vs 随机 2.04%
"""
import sqlite3
import os
from collections import Counter, defaultdict

DB = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "warehouse.db")


def load():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT date, draw_number FROM records ORDER BY date").fetchall()
    db.close()
    return rows


def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main():
    rows = load()
    n = len(rows)
    print(f"总记录数: {n}  ({rows[0]['date']} ~ {rows[-1]['date']})")

    tails = [r["draw_number"] % 10 for r in rows]
    nums = [r["draw_number"] for r in rows]

    def grp(x):
        return "0-4" if x <= 4 else "5-9"
    groups = [grp(t) for t in tails]

    # 1. 两分类占比
    section("1. 两分类占比")
    n04 = groups.count("0-4"); n59 = groups.count("5-9")
    print(f"  0-4尾: {n04} ({n04/n*100:.1f}%)  5-9尾: {n59} ({n59/n*100:.1f}%)")

    # 2. 具体尾数频率
    section("2. 具体尾数(0-9)频率")
    freq = Counter(tails)
    for t in range(10):
        c = freq.get(t, 0)
        print(f"  尾{t}: {c:4d}次 ({c/n*100:5.1f}%)")

    # 3. 马尔可夫转移：连续k天 → 下期延续/反转
    section("3. 马尔可夫转移 (连续k天后下期延续概率)")
    for target in ["0-4", "5-9"]:
        print(f"  [{target}尾]")
        for k in range(1, 9):
            cont = rev = 0
            for i in range(k, n):
                if all(groups[j] == target for j in range(i - k, i)):
                    if groups[i] == target:
                        cont += 1
                    else:
                        rev += 1
            if cont + rev > 0:
                print(f"    连续{k}天: 延续{cont} 反转{rev} → 延续 {cont/(cont+rev)*100:.0f}%")

    # 4. 遗漏均值回归
    section("4. 遗漏均值回归检验")

    def gap_regression(seq, universe, k):
        hit = tot = 0
        for x in universe:
            gap = 0
            for i in range(n - 1):
                if seq[i] == x:
                    gap = 0
                else:
                    gap += 1
                    if gap >= k:
                        tot += 1
                        if seq[i + 1] == x:
                            hit += 1
        return hit, tot

    print("  [尾数, 理论基线 10%]")
    for k in [5, 8, 10, 12, 15, 20]:
        h, t = gap_regression(tails, range(10), k)
        if t:
            print(f"    遗漏>={k}期后命中: {h}/{t} = {h/t*100:.1f}%")
    print("  [号码1-49, 理论基线 2.04%]")
    for k in [30, 50, 80, 100, 120, 150, 178]:
        h, t = gap_regression(nums, range(1, 50), k)
        if t:
            print(f"    遗漏>={k}期后命中: {h}/{t} = {h/t*100:.2f}%")

    # 5. 热尾延续
    section("5. 近30期热尾延续 (理论 30%)")
    hot_hit = hot_tot = 0
    for i in range(30, n):
        c = Counter(tails[i - 30:i])
        top3 = {x for x, _ in c.most_common(3)}
        if tails[i] in top3:
            hot_hit += 1
        hot_tot += 1
    print(f"  近30期TOP3热尾下期命中: {hot_hit/hot_tot*100:.1f}%")

    # 6. 单双
    section("6. 单双占比")
    odd = sum(1 for t in tails if t % 2 == 1)
    print(f"  单: {odd} ({odd/n*100:.1f}%)  双: {n-odd} ({(n-odd)/n*100:.1f}%)")

    # 7. 策略回测
    section("7. 策略回测 (两分类随机基线 50%)")

    def add_strategy(name, preds):
        hits = sum(1 for i in range(1, n) if preds[i] == groups[i])
        print(f"  {name}: {hits/(n-1)*100:.2f}% ({hits}/{n-1})")

    add_strategy("始终猜0-4尾", ["0-4"] * n)
    add_strategy("始终猜5-9尾", ["5-9"] * n)
    add_strategy("延续策略(猜上期同组)", [groups[i - 1] if i > 0 else "0-4" for i in range(n)])
    add_strategy("反转策略(猜上期反组)", [("5-9" if groups[i - 1] == "0-4" else "0-4") if i > 0 else "0-4" for i in range(n)])

    print("\n结论：尾数层面接近真随机，无稳定可赢信号；唯一微弱信号是号码超长遗漏。")


if __name__ == "__main__":
    main()
