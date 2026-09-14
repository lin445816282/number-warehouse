#!/usr/bin/env python3
"""
3年训练 → 真实买卖逻辑 样本外验证
====================================
训练期：最早 3 年（2020-03-18 ~ 2023-03-17，1095 期）
测试期：之后（2023-03-18 ~ 2026-09-11，1274 期）

流程：
1. 训练期穷尽全部方案（信号×阈值×K×下注结构），按训练期总盈亏选出最优
2. 测试期固定最优参数，walk-forward 逐期真实操作（只用过去数据，不重训）
3. 输出逐轮明细列表 + 汇总结果，保存 JSON

用法：python3 analysis/train3y_live_test.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


# ── 统一 walk-forward 引擎（训练期评估 + 测试期操作共用）──
def walk_forward(draws, signal="gap", theta=10, mv=4, K=12, structure="hold",
                 warmup=100, record_from=None):
    """
    从 warmup 期开始逐期推进（只用过去数据），从 record_from 期开始记录轮次。
    structure: 'hold'=跟踪持有 / 'stopwait'=不开就停
    返回 rounds: [{num, enter_idx, enter_gap, held, result, pnl, end_idx}]
    """
    M = len(draws)
    freq = {n: 0 for n in range(1, 50)}
    maxgap = {n: 0 for n in range(1, 50)}
    last_seen = {n: -1 for n in range(1, 50)}
    tail_last = {t: -1 for t in range(10)}
    zodiac_last = {z: -1 for z in set(te.ZODIAC.values())}
    element_last = {e: -1 for e in set(te.ELEMENT.values())}
    color_last = {c: -1 for c in set(te.COLOR.values())}

    def update(t):
        d = draws[t]
        freq[d] += 1
        if last_seen[d] >= 0:
            g = t - last_seen[d] - 1
            if g > maxgap[d]:
                maxgap[d] = g
        last_seen[d] = t
        tail_last[te.TAIL[d]] = t
        zodiac_last[te.ZODIAC[d]] = t
        element_last[te.ELEMENT[d]] = t
        color_last[te.COLOR[d]] = t

    for t in range(min(warmup, M)):
        update(t)

    rec_from = record_from if record_from is not None else warmup
    rounds = []

    if structure == "stopwait":
        state = "IDLE"; wait_num = None
        for t in range(warmup, M):
            gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
            if state == "WAIT":
                update(t)
                if draws[t] == wait_num:
                    state = "IDLE"; wait_num = None
                continue
            num = _pick(signal, theta, mv, gap, maxgap, tail_last, zodiac_last, element_last, color_last, t)
            if num is None:
                update(t); continue
            if t >= rec_from:
                if draws[t] == num:
                    rounds.append({"num": num, "enter_idx": t, "enter_gap": gap[num],
                                   "held": 1, "result": "hit", "pnl": 46, "end_idx": t})
                    state = "IDLE"
                else:
                    rounds.append({"num": num, "enter_idx": t, "enter_gap": gap[num],
                                   "held": 1, "result": "stop", "pnl": -1, "end_idx": t})
                    state = "WAIT"; wait_num = num
            else:
                # 训练期（record_from 之前）也要推进状态，但不记录
                if draws[t] == num:
                    state = "IDLE"
                else:
                    state = "WAIT"; wait_num = num
            update(t)
    else:  # hold
        tracking = None; held = 0; enter_idx = None; enter_gap = None
        for t in range(warmup, M):
            gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}
            if tracking is None:
                num = _pick(signal, theta, mv, gap, maxgap, tail_last, zodiac_last, element_last, color_last, t)
                if num is not None:
                    tracking = num; held = 0; enter_idx = t; enter_gap = gap[num]
            if tracking is not None:
                held += 1
                if draws[t] == tracking:
                    if t >= rec_from:
                        rounds.append({"num": tracking, "enter_idx": enter_idx, "enter_gap": enter_gap,
                                       "held": held, "result": "hit", "pnl": 47 - held, "end_idx": t})
                    tracking = None
                elif held >= K:
                    if t >= rec_from:
                        rounds.append({"num": tracking, "enter_idx": enter_idx, "enter_gap": enter_gap,
                                       "held": held, "result": "stop", "pnl": -K, "end_idx": t})
                    tracking = None
            update(t)
    return rounds


def _pick(signal, theta, mv, gap, maxgap, tail_last, zodiac_last, element_last, color_last, t):
    if signal == "consensus":
        tg = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
        zg = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
        eg = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
        cg = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}
        return te._consensus_pick(gap, maxgap, tg, zg, eg, cg, mv)[0]
    elif signal == "ratio":
        num = max(range(1, 50), key=lambda x: gap[x] / max(maxgap[x], 1))
        return num if gap[num] / max(maxgap[num], 1) >= theta else None
    else:
        num = max(range(1, 50), key=lambda x: gap[x])
        return num if gap[num] >= theta else None


def summary(rounds, K=12):
    if not rounds:
        return {"total": 0, "hits": 0, "rate": 0, "pnl": 0, "mu": 0, "max_dd": 0, "max_loss": 0}
    hits = sum(1 for r in rounds if r["result"] == "hit")
    pnl = sum(r["pnl"] for r in rounds)
    # 最大回撤（按轮次累计）
    cur = 0; dd = 0; peak = 0; equity = 0
    for r in rounds:
        equity += r["pnl"]
        peak = max(peak, equity)
        dd = min(dd, equity - peak)
    # 最长连亏
    cur_loss = mx = 0
    for r in rounds:
        if r["pnl"] < 0:
            cur_loss += 1; mx = max(mx, cur_loss)
        else:
            cur_loss = 0
    return {"total": len(rounds), "hits": hits,
            "rate": round(hits / len(rounds) * 100, 2), "pnl": pnl,
            "mu": round(pnl / len(rounds), 3), "max_dd": dd, "max_loss": mx}


def main():
    dates, draws = te.load_records()
    TRAIN = 1095  # 最早 3 年
    print(f"训练期 {TRAIN} 期（{dates[0]} ~ {dates[TRAIN-1]}）")
    print(f"测试期 {len(draws)-TRAIN} 期（{dates[TRAIN]} ~ {dates[-1]}）\n")

    # 方案空间
    sigs = []
    for th in [10, 30, 50, 100, 150, 180]:
        sigs.append(("gap", th, 4))
    for th in [0.3, 0.5, 0.7, 0.9]:
        sigs.append(("ratio", th, 4))
    for mv in [2, 3, 4, 5, 6, 7]:
        sigs.append(("consensus", 10, mv))
    Ks = [3, 6, 9, 12, 18, 24, 30]

    # ── 1. 训练期穷尽 ──
    print("=" * 80)
    print("【训练期穷尽】全部方案在最早3年的表现（按总盈亏降序 TOP 20）")
    print("=" * 80)
    train_rows = []
    for signal, theta, mv in sigs:
        for K in Ks:
            r = walk_forward(draws[:TRAIN], signal, theta, mv, K, "hold", warmup=100)
            s = summary(r, K)
            train_rows.append({"structure": "hold", "signal": signal, "theta": theta, "mv": mv, "K": K,
                               **s, "rounds": r})
        r = walk_forward(draws[:TRAIN], signal, theta, mv, 1, "stopwait", warmup=100)
        s = summary(r, 1)
        train_rows.append({"structure": "stopwait", "signal": signal, "theta": theta, "mv": mv, "K": 1,
                           **s, "rounds": r})

    train_rows.sort(key=lambda x: -x["pnl"])
    print(f"{'结构':<8}{'信号':<10}{'阈值':>5}{'K':>4}{'训练期轮数':>9}{'命中率':>8}{'总盈亏':>8}{'单轮期望':>9}")
    for r in train_rows[:20]:
        th = r["mv"] if r["signal"] == "consensus" else r["theta"]
        print(f"{r['structure']:<8}{r['signal']:<10}{th:>5}{r['K']:>4}{r['total']:>9}{r['rate']:>7.1f}%"
              f"{r['pnl']:>+8}{r['mu']:>+9.2f}")

    best = train_rows[0]
    th = best["mv"] if best["signal"] == "consensus" else best["theta"]
    print(f"\n>>> 训练期最优：{best['structure']} | {best['signal']} | 阈值={th} | K={best['K']} "
          f"| 训练期总盈亏 {best['pnl']:+.0f} | 命中率 {best['rate']}%")

    # ── 2. 测试期真实操作 ──
    print("\n" + "=" * 80)
    print(f"【测试期真实操作】固定最优参数，walk-forward 逐期操作（{dates[TRAIN]} ~ {dates[-1]}）")
    print("=" * 80)
    test_rounds = walk_forward(draws, best["signal"], best["theta"], best["mv"], best["K"],
                               best["structure"], warmup=100, record_from=TRAIN)
    s = summary(test_rounds, best["K"])
    print(f"测试期轮数 {s['total']} | 命中 {s['hits']}（{s['rate']}%）| 总盈亏 {s['pnl']:+.0f} "
          f"| 单轮期望 {s['mu']:+.2f} | 最大回撤 {s['max_dd']} | 最长连亏 {s['max_loss']} 轮")

    # 逐轮明细
    print(f"\n{'进场日期':<12}{'号码':>4}{'遗漏':>6}{'跟期':>5}{'结果':>6}{'盈亏':>7}{'累计盈亏':>9}")
    print("-" * 60)
    cum = 0
    detail = []
    for r in test_rounds:
        cum += r["pnl"]
        d = dates[r["end_idx"]]
        res = "✅命中" if r["result"] == "hit" else "⛔止损"
        print(f"{d:<12}{r['num']:>4}{r['enter_gap']:>6}{r['held']:>5}{res:>6}{r['pnl']:>+7}{cum:>+9}")
        detail.append({"date": d, "num": r["num"], "gap": r["enter_gap"], "held": r["held"],
                       "result": r["result"], "pnl": r["pnl"], "cum_pnl": cum})

    # 保存
    out = {
        "train_period": [dates[0], dates[TRAIN - 1]],
        "test_period": [dates[TRAIN], dates[-1]],
        "best_scheme": {"structure": best["structure"], "signal": best["signal"],
                        "theta": best["theta"], "min_votes": best["mv"], "K": best["K"],
                        "train_pnl": best["pnl"], "train_rate": best["rate"]},
        "test_summary": s,
        "test_rounds": detail,
    }
    out_path = os.path.join(os.path.dirname(__file__), "train3y_live_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
