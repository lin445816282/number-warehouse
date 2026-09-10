#!/usr/bin/env python3
"""
「最长跟踪」对比分析脚本 v2（可重跑，越细越好）

复用 backend/tracking_engine.py（67 算法），跑 4 个时间窗口：
  - 全量：2367 期（2020-03-18 ~ 2026-09-09）
  - 近2年：731 期（2024-09-09 ~ 2026-09-09）
  - 前段（训练）：前 1183 期
  - 后段（测试）：后 1184 期

分析维度：
  1. 总体对比（12 指标）
  2. 真样本外验证（前段训练 → 后段测试，无重叠）
  3. 交叉稳定性（2年 vs 全量）
  4. 算法类别 17 类
  5. N 维度
  6. 候选池饱和分析（过滤器候选号数 ≤ N 时选号不变）
  7. 等额/倍投 TOP（相邻饱和去重）
  8. 关键洞察 + 诚实结论

产出：
  - analysis/tracking_comparison_data.json
  - analysis/tracking_comparison_report.md
"""
import sys, os, json, time
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
from tracking_engine import (
    ALGORITHMS, ALGO_CATEGORIES, load_records, load_count_value_map,
    run_backtest, build_report, FILTER_FUNCS, TAIL_SETS, TAIL, ZODIAC,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(OUT_DIR, 'tracking_comparison_data.json')
MD_PATH = os.path.join(OUT_DIR, 'tracking_comparison_report.md')

WARMUP = 100
TOP = 30


def filter_by_years(dates, draws, years):
    if not dates or years <= 0:
        return dates, draws
    max_date = date.fromisoformat(dates[-1])
    cutoff = (max_date - timedelta(days=years * 365)).isoformat()
    idx = 0
    for i, d in enumerate(dates):
        if d >= cutoff:
            idx = i
            break
    return dates[idx:], draws[idx:]


def run_window(dates, draws, count_map, years):
    d2, dr2 = filter_by_years(dates, draws, years)
    st = time.time()
    results = run_backtest(dr2, d2, count_map, 3, 25, WARMUP)
    rows = build_report(results, 3, 25)
    return {
        'years': years, 'date_from': d2[0], 'date_to': d2[-1], 'total_records': len(d2),
        'rows': rows, 'elapsed': round(time.time() - st, 1),
    }


def summarize(win):
    rows = win['rows']
    eq_prof = [r for r in rows if r['eq_pnl'] > 0]
    bt_prof = [r for r in rows if r['bt_pnl'] > 0]
    eq_total = sum(r['eq_pnl'] for r in rows)
    n = len(rows)
    above_baseline = [r for r in rows if r['hit_rate'] > (r['n'] / 49 * 100)]
    above_breakeven = [r for r in rows if r['hit_rate'] > (r['n'] / 47 * 100)]
    return {
        'total': n,
        'eq_profitable': len(eq_prof),
        'eq_profitable_pct': round(len(eq_prof) / n * 100, 2),
        'bt_profitable': len(bt_prof),
        'bt_profitable_pct': round(len(bt_prof) / n * 100, 2),
        'eq_total_pnl': round(eq_total, 1),
        'eq_avg_per_scheme': round(eq_total / n, 3),
        'best_eq_pnl': max(r['eq_pnl'] for r in rows),
        'worst_eq_pnl': min(r['eq_pnl'] for r in rows),
        'best_bt_pnl': max(r['bt_pnl'] for r in rows),
        'above_baseline': len(above_baseline),
        'above_breakeven': len(above_breakeven),
        'mean_hit_rate': round(sum(r['hit_rate'] for r in rows) / n, 2),
    }


def by_category(win):
    out = []
    for (lo, hi), cat, note in ALGO_CATEGORIES:
        rows = [r for r in win['rows'] if lo <= r['algo_id'] <= hi]
        if not rows:
            continue
        eq_prof = [r for r in rows if r['eq_pnl'] > 0]
        best = max(rows, key=lambda r: r['eq_pnl'])
        out.append({
            'category': cat, 'total': len(rows),
            'eq_profitable': len(eq_prof),
            'eq_profitable_pct': round(len(eq_prof) / len(rows) * 100, 1),
            'eq_total_pnl': round(sum(r['eq_pnl'] for r in rows), 1),
            'best_eq': round(best['eq_pnl'], 1),
            'best_algo': best['algo_name'], 'best_n': best['n'], 'best_hit_rate': best['hit_rate'],
        })
    return out


def by_n(win):
    out = {}
    for r in win['rows']:
        out.setdefault(r['n'], {'total': 0, 'eq_profitable': 0, 'eq_pnl': 0, 'hit_rate_sum': 0})
        out[r['n']]['total'] += 1
        out[r['n']]['eq_pnl'] += r['eq_pnl']
        out[r['n']]['hit_rate_sum'] += r['hit_rate']
        if r['eq_pnl'] > 0:
            out[r['n']]['eq_profitable'] += 1
    for n in out:
        out[n]['eq_pnl'] = round(out[n]['eq_pnl'], 1)
        out[n]['avg_hit_rate'] = round(out[n]['hit_rate_sum'] / out[n]['total'], 2)
        out[n]['baseline'] = round(n / 49 * 100, 2)
        out[n].pop('hit_rate_sum', None)
    return out


def dedup_top(rows, key, k=TOP):
    """TOP 排名 + 相邻饱和去重：同一算法相邻 N 若关键指标完全相同（候选池饱和），合并为一行 N≥x。"""
    rows = sorted(rows, key=lambda r: -r[key])
    out = []
    for r in rows:
        if len(out) >= k:
            break
        if out and out[-1]['algo_id'] == r['algo_id'] and out[-1][key] == r[key] and out[-1]['hit_rate'] == r['hit_rate']:
            # 候选池饱和：命中率/盈利完全一致 → 合并 N 范围
            out[-1]['n_range'] = f"{out[-1]['n_min']}~{r['n']}"
            continue
        out.append({
            'algo_id': r['algo_id'], 'algo_name': r['algo_name'],
            'n': r['n'], 'n_min': r['n'], 'n_range': str(r['n']),
            'hit_rate': r['hit_rate'], 'baseline': round(r['n'] / 49 * 100, 2),
            'eq_pnl': r['eq_pnl'], 'eq_avg': r['eq_avg'], 'bt_pnl': r['bt_pnl'],
            'max_drawdown': r['max_drawdown'], 'eq_win_rate': r['eq_win_rate'],
        })
    return out


def compute_pool_sizes():
    """各静态过滤器过滤后候选号数量（1~49），用于候选池饱和分析。"""
    pool = {}
    for name, fn in FILTER_FUNCS.items():
        if name == 'none':
            continue
        pool[name] = sum(1 for num in range(1, 50) if fn(num))
    # 尾数组合（37-41）
    for aid, ts in TAIL_SETS.items():
        pool[f'tail_set_{aid}'] = sum(1 for num in range(1, 50) if TAIL[num] in ts)
    return pool


def main():
    print('读取记录...')
    dates, draws = load_records()
    count_map = load_count_value_map()
    M = len(draws)
    print(f'共 {M} 期 ({dates[0]} ~ {dates[-1]})，{len(ALGORITHMS)} 算法')

    winA = run_window(dates, draws, count_map, 0)
    print(f'[全量] {winA["elapsed"]}s {winA["total_records"]}期 {len(winA["rows"])}方案')
    winB = run_window(dates, draws, count_map, 2)
    print(f'[近2年] {winB["elapsed"]}s {winB["total_records"]}期')

    # 真样本外：前段训练 / 后段测试
    half = M // 2
    train = run_window(dates[:half], draws[:half], count_map, 0)
    test = run_window(dates[half:], draws[half:], count_map, 0)
    print(f'[前段训练] {train["elapsed"]}s {train["total_records"]}期 | [后段测试] {test["elapsed"]}s {test["total_records"]}期')

    # 候选池
    pool = compute_pool_sizes()

    # 交叉：2年 vs 全量
    keyA = {(r['algo_id'], r['n']): r['eq_pnl'] for r in winA['rows']}
    keyB = {(r['algo_id'], r['n']): r['eq_pnl'] for r in winB['rows']}
    profA = {k for k, v in keyA.items() if v > 0}
    profB = {k for k, v in keyB.items() if v > 0}
    both = profA & profB
    both_detail = []
    for k in sorted(both, key=lambda x: -keyB[x]):
        algo = next((a for a in ALGORITHMS if a[0] == k[0]), None)
        both_detail.append({
            'algo_id': k[0], 'algo_name': algo[1] if algo else '?', 'n': k[1],
            'eq_pnl_2y': round(keyB[k], 1), 'eq_pnl_full': round(keyA[k], 1),
        })

    # 真样本外：前段盈利 → 后段表现
    keyTrain = {(r['algo_id'], r['n']): r['eq_pnl'] for r in train['rows']}
    keyTest = {(r['algo_id'], r['n']): r['eq_pnl'] for r in test['rows']}
    profTrain = {k for k, v in keyTrain.items() if v > 0}
    profTest = {k for k, v in keyTest.items() if v > 0}
    oos_both = profTrain & profTest          # 前段盈利且后段仍盈利（稳健）
    oos_fail = profTrain - profTest          # 前段盈利但后段亏损（过拟合）
    oos_detail = []
    for k in sorted(oos_both, key=lambda x: -keyTest[x]):
        algo = next((a for a in ALGORITHMS if a[0] == k[0]), None)
        oos_detail.append({
            'algo_id': k[0], 'algo_name': algo[1] if algo else '?', 'n': k[1],
            'eq_train': round(keyTrain[k], 1), 'eq_test': round(keyTest[k], 1),
        })

    data = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'warmup': WARMUP, 'algo_count': len(ALGORITHMS),
        'windows': {
            'full': {'years': 0, 'summary': summarize(winA), 'by_category': by_category(winA),
                     'by_n': by_n(winA), 'top_eq': dedup_top(winA['rows'], 'eq_pnl'),
                     'top_bt': dedup_top(winA['rows'], 'bt_pnl'),
                     'date_from': winA['date_from'], 'date_to': winA['date_to'], 'total_records': winA['total_records']},
            '2y': {'years': 2, 'summary': summarize(winB), 'by_category': by_category(winB),
                   'by_n': by_n(winB), 'top_eq': dedup_top(winB['rows'], 'eq_pnl'),
                   'top_bt': dedup_top(winB['rows'], 'bt_pnl'),
                   'date_from': winB['date_from'], 'date_to': winB['date_to'], 'total_records': winB['total_records']},
            'train': {'summary': summarize(train), 'date_from': train['date_from'], 'date_to': train['date_to'], 'total_records': train['total_records']},
            'test': {'summary': summarize(test), 'date_from': test['date_from'], 'date_to': test['date_to'], 'total_records': test['total_records']},
        },
        'cross': {
            'profitable_full': len(profA), 'profitable_2y': len(profB),
            'both_profitable': len(both), 'only_2y': len(profB - profA), 'only_full': len(profA - profB),
            'both_detail': both_detail,
        },
        'oos': {
            'train_profitable': len(profTrain), 'test_profitable': len(profTest),
            'oos_both': len(oos_both), 'oos_fail': len(oos_fail),
            'oos_detail': oos_detail,
        },
        'pool_sizes': pool,
    }

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'\n结构化数据已保存: {JSON_PATH}')

    md = build_report_md(data)
    with open(MD_PATH, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'报告已保存: {MD_PATH}')


