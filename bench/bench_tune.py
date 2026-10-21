#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подбор слияния каналов офлайн — по снимкам каналов из bench_results_*.json (без обращения к API, за секунды).

    python bench/bench_tune.py bench/results/bench_results_ГГГГММДД-ЧЧММ.json

Для каждого запроса берутся сохранённые списки film_id: FTS по запросу (fts_raw), FTS «только полное покрытие» (fts_and),
семантика по запросу (sem_raw), а также варианты с расширением (fts_exp, sem_exp), если они есть. Перебираются:
  - вес FTS в RRF (0.0…1.0, k=60) для четырёх наборов каналов: сырые; с расширением; сырой FTS + семантика расширения; FTS расширения + сырая семантика;
  - бонус за полное лексическое покрытие: фильмы из первых N строк fts_and получают добавку к RRF-очкам (или ставятся первыми).
Метрики слитого списка (до реранкера): Hit@1, Recall@5, Recall@20, MRR@20 — в целом и по классам известные/редкие.
Это только этап отбора кандидатов: как поведёт себя реранкер на новом слиянии, покажет повторный bench_search.py."""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')


def rrf(lists_with_weights, k=60):
    sc = {}
    for ids, w in lists_with_weights:
        for rank, fid in enumerate(ids):
            sc[fid] = sc.get(fid, 0.0) + w / (k + rank + 1)
    return sc


def evaluate(channels, cls_of, w_fts, mode, bonus_n=0, bonus=0.0, k=60):
    res = {'all': [], 'famous': [], 'rare': []}
    for n, ch in channels.items():
        fid = ch['film_id']
        if mode == 'raw': f, s = ch.get('fts_raw', []), ch.get('sem_raw', [])
        elif mode == 'exp': f, s = ch.get('fts_exp', []), ch.get('sem_exp', [])
        elif mode == 'fraw_sexp': f, s = ch.get('fts_raw', []), ch.get('sem_exp', [])
        elif mode == 'fexp_sraw': f, s = ch.get('fts_exp', []), ch.get('sem_raw', [])
        else: raise ValueError(mode)
        sc = rrf([(f, w_fts), (s, 1.0 - w_fts)], k)
        if bonus_n:
            for fid2 in ch.get('fts_and', [])[:bonus_n]:
                sc[fid2] = sc.get(fid2, 0.0) + bonus
        ranked = [x for x, _ in sorted(sc.items(), key=lambda kv: kv[1], reverse=True)]
        r = ranked.index(fid) + 1 if fid in ranked else None
        res['all'].append(r); res[cls_of[n]].append(r)
    out = {}
    for key, rs in res.items():
        if not rs: continue
        n = len(rs)
        out[key] = {'n': n, 'hit1': sum(1 for r in rs if r == 1) / n, 'r5': sum(1 for r in rs if r and r <= 5) / n,
                    'r20': sum(1 for r in rs if r and r <= 20) / n, 'mrr20': sum(1.0 / r for r in rs if r and r <= 20) / n}
    return out


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    data = json.load(open(sys.argv[1], encoding='utf-8'))
    channels = {int(n): ch for n, ch in data['channels'].items() if 'fts_raw' in ch}
    cls_of = {r['n']: r['class'] for r in data['rows']}
    has_exp = any('fts_exp' in ch for ch in channels.values())
    print(f"Запросов со снимками каналов: {len(channels)}; расширение: {'есть' if has_exp else 'нет'}\n")
    modes = ['raw'] + (['exp', 'fraw_sexp', 'fexp_sraw'] if has_exp else [])
    names = {'raw': 'сырые FTS + сырая семантика', 'exp': 'FTS расширения + семантика расширения', 'fraw_sexp': 'сырой FTS + семантика расширения', 'fexp_sraw': 'FTS расширения + сырая семантика'}
    rows = []
    for mode in modes:
        for w in [i / 10 for i in range(0, 11)]:
            for bn, b in [(0, 0.0), (3, 0.01), (5, 0.01), (3, 0.02), (5, 0.02)]:
                m = evaluate(channels, cls_of, w, mode, bn, b)
                rows.append((mode, w, bn, b, m))
    rows.sort(key=lambda x: (x[4]['all']['mrr20'], x[4]['all']['r20']), reverse=True)
    try:
        import film_search as _fs
        _w = f"{_fs.fusion_weights(True)[0]} (с реранкером) / {_fs.fusion_weights(False)[0]} (без)"
    except Exception:
        _w = "см. FTS_WEIGHT_* в film_search.py"
    print(f"Настройки движка сейчас: вес FTS {_w}; расширение по умолчанию выключено (сырые каналы); без бонуса покрытия.")
    def line(mode, w, bn, b, m):
        a = m['all']; f = m.get('famous'); r = m.get('rare')
        def fmt(x): return f"H1 {x['hit1']:.0%} R5 {x['r5']:.0%} R20 {x['r20']:.0%} MRR {x['mrr20']:.2f}" if x else '—'
        return f"| {names[mode]} | {w:.1f} | {('нет' if not bn else f'топ-{bn} +{b}')} | {fmt(a)} | {fmt(f)} | {fmt(r)} |"
    print("\n| Каналы | вес FTS | бонус покрытия | все | известные | редкие |\n|---|---|---|---|---|---|")
    for row in rows[:15]: print(line(*row))
    print("\n… (лучшие 15 из %d сочетаний по MRR@20). Опорные точки:" % len(rows))
    for mode in modes:
        for w in (0.3, 0.6):
            m = evaluate(channels, cls_of, w, mode)
            print(line(mode, w, 0, 0.0, m))
    # только по одному каналу
    print("\nОдин канал:")
    for key, nm in (('fts_raw', 'FTS по запросу'), ('fts_and', 'FTS полное покрытие'), ('sem_raw', 'семантика по запросу'), ('fts_exp', 'FTS расширения'), ('sem_exp', 'семантика расширения')):
        rs = [ (ch[key].index(ch['film_id']) + 1 if ch['film_id'] in ch[key] else None) for ch in channels.values() if key in ch]
        if rs:
            n = len(rs)
            print(f"  {nm:24} H1 {sum(1 for r in rs if r == 1)/n:.0%}  R5 {sum(1 for r in rs if r and r <= 5)/n:.0%}  R20 {sum(1 for r in rs if r and r <= 20)/n:.0%}  найден {sum(1 for r in rs if r)/n:.0%}")


if __name__ == '__main__':
    main()
