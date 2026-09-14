#!/usr/bin/env python3
"""
验证 train3y_live_test.py 的 walk_forward 逻辑正确性
=====================================================
四重验证：
1. hold 结构 vs 已验证引擎 run_tracking_hold 交叉对拍（6 组参数）
2. stopwait 结构 vs stop_and_wait.run_stop_wait 交叉对拍
3. 无未来函数：每轮进场号，用进场期之前数据重算遗漏，核对 enter_gap
4. 盈亏手算：逐轮 pnl 独立重算核对累计
用法：python3 analysis/verify_logic.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))
import tracking_engine as te
from train3y_live_test import walk_forward, summary, _pick
from stop_and_wait import run_stop_wait


def check_hold_crosscheck(draws):
    print("【验证1】hold 结构 vs run_tracking_hold 交叉对拍")
    tests = [
        ("gap", 10, 4, 12), ("gap", 50, 4, 12), ("gap", 150, 4, 24),
        ("ratio", 0.5, 4, 12),
        ("consensus", 10, 4, 12), ("consensus", 10, 4, 24), ("consensus", 10, 7, 24),
    ]
    all_ok = True
    for signal, theta, mv, K in tests:
        mine = walk_forward(draws, signal, theta, mv, K, "hold", warmup=100)
        ref = te.run_tracking_hold(draws, theta=theta, K=K, signal=signal, min_votes=mv)
        my_hits = sum(1 for r in mine if r["result"] == "hit")
        my_pnl = sum(r["pnl"] for r in mine)
        ok = (len(mine) == ref["rounds"] and my_hits == ref["wins"] and my_pnl == ref["total_pnl"])
        all_ok &= ok
        print(f"  [{'✅' if ok else '❌'}] {signal:<10} theta={theta:>4} mv={mv} K={K:>2} | "
              f"轮数 {len(mine)}={ref['rounds']} 命中 {my_hits}={ref['wins']} 盈亏 {my_pnl}={ref['total_pnl']}")
    return all_ok


def check_stopwait_crosscheck(draws):
    print("\n【验证2】stopwait 结构 vs stop_and_wait.run_stop_wait 交叉对拍")
    tests = [("gap", 10, 4), ("ratio", 0.5, 4), ("consensus", 10, 4), ("consensus", 10, 7)]
    all_ok = True
    for signal, theta, mv in tests:
        mine = walk_forward(draws, signal, theta, mv, 1, "stopwait", warmup=100)
        ref_bets, ref_total = run_stop_wait(draws, signal, theta, mv)
        my_pnl = sum(r["pnl"] for r in mine)
        my_hits = sum(1 for r in mine if r["result"] == "hit")
        ref_hits = sum(1 for b in ref_bets if b["hit"])
        ok = (len(mine) == len(ref_bets) and my_hits == ref_hits and my_pnl == ref_total)
        all_ok &= ok
        print(f"  [{'✅' if ok else '❌'}] {signal:<10} theta={theta:>4} mv={mv} | "
              f"下注 {len(mine)}={len(ref_bets)} 命中 {my_hits}={ref_hits} 盈亏 {my_pnl}={ref_total}")
    return all_ok


def check_no_lookahead(draws):
    print("\n【验证3】无未来函数：逐轮重算 enter_gap 核对")
    rounds = walk_forward(draws, "gap", 10, 4, 12, "hold", warmup=100)
    all_ok = True
    n_check = min(8, len(rounds))
    for r in rounds[:n_check]:
        num, t = r["num"], r["enter_idx"]
        last = -1
        for i in range(t):  # 只用 t 之前的数据
            if draws[i] == num:
                last = i
        gap = t - last if last >= 0 else t
        ok = (gap == r["enter_gap"])
        all_ok &= ok
        if not ok:
            print(f"  ❌ 号{num} enter_idx={t} 重算遗漏={gap} ≠ 记录={r['enter_gap']}")
    print(f"  [{'✅' if all_ok else '❌'}] 抽查前 {n_check} 轮 enter_gap 全部与「只用过去数据重算」一致")
    return all_ok


def check_pnl(draws):
    print("\n【验证4】盈亏手算核对（每轮 pnl 独立重算）")
    rounds = walk_forward(draws, "consensus", 10, 4, 12, "hold", warmup=100)
    all_ok = True
    cum = 0
    for r in rounds:
        expect = (47 - r["held"]) if r["result"] == "hit" else -12
        if r["pnl"] != expect:
            all_ok = False
            print(f"  ❌ 轮 {r['enter_idx']} pnl={r['pnl']} ≠ 期望 {expect}")
        cum += r["pnl"]
    s = summary(rounds, 12)
    ok2 = (cum == s["pnl"])
    all_ok &= ok2
    print(f"  [{'✅' if all_ok else '❌'}] {len(rounds)} 轮 pnl 逐轮核对，累计 {cum} = summary {s['pnl']}")
    return all_ok


def check_split_boundary(draws):
    print("\n【验证5】训练/测试期切分边界核对")
    TRAIN = 1095
    # 训练期最优方案重跑，确认训练期轮次全部 end_idx < TRAIN
    train_rounds = walk_forward(draws[:TRAIN], "consensus", 10, 7, 24, "hold", warmup=100)
    max_end = max(r["end_idx"] for r in train_rounds) if train_rounds else 0
    ok = max_end < TRAIN
    print(f"  [{'✅' if ok else '❌'}] 训练期 {len(train_rounds)} 轮，最后结束期 {max_end} < 训练期边界 {TRAIN}")
    # 测试期首轮 enter_idx 可能 < TRAIN（跨边界持仓），这是真实逻辑允许的
    test_rounds = walk_forward(draws, "consensus", 10, 7, 24, "hold", warmup=100, record_from=TRAIN)
    if test_rounds:
        first_enter = test_rounds[0]["enter_idx"]
        print(f"  ℹ️ 测试期首轮进场期 {first_enter}（跨边界持仓：训练期进场、测试期结算，属真实逻辑）")
    return ok


def main():
    dates, draws = te.load_records()
    print(f"数据 {len(draws)} 期\n")
    r1 = check_hold_crosscheck(draws)
    r2 = check_stopwait_crosscheck(draws)
    r3 = check_no_lookahead(draws)
    r4 = check_pnl(draws)
    r5 = check_split_boundary(draws)
    print("\n" + "=" * 60)
    all_ok = all([r1, r2, r3, r4, r5])
    print(f"总结论：{'✅ 全部验证通过，逻辑正确' if all_ok else '❌ 存在逻辑问题，需修复'}")


if __name__ == "__main__":
    main()
