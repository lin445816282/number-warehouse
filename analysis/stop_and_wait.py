#!/usr/bin/env python3
"""
「不开就停，等开了再继续」策略验证
==================================
策略：锁定最冷号 → 买 1 期 → 命中(+46) 回到空仓重选号；没开(-1) 停手，等这个号开出后再重选号。
对比「跟踪持有(连续追K期)」，本策略单次只亏 1 元，避免连续追号的中间亏损。

核心指标：每次下注的命中率 p（盈亏平衡 1/47 = 2.13%）。
用法：python3 analysis/stop_and_wait.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tracking_engine as te


def run_stop_wait(draws, signal="gap", theta=10, min_votes=4, warmup=100, start_period=None):
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

    state = "IDLE"
    wait_num = None
    bets = []
    total = 0
    start = start_period if start_period is not None else warmup

    for t in range(warmup, M):
        gap = {n: (t - last_seen[n]) if last_seen[n] >= 0 else t for n in range(1, 50)}

        if state == "WAIT":
            update(t)
            if draws[t] == wait_num:
                state = "IDLE"
                wait_num = None
            continue

        # IDLE：找最冷号
        if signal == "consensus":
            tg = {x: (t - tail_last[x]) if tail_last[x] >= 0 else t for x in range(10)}
            zg = {z: (t - zodiac_last[z]) if zodiac_last[z] >= 0 else t for z in zodiac_last}
            eg = {e: (t - element_last[e]) if element_last[e] >= 0 else t for e in element_last}
            cg = {c: (t - color_last[c]) if color_last[c] >= 0 else t for c in color_last}
            num, _ = te._consensus_pick(gap, maxgap, tg, zg, eg, cg, min_votes)
            if num is None:
                update(t)
                continue
        elif signal == "ratio":
            num = max(range(1, 50), key=lambda x: gap[x] / max(maxgap[x], 1))
            if gap[num] / max(maxgap[num], 1) < theta:
                update(t)
                continue
        else:  # gap
            num = max(range(1, 50), key=lambda x: gap[x])
            if gap[num] < theta:
                update(t)
                continue

        if t < start:
            update(t)
            continue

        # 买 1 期
        if draws[t] == num:
            pnl = 46
            state = "IDLE"
        else:
            pnl = -1
            state = "WAIT"
            wait_num = num
        bets.append({"num": num, "gap": gap[num], "hit": pnl > 0, "pnl": pnl})
        total += pnl
        update(t)

    return bets, total


def report(draws, signal, theta, min_votes, label, start_period=None):
    bets, total = run_stop_wait(draws, signal, theta, min_votes, start_period=start_period)
    if not bets:
        print(f"[{label}] 无下注")
        return
    hits = sum(1 for b in bets if b["hit"])
    n = len(bets)
    p = hits / n * 100
    mu = total / n
    # 最长连亏（连续未中次数）
    cur = mx = 0
    for b in bets:
        if b["hit"]:
            cur = 0
        else:
            cur += 1
            mx = max(mx, cur)
    flag = "✅" if mu > 0 else "🔴"
    print(f"[{label}] 下注{n}次 命中{hits}({p:.2f}%) 盈亏平衡2.13% 单次期望{mu:+.3f} 总盈亏{total:+} 最长连亏{mx}次 {flag}")


def main():
    dates, draws = te.load_records()
    half = len(draws) // 2
    print(f"数据 {len(draws)} 期 ({dates[0]} ~ {dates[-1]})")
    print(f"单次下注命中盈亏平衡 = 1/47 = 2.13%\n")

    for sig, theta in [("gap", 10), ("ratio", 10), ("consensus", 4)]:
        print(f"===== 信号 {sig} =====")
        report(draws, sig, theta, 4, "全量")
        report(draws[:half], sig, theta, 4, "前段 2020-2024")
        # 后段用 start_period 保留前段 warmup
        report(draws, sig, theta, 4, "后段 2024-2026", start_period=half)


if __name__ == "__main__":
    main()