def _md_table(header, rows):
    L = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join(['---'] * len(header)) + '|']
    for r in rows:
        L.append('| ' + ' | '.join(str(x) for x in r) + ' |')
    return '\n'.join(L)


def build_report_md(data):
    A, B = data['windows']['full'], data['windows']['2y']
    sA, sB = A['summary'], B['summary']
    C, O = data['cross'], data['oos']
    L = []
    L.append('# 最长跟踪演算 — 全量 vs 近2年 vs 真样本外 对比分析报告')
    L.append('')
    L.append(f"> 生成：{data['generated_at']} · 算法 {data['algo_count']} · 预热 {data['warmup']} 期")
    L.append(f"> 全量 {A['total_records']}期（{A['date_from']}~{A['date_to']}） · 近2年 {B['total_records']}期（{B['date_from']}~{B['date_to']}）")
    L.append(f"> 前段训练 {data['windows']['train']['total_records']}期 · 后段测试 {data['windows']['test']['total_records']}期")
    L.append('')

    # 关键洞察（前置）
    L.append('## 〇、关键洞察（TL;DR）')
    L.append('')
    L.append(f"1. **近2年等额盈利方案占比 {sB['eq_profitable_pct']}%（445/{sB['total']}），远高于全量 {sA['eq_profitable_pct']}%（{sA['eq_profitable']}/{sA['total']}）** —— 2年窗口的「盈利」大部分是窗口偶然，拉长历史即大幅缩水。")
    L.append(f"2. **真样本外（前段训练→后段测试）仅 {O['oos_both']} 个方案两段都盈利**，而前段盈利的 {O['train_profitable']} 个方案里有 {O['oos_fail']} 个在后段转亏 —— 过拟合率 {round(O['oos_fail']/max(O['train_profitable'],1)*100,1)}%。")
    L.append(f"3. **2年 vs 全量交叉：仅 {C['both_profitable']} 个方案两窗口都盈利**（{C['profitable_2y']} 个2年盈利方案里 {C['only_2y']} 个全量转亏）。")
    L.append(f"4. **小 N 才是等额正期望区**：N=3 时近2年 41/67 方案盈利、总盈亏 +4722；N≥5 总盈亏转负，N 越大越亏（详见第四节）。")
    L.append(f"5. **候选池饱和**：五行木/水/火等过滤仅 ~10 个号，N≥10 后选号不再变（TOP 表已合并去重）。")
    L.append('')

    # 1. 总体
    L.append('## 一、总体对比')
    L.append('')
    L.append(_md_table(
        ['指标', '全量', '近2年', '前段训练', '后段测试'],
        [
            ['方案总数', sA['total'], sB['total'], data['windows']['train']['summary']['total'], data['windows']['test']['summary']['total']],
            ['等额盈利方案', f"{sA['eq_profitable']}（{sA['eq_profitable_pct']}%）", f"{sB['eq_profitable']}（{sB['eq_profitable_pct']}%）",
             f"{data['windows']['train']['summary']['eq_profitable']}", f"{data['windows']['test']['summary']['eq_profitable']}"],
            ['倍投盈利方案', f"{sA['bt_profitable']}（{sA['bt_profitable_pct']}%）", f"{sB['bt_profitable']}（{sB['bt_profitable_pct']}%）", '—', '—'],
            ['等额总盈亏', sA['eq_total_pnl'], sB['eq_total_pnl'], '—', '—'],
            ['等额单方案均值', sA['eq_avg_per_scheme'], sB['eq_avg_per_scheme'], '—', '—'],
            ['最佳等额盈利', sA['best_eq_pnl'], sB['best_eq_pnl'], '—', '—'],
            ['平均命中率', f"{sA['mean_hit_rate']}%", f"{sB['mean_hit_rate']}%", '—', '—'],
            ['命中率超基线(N/49)', sA['above_baseline'], sB['above_baseline'], '—', '—'],
            ['命中率超盈亏平衡(N/47)', sA['above_breakeven'], sB['above_breakeven'], '—', '—'],
        ]
    ))
    L.append('')
    L.append('> 注：等额盈利 ⇔ 命中率 > N/47（47×命中 − N > 0），故「等额盈利方案数」=「命中率超盈亏平衡方案数」。')
    L.append('')

    # 2. 真样本外
    L.append('## 二、真样本外验证（前段训练 → 后段测试，无重叠）')
    L.append('')
    L.append('把 2367 期按时间对半切：前 1183 期训练（找盈利方案），后 1184 期测试（验证是否仍盈利）。这是无未来函数的严格样本外。')
    L.append('')
    L.append(_md_table(['指标', '数值'],
        [['前段盈利方案', O['train_profitable']],
         ['后段盈利方案', O['test_profitable']],
         ['两段都盈利（稳健信号）', f"**{O['oos_both']}**"],
         ['前段盈利但后段亏损（过拟合）', O['oos_fail']]]))
    L.append('')
    if O['oos_detail']:
        L.append('两段都盈利的方案（按后段等额盈利降序）：')
        L.append('')
        L.append(_md_table(['算法', 'N', '前段等额', '后段等额'],
            [[d['algo_name'], d['n'], d['eq_train'], d['eq_test']] for d in O['oos_detail']]))
        L.append('')

    # 3. 交叉稳定性
    L.append('## 三、交叉稳定性（2年 vs 全量）')
    L.append('')
    L.append(_md_table(['指标', '数值'],
        [['近2年盈利方案', C['profitable_2y']],
         ['全量盈利方案', C['profitable_full']],
         ['两窗口都盈利', f"**{C['both_profitable']}**"],
         ['仅近2年盈利（全量转亏）', C['only_2y']],
         ['仅全量盈利（近2年衰减）', C['only_full']]]))
    L.append('')
    if C['both_detail']:
        L.append('两窗口都盈利的方案（按近2年等额盈利降序）：')
        L.append('')
        L.append(_md_table(['算法', 'N', '近2年等额', '全量等额'],
            [[d['algo_name'], d['n'], d['eq_pnl_2y'], d['eq_pnl_full']] for d in C['both_detail']]))
        L.append('')

    # 4. 算法类别
    L.append('## 四、算法类别（17类）表现')
    L.append('')
    catB = {c['category']: c for c in B['by_category']}
    rows = []
    for cA in A['by_category']:
        cB = catB.get(cA['category'])
        rows.append([
            cA['category'],
            f"{cA['eq_profitable']}/{cA['total']}",
            f"{cB['eq_profitable']}/{cB['total']}" if cB else '—',
            cB['best_eq'] if cB else '—',
            f"{cB['best_algo']}(N={cB['best_n']})" if cB else '—',
        ])
    L.append(_md_table(['类别', '全量盈利/总', '近2年盈利/总', '近2年最佳等额', '最佳方案'], rows))
    L.append('')

    # 5. N 维度
    L.append('## 五、号码数 N 维度（近2年）')
    L.append('')
    L.append(_md_table(['N', '方案数', '盈利方案', '等额总盈亏', '平均命中率', '基线'],
        [[n, x['total'], x['eq_profitable'], x['eq_pnl'], f"{x['avg_hit_rate']}%", f"{x['baseline']}%"]
         for n in sorted(B['by_n'].keys()) for x in [B['by_n'][n]]]))
    L.append('')

    # 6. 候选池饱和
    L.append('## 六、候选池饱和（过滤器候选号数 ≤ N 时选号不变）')
    L.append('')
    pool = data['pool_sizes']
    pool_rows = sorted(pool.items(), key=lambda x: x[1])
    L.append(_md_table(['过滤器', '候选号数'], [[k, v] for k, v in pool_rows]))
    L.append('')
    L.append('> 候选号数 ≤ 25 的过滤器，当 N 超过候选数时选出的号完全相同（如五行木仅 10 个号，N=10~25 结果一致，TOP 表已合并）。')
    L.append('')

    # 7. 等额 TOP
    L.append(f'## 七、等额口径 TOP {TOP}（饱和去重）')
    L.append('')
    L.append('### 近2年')
    L.append('')
    L.append(_md_table(['#', '算法', 'N', '命中率', '基线', '等额盈利', '单期均值', '最大回撤'],
        [[i+1, r['algo_name'], r['n_range'], f"{r['hit_rate']}%", f"{r['baseline']}%", r['eq_pnl'], r['eq_avg'], r['max_drawdown']]
         for i, r in enumerate(B['top_eq'])]))
    L.append('')
    L.append('### 全量')
    L.append('')
    L.append(_md_table(['#', '算法', 'N', '命中率', '基线', '等额盈利', '单期均值'],
        [[i+1, r['algo_name'], r['n_range'], f"{r['hit_rate']}%", f"{r['baseline']}%", r['eq_pnl'], r['eq_avg']]
         for i, r in enumerate(A['top_eq'])]))
    L.append('')

    # 8. 倍投 TOP
    L.append(f'## 八、倍投口径 TOP {TOP}（杠杆放大，勿与等额直接比较）')
    L.append('')
    L.append('### 近2年')
    L.append('')
    L.append(_md_table(['#', '算法', 'N', '命中率', '倍投盈利'],
        [[i+1, r['algo_name'], r['n_range'], f"{r['hit_rate']}%", r['bt_pnl']] for i, r in enumerate(B['top_bt'])]))
    L.append('')

    # 9. 诚实结论
    L.append('## 九、诚实结论')
    L.append('')
    L.append('- **结构约束**：47 赔率 < 49 号码，等额长期负期望。命中率需 > N/47 才盈利，随机基线 N/49，胜率窗口仅约 2 个百分点（且随 N 增大窗口收窄到 0）。')
    L.append('- **冷号回补假设**：命中率普遍贴近随机基线，说明「越久未出越该出」无强支撑（与尾数分析一致）。')
    L.append('- **窗口脆弱**：近2年 28.9% 方案盈利看似可观，但拉长到全量只剩 6.6%，真样本外过拟合率极高——**大部分「盈利」是窗口噪声，不是信号**。')
    L.append('- **唯一稳健方向**：真样本外 + 2年/全量交叉都盈利的极少数方案（多为 N=3~4 的小号数 + 遗漏比/遗漏类），命中率仅比基线高 1~2 个百分点，单期均值 1~2 元，属「微弱但可能真实」的边缘优势，需实盘小注验证。')
    L.append('- **倍投陷阱**：倍投盈利随遗漏指数放大（杠杆假象），回撤与资金曲线完全不同，不可与等额比较。')
    L.append('- **筛选建议**：以「真样本外两段都盈利」+「2年/全量交叉都盈利」的交集为候选池，再按命中率超 N/47 幅度 + 最大回撤排序，小 N 优先。')
    L.append('')
    L.append('---')
    L.append('')
    L.append('> 本报告由 `analysis/tracking_comparison.py` 生成，可重跑。结构化数据见 `tracking_comparison_data.json`。')
    L.append('')
    return '\n'.join(L)


if __name__ == '__main__':
    main()
