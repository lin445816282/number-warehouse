#!/usr/bin/env python3
"""
「前8最冷号 + 6期周期」方案 —— 完整过程逐轮明细
================================================
策略：锁定当前最冷的 8 个号，每期各买 1 元（每期 8 元）：
  - 命中(8个号里某个开出) → 该号赚 47 元，净 47-8×期数，重新选 8 号重算 6 期
  - 6 期全没中 → 亏 48 元，停手空仓，等这 8 个号里某个开出 → 再选 8 号买 6 期

输出：每轮完整过程（进场8号+遗漏 → 命中/止损 → 盈亏 → 累计）+ 汇总
用法：python3 analysis/multi_track_detail.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def pad2(n):
    return str(n).zfill(2)


def run_detail(draws, N=8, K=6, warmup=100):
    M = len(draws)
    last_seen = {n: -1 for n in range(1, 50)}
    for t in range(min(warmup, M)):
        last_seen[draws[t]] = t

    state = "BUY"
    tracking = []
    held = 0
    enter_idx = None
    wait_set = set()
    rounds = []
    wait_days = 0

    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}

        if state == "WAIT":
            wait_days += 1
            if draws[t] in wait_set:
                state = "BUY"
                wait_set = set()
                tracking = []
                held = 0
                enter_idx = None
        else:  # BUY
            if not tracking:
                # 选当前最冷 8 个号
                tracking = sorted(range(1, 50), key=lambda x: gap[x], reverse=True)[:N]
                held = 0
                enter_idx = t
            held += 1
            if draws[t] in tracking:
                # 命中
                rounds.append({
                    "enter_idx": enter_idx, "enter_date": None,
                    "nums": tracking[:], "gaps": [gap[x] for x in tracking],
                    "held": held, "hit_num": draws[t], "result": "hit",
                    "pnl": 47 - N * held, "end_idx": t, "end_date": None,
                })
                tracking = []
                held = 0
                enter_idx = None
            elif held >= K:
                # 6 期没中，止损
                rounds.append({
                    "enter_idx": enter_idx, "enter_date": None,
                    "nums": tracking[:], "gaps": [gap[x] for x in tracking],
                    "held": K, "hit_num": None, "result": "stop",
                    "pnl": -N * K, "end_idx": t, "end_date": None,
                })
                wait_set = set(tracking)
                tracking = []
                held = 0
                enter_idx = None
                state = "WAIT"

        last_seen[draws[t]] = t

    return rounds, wait_days


def main():
    dates, draws = te.load_records()
    N, K = 8, 6
    rounds, wait_days = run_detail(draws, N, K)

    # 补日期
    for r in rounds:
        r["enter_date"] = dates[r["enter_idx"]]
        r["end_date"] = dates[r["end_idx"]]

    # 累计盈亏
    cum = 0
    hits = 0
    for r in rounds:
        cum += r["pnl"]
        r["cum_pnl"] = cum
        if r["result"] == "hit":
            hits += 1

    total = len(rounds)
    print(f"=== 「前 8 最冷号 + 6 期周期」完整逐轮过程（{dates[0]} ~ {dates[-1]}）===")
    print(f"总轮数 {total} | 命中 {hits} | 止损 {total-hits} | 总盈亏 {cum:+} | 空仓 {wait_days} 天\n")

    print(f"{'#':>4} {'进场日期':<11}{'进场8号(遗)':<45}{'结果':<18}{'盈亏':>6}{'累计':>8}")
    print("-" * 100)
    for i, r in enumerate(rounds, 1):
        nums_str = ".".join(pad2(x) for x in r["nums"])
        if r["result"] == "hit":
            res = f"第{r['held']}期中{pad2(r['hit_num'])}"
        else:
            res = f"6期未中·止损"
        print(f"{i:>4} {r['enter_date']:<11}{nums_str:<45}{res:<18}{r['pnl']:>+6}{r['cum_pnl']:>+8}")

    # 保存 JSON
    out = os.path.join(os.path.dirname(__file__), "multi_track_detail.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rounds, f, ensure_ascii=False, indent=2)
    print(f"\n完整明细已保存: {out}")


if __name__ == "__main__":
    main()
