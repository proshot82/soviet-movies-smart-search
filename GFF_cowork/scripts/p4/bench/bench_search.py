#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Бенчмарк поиска по эталонному набору (bench_set.json) с метриками по профилям.

Кладётся в папку движка (рядом с film_search.py, gosfilmofond.db, bench_set.json). Запуск:
    python bench_search.py                        # профили по умолчанию: default (как в интерфейсе), expand, norerank, nofts
    python bench_search.py --profiles default,norerank   # только то, что меняли
    python bench_search.py --limit 10             # быстрая проба на первых 10 запросах
    python bench_search.py --profiles default,expand,norerank,nofts,thinking   # выбор профилей (all = все 12 сочетаний)
    python bench_search.py --classes rare --styles vague,wrong                 # срез набора
    python bench_search.py --repeat 2             # повторы (реранкер недетерминирован)

Профили = сочетания: расширение запроса (E) × FTS-гибрид (F) × реранкер (R: off/fast/thinking).
Пайплайн — тот же, что у веб-интерфейса (/search в film_search.py); веса слияния берутся из film_search.fusion_weights().
Расширение и эмбеддинги запроса считаются один раз на запрос и переиспользуются всеми профилями
(иначе различия между профилями тонут в случайности LLM).

Метрики (по профилю, в целом и в разрезе класс/стиль):
  Recall@20 — фильм среди первых 20 кандидатов после слияния (до реранкера); Recall@all — среди всех кандидатов (50–70);
  Hit@1, Hit@5 — фильм на 1-м месте / в показанном топ-5; MRR@5 — средний 1/место в топ-5 (0, если не показан);
  задержка — медиана и p90 полного запроса (без расширения и эмбеддингов запроса — они кэшируются); токены по моделям
  (стоимость — если заданы цены в PRICES). Калибровка: сколько раз метка «наиболее вероятно» стояла на неверном топ-1 и на верном.
Если у запроса в bench_set.json есть "also_ok" (другие фильмы базы, одинаково подходящие под запрос — вторая экранизация
той же пьесы и т.п.), попадание засчитывается по лучшему из них; такие случаи перечисляются отдельно в отчёте.
Снимки каналов (списки film_id: FTS по запросу и по ключевым словам расширения, семантика по запросу и по вариантам)
сохраняются в JSON — на них bench_tune.py подбирает веса слияния без обращения к API.

Результат: bench_results_ГГГГММДД-ЧЧММ.md (таблицы), .json (всё), .csv (по одной строке на прогон — для Excel)."""
import argparse
import csv
import datetime
import json
import statistics
import sys
import time
import traceback

sys.stdout.reconfigure(encoding='utf-8')
import film_search as fs

# Цены за 1 млн токенов (USD): None — стоимость не считается, только токены. Эмбеддинг — как в film_search.py.
# Для gpt-5.5 и gpt-5.4-nano цены не заданы: на странице цен OpenAI (проверено 04.09.2026) этих моделей уже нет —
# впиши числа из своего биллинга, если нужна стоимость в отчёте.
PRICES = {
    fs.EMBEDDING_MODEL: {'in': 0.13, 'out': 0.0},
    fs.QUERY_EXPAND_MODEL: {'in': None, 'out': None},
    fs.RERANK_MODEL: {'in': None, 'out': None},
}
PROFILES = {   # ключ: (expand, fts, rerank_mode, подпись)
    'default':   (False, True,  'fast',     'по умолчанию: F+R'),
    'expand':    (True,  True,  'fast',     'с расширением: E+F+R'),
    'norerank':  (False, True,  'off',      'без реранкера: F'),
    'nofts':     (False, False, 'fast',     'только семантика: R'),
    'thinking':  (False, True,  'thinking', 'thinking-реранкер: F+Rt'),
}
PROFILE_ALIASES = {'current': 'expand', 'noexpand': 'default'}   # имена из прошлых прогонов
ALL_MODES = {f"E{int(e)}F{int(f)}R{m}": (e, f, m, f"E={'да' if e else 'нет'} F={'да' if f else 'нет'} R={m}")
             for e in (True, False) for f in (True, False) for m in ('off', 'fast', 'thinking')}


class Usage:
    """Обёртка над клиентом OpenAI: считает токены по моделям, остальное передаёт как есть."""
    def __init__(self, real):
        self.real = real; self.by_model = {}
        outer = self
        class _Completions:
            def create(self, **kw):
                r = outer.real.chat.completions.create(**kw); outer.add(kw.get('model'), r); return r
        class _Chat:
            completions = _Completions()
        class _Embeddings:
            def create(self, **kw):
                r = outer.real.embeddings.create(**kw); outer.add(kw.get('model'), r); return r
        self.chat = _Chat(); self.embeddings = _Embeddings()
    def add(self, model, r):
        u = getattr(r, 'usage', None); d = self.by_model.setdefault(model, {'calls': 0, 'in': 0, 'out': 0})
        d['calls'] += 1
        if u is not None:
            d['in'] += getattr(u, 'prompt_tokens', 0) or 0
            d['out'] += getattr(u, 'completion_tokens', 0) or 0
    def snapshot(self):
        return {m: dict(v) for m, v in self.by_model.items()}
    @staticmethod
    def diff(a, b):
        out = {}
        for m in set(a) | set(b):
            x, y = a.get(m, {'calls': 0, 'in': 0, 'out': 0}), b.get(m, {'calls': 0, 'in': 0, 'out': 0})
            out[m] = {k: y[k] - x[k] for k in ('calls', 'in', 'out')}
        return out
    @staticmethod
    def cost(d):
        total = 0.0; unknown = False
        for m, v in d.items():
            p = PRICES.get(m)
            if p and p['in'] is not None:
                total += v['in'] / 1e6 * p['in'] + v['out'] / 1e6 * (p['out'] or 0)
            elif v['calls']:
                unknown = True
        return total, unknown


def find_target(conn, x):
    rows = conn.execute("SELECT film_id, title, year FROM films WHERE title = ? AND year = ?", (x['title'], x['year'])).fetchall()
    if not rows:
        rows = conn.execute("SELECT film_id, title, year FROM films WHERE title = ?", (x['title'],)).fetchall()
    if not rows:
        rows = conn.execute("SELECT film_id, title, year FROM films WHERE title LIKE ? AND year = ?", (f"%{x['title']}%", x['year'])).fetchall()
    return rows[0][0] if rows else None


def rank_of(items, fid):
    for i, r in enumerate(items):
        if (r.get('film_id') if isinstance(r, dict) else r) == fid:
            return i + 1
    return None


def best_rank(items, fids):
    """Лучшее место среди принимаемых фильмов (цель + also_ok): (место, film_id) или (None, None)."""
    best = (None, None)
    for fid in fids:
        r = rank_of(items, fid)
        if r and (best[0] is None or r < best[0]):
            best = (r, fid)
    return best


def run_pipeline(conn, client, query, expand, do_fts, rerank_mode):
    """Повторяет api_search из film_search.py; возвращает (candidates, results, variants, t_total, t_rerank)."""
    do_rerank = rerank_mode != 'off'
    effort = 'medium' if rerank_mode == 'thinking' else 'none'
    if hasattr(fs, 'fusion_weights'):
        fts_w, sem_w = fs.fusion_weights(do_rerank)
    else:   # старый film_search.py без fusion_weights()
        fts_w, sem_w = (0.3, 0.7) if do_rerank else (0.6, 0.4)
    t0 = time.time()
    if do_fts:
        candidates, variants = fs.hybrid_search(conn, client, query, limit=50, expand=expand, fts_weight=fts_w, sem_weight=sem_w)
    else:
        variants = fs.expand_query(client, query)[1] if expand else [query]
        candidates = fs.semantic_search(conn, fs._embed_queries(client, variants), limit=50)
    t1 = time.time()
    if do_rerank and candidates:
        results = fs.rerank(client, query, candidates, top_k=fs.TOP_RESULTS, effort=effort)
        if results is None:   # реранкер недоступен — движок показал бы запасной порядок; в отчёте это ошибка прогона
            raise RuntimeError('реранкер недоступен (3 неудачные попытки)')
    else:
        results = candidates[:fs.TOP_RESULTS]
    t2 = time.time()
    return candidates, results, variants, t2 - t0, t2 - t1


def fts_and(conn, query, limit=150):
    """Только первый ярус FTS: все содержательные леммы запроса присутствуют (для проверки «бонуса за полное покрытие» в bench_tune.py)."""
    import re
    cleaned = fs.lemmatize_text(re.sub(r'[_\W]+', ' ', query, flags=re.UNICODE))
    tokens = [t for t in cleaned.split() if len(t) >= 2 and t not in fs._RU_STOP and t.upper() not in ('AND', 'OR', 'NOT', 'NEAR')]
    if not tokens: return []
    try:
        rows = conn.execute("SELECT rowid FROM films_fts WHERE films_fts MATCH ? ORDER BY rank LIMIT ?", (' '.join(f'{t}*' for t in tokens), limit)).fetchall()
    except Exception:
        return []
    return [r[0] for r in rows]


def pct(a, b): return f"{100.0 * a / b:.0f}%" if b else '—'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=fs.DB_PATH)
    ap.add_argument('--set', default='bench_set.json')
    ap.add_argument('--profiles', default='default,expand,norerank,nofts')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--classes', default='')
    ap.add_argument('--styles', default='')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--fresh', action='store_true', help='не кэшировать расширение/эмбеддинги между профилями')
    args = ap.parse_args()

    if args.profiles == 'all':
        profiles = ALL_MODES
    else:
        profiles = {}
        for k in args.profiles.split(','):
            k = PROFILE_ALIASES.get(k.strip(), k.strip())
            if k in PROFILES: profiles[k] = PROFILES[k]
            elif k in ALL_MODES: profiles[k] = ALL_MODES[k]
            else: sys.exit(f'неизвестный профиль: {k} (доступны: {", ".join(PROFILES)} или коды вида E1F1Rfast, all)')
    items = json.load(open(args.set, encoding='utf-8'))
    if args.classes: items = [x for x in items if x['class'] in args.classes.split(',')]
    if args.styles: items = [x for x in items if x['style'] in args.styles.split(',')]
    if args.limit: items = items[:args.limit]

    conn = fs.open_db(args.db, schema=False)
    client = Usage(fs.get_openai_client())
    fs._load_index(conn); fs._get_morph()
    if not args.fresh:
        _exp, _emb = {}, {}
        real_expand, real_embed = fs.expand_query, fs._embed_queries
        def cached_expand(c, q):
            if q not in _exp: _exp[q] = real_expand(c, q)
            return _exp[q]
        def cached_embed(c, qs):
            key = tuple(qs)
            if key not in _emb: _emb[key] = real_embed(c, qs)
            return _emb[key]
        fs.expand_query, fs._embed_queries = cached_expand, cached_embed

    need_expand = any(p[0] for p in profiles.values())
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    rows, channels, snap_usage = [], {}, {}
    print(f"Набор: {len(items)} запросов; профили: {', '.join(profiles)}; повторов: {args.repeat}\n")
    for x in items:
        fid = find_target(conn, x)
        if fid is None:
            print(f"!! #{x['n']} «{x['title']}» ({x['year']}) не найден в базе — пропуск"); continue
        # принимаемые ответы: цель + also_ok (другие фильмы базы, одинаково подходящие под запрос)
        accepted = [fid]
        alt_names = {}
        for alt in x.get('also_ok') or []:
            afid = find_target(conn, alt)
            if afid is None:
                print(f"!! #{x['n']}: also_ok «{alt.get('title')}» ({alt.get('year')}) не найден в базе — не учитывается")
            elif afid not in accepted:
                accepted.append(afid); alt_names[afid] = f"{alt.get('title')} ({alt.get('year')})"
        q = x['query']
        # снимки каналов (для bench_tune.py): списки film_id по убыванию
        ch = {}
        u_snap0 = client.snapshot()
        try:
            ch['fts_raw'] = [r['film_id'] for r in fs.fts_search(conn, q, limit=150)]
            ch['fts_and'] = fts_and(conn, q)
            sem = fs.semantic_search(conn, fs._embed_queries(client, [q]), limit=50)
            ch['sem_raw'] = [r['film_id'] for r in sem]; ch['sem_raw_scores'] = [round(r['sem_score'], 4) for r in sem]
            if need_expand:
                fq, variants = fs.expand_query(client, q)
                ch['fts_query'] = fq; ch['variants'] = variants
                ch['fts_exp'] = [r['film_id'] for r in fs.fts_search(conn, fq, limit=150)]
                sem2 = fs.semantic_search(conn, fs._embed_queries(client, variants), limit=50)
                ch['sem_exp'] = [r['film_id'] for r in sem2]; ch['sem_exp_scores'] = [round(r['sem_score'], 4) for r in sem2]
        except Exception as e:
            ch['error'] = str(e)
        channels[x['n']] = {'film_id': fid, **ch}
        for m, v in Usage.diff(u_snap0, client.snapshot()).items():
            d = snap_usage.setdefault(m, {'calls': 0, 'in': 0, 'out': 0})
            for k in d: d[k] += v[k]
        cr = {k: rank_of(ch.get(k, []), fid) for k in ('fts_raw', 'fts_exp', 'sem_raw', 'sem_exp')}
        print(f"#{x['n']:>2} [{x['class']}/{x['style']}] «{x['title']}» ({x['year']}) — каналы: FTS {cr['fts_raw'] or '—'}"
              + (f"/{cr['fts_exp'] or '—'}" if need_expand else '') + f", сем. {cr['sem_raw'] or '—'}" + (f"/{cr['sem_exp'] or '—'}" if need_expand else ''))
        for pk, (expand, do_fts, mode, label) in profiles.items():
            for rep in range(args.repeat):
                u0 = client.snapshot()
                row = {'n': x['n'], 'class': x['class'], 'style': x['style'], 'title': x['title'], 'year': x['year'], 'film_id': fid,
                       'title_in_query': x.get('title_in_query', False), 'profile': pk, 'rep': rep + 1}
                try:
                    cands, results, variants, dt, dt_rr = run_pipeline(conn, client, q, expand, do_fts, mode)
                    top1 = results[0] if results else None
                    cand_rank, _ = best_rank(cands, accepted)
                    top5_rank, hit_fid = best_rank(results, accepted)
                    row.update({'cand_rank': cand_rank, 'n_cand': len(cands), 'top5_rank': top5_rank,
                                'target_cand_rank': rank_of(cands, fid), 'target_top5_rank': rank_of(results, fid),
                                'conf_target': next((r.get('confidence') for r in results if r.get('film_id') == hit_fid), None),
                                'top1': f"{top1['title']} ({top1['year']})" if top1 else None, 'top1_conf': top1.get('confidence') if top1 else None,
                                'top1_correct': bool(top1 and top1.get('film_id') in accepted),
                                'alt_hit': alt_names.get(hit_fid) if hit_fid in alt_names else None,
                                'sec': round(dt, 1), 'sec_rerank': round(dt_rr, 1),
                                'usage': Usage.diff(u0, client.snapshot()), 'error': None})
                except Exception as e:
                    row.update({'cand_rank': None, 'n_cand': 0, 'top5_rank': None, 'target_cand_rank': None, 'target_top5_rank': None,
                                'conf_target': None, 'top1': None, 'top1_conf': None, 'top1_correct': False, 'alt_hit': None,
                                'sec': None, 'sec_rerank': None, 'usage': Usage.diff(u0, client.snapshot()), 'error': f'{type(e).__name__}: {e}'})
                    traceback.print_exc()
                rows.append(row)
                print(f"      {pk:10} → канд. {row['cand_rank'] or '—'}/{row['n_cand']}  топ-5: {row['top5_rank'] or '—'}  топ-1: {row['top1']}"
                      f"{' [' + row['top1_conf'] + ']' if row['top1_conf'] else ''}  {row['sec']} с"
                      + (f"  (засчитан {row['alt_hit']})" if row['alt_hit'] else '') + (f"  ОШИБКА {row['error']}" if row['error'] else ''))

    # ── метрики ──
    def metrics(rs):
        n = len(rs)
        if not n: return None
        secs = sorted(r['sec'] for r in rs if r['sec'] is not None)
        return {'n': n,
                'recall20': sum(1 for r in rs if r['cand_rank'] and r['cand_rank'] <= 20), 'recall_all': sum(1 for r in rs if r['cand_rank']),
                'hit1': sum(1 for r in rs if r['top5_rank'] == 1), 'hit5': sum(1 for r in rs if r['top5_rank']),
                'mrr5': sum(1.0 / r['top5_rank'] for r in rs if r['top5_rank']) / n,
                'sec_med': statistics.median(secs) if secs else None, 'sec_p90': (secs[min(len(secs) - 1, int(round(0.9 * (len(secs) - 1))))] if secs else None),
                'conf_wrong_high': sum(1 for r in rs if r['top1'] and not r['top1_correct'] and r['top1_conf'] == 'наиболее вероятно'),
                'conf_right_high': sum(1 for r in rs if r['top1_correct'] and r['top1_conf'] == 'наиболее вероятно'),
                'wrong_top1': sum(1 for r in rs if r['top1'] and not r['top1_correct']), 'errors': sum(1 for r in rs if r['error'])}
    def usage_sum(rs):
        tot = {}
        for r in rs:
            for m, v in r['usage'].items():
                d = tot.setdefault(m, {'calls': 0, 'in': 0, 'out': 0})
                for k in d: d[k] += v[k]
        return tot
    w_r, w_n = (fs.fusion_weights(True)[0], fs.fusion_weights(False)[0]) if hasattr(fs, 'fusion_weights') else (0.3, 0.6)
    settings = f"веса FTS в слиянии: {w_r} с реранкером / {w_n} без; аннотация для реранкера: {getattr(fs, 'RERANK_ANN_CHARS', 500)} символов; реранкер {fs.RERANK_MODEL}; расширение {fs.QUERY_EXPAND_MODEL}"
    L = [f"# Бенчмарк поиска — {stamp}", "",
         f"База: {args.db}; набор: {args.set} ({len(items)} запросов; {sum(1 for x in items if x['class']=='famous')} известных / {sum(1 for x in items if x['class']=='rare')} редких); "
         f"профили: {', '.join(f'{k} ({v[3]})' for k, v in profiles.items())}; повторов: {args.repeat}. Расширение/эмбеддинги {'считались заново' if args.fresh else 'считались один раз на запрос'}.", "",
         f"Настройки движка: {settings}.", "",
         "Recall@20 / Recall@all — фильм среди первых 20 / среди всех кандидатов после слияния (до реранкера); Hit@1 / Hit@5 — на 1-м месте / в показанном топ-5; "
         "MRR@5 — средний 1/место; задержка — медиана / p90 полного запроса; «увер. ошиб.» — на скольких неверных топ-1 стояло «наиболее вероятно» (из всех неверных топ-1); «увер. верн.» — на скольких верных.", ""]
    def table(title, groups):
        L.append(f"## {title}"); L.append("")
        L.append("| Профиль | n | Recall@20 | Recall@all | Hit@1 | Hit@5 | MRR@5 | задержка мед./p90 | увер. ошиб. | увер. верн. | ошибки |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for name, rs in groups:
            m = metrics(rs)
            if not m: continue
            L.append(f"| {name} | {m['n']} | {pct(m['recall20'], m['n'])} | {pct(m['recall_all'], m['n'])} | {pct(m['hit1'], m['n'])} | {pct(m['hit5'], m['n'])} | {m['mrr5']:.2f} | "
                     f"{m['sec_med'] if m['sec_med'] is not None else '—'} / {m['sec_p90'] if m['sec_p90'] is not None else '—'} с | {m['conf_wrong_high']}/{m['wrong_top1']} | {m['conf_right_high']}/{m['hit1']} | {m['errors']} |")
        L.append("")
    table("Итог по профилям", [(profiles[pk][3], [r for r in rows if r['profile'] == pk]) for pk in profiles])
    for cls in ('famous', 'rare'):
        table(f"Класс: {'известные' if cls == 'famous' else 'редкие'}", [(profiles[pk][3], [r for r in rows if r['profile'] == pk and r['class'] == cls]) for pk in profiles])
    STYLES = {'precise': 'точное описание', 'vague': 'расплывчатое', 'wrong': 'одна неверная деталь', 'noisy': 'форумное с шумом', 'formula': 'в аннотации только формула источника'}
    for st, sname in STYLES.items():
        if any(r['style'] == st for r in rows):
            table(f"Стиль: {sname}", [(profiles[pk][3], [r for r in rows if r['profile'] == pk and r['style'] == st]) for pk in profiles])
    # каналы по отдельности
    L.append("## Каналы по отдельности (место фильма; без реранкера)"); L.append("")
    def chan_metrics(key):
        rs = [rank_of(channels[n].get(key, []), channels[n]['film_id']) for n in channels if key in channels[n]]
        if not rs: return None
        return len(rs), sum(1 for r in rs if r and r <= 1), sum(1 for r in rs if r and r <= 5), sum(1 for r in rs if r and r <= 20), sum(1 for r in rs if r), sum(1.0 / r for r in rs if r) / len(rs)
    L.append("| Канал | n | место 1 | в топ-5 | в топ-20 | найден | MRR |"); L.append("|---|---|---|---|---|---|---|")
    for key, name in (('fts_raw', 'FTS по запросу (топ-150)'), ('fts_exp', 'FTS по ключевым словам расширения'), ('sem_raw', 'семантика по запросу (топ-50)'), ('sem_exp', 'семантика по вариантам расширения')):
        cm = chan_metrics(key)
        if cm: L.append(f"| {name} | {cm[0]} | {pct(cm[1], cm[0])} | {pct(cm[2], cm[0])} | {pct(cm[3], cm[0])} | {pct(cm[4], cm[0])} | {cm[5]:.2f} |")
    L.append("")
    # токены и стоимость
    L.append("## Токены и стоимость по профилям (суммарно за прогон)"); L.append("")
    L.append("| Профиль | модель | вызовов | токены вход | токены выход | стоимость |"); L.append("|---|---|---|---|---|---|")
    for pk in profiles:
        tot = usage_sum([r for r in rows if r['profile'] == pk])
        for m, v in sorted(tot.items()):
            c, unk = Usage.cost({m: v})
            L.append(f"| {profiles[pk][3]} | {m} | {v['calls']} | {v['in']:,} | {v['out']:,} | {'укажи цену в PRICES' if unk else f'${c:.3f}'} |")
    for m, v in sorted(snap_usage.items()):
        c, unk = Usage.cost({m: v})
        L.append(f"| снимки каналов (расширение + эмбеддинги запроса, один раз на запрос) | {m} | {v['calls']} | {v['in']:,} | {v['out']:,} | {'укажи цену в PRICES' if unk else f'${c:.3f}'} |")
    L.append("")
    L.append("Примечание: расширение запроса и эмбеддинги кэшируются и считаются в строке «снимки каналов»; в профилях учтены только их собственные вызовы (реранкер). Полный итог токенов — в JSON (usage_total).")
    L.append("")
    # неверный топ-1 (фильм показан, но не первым) и провалы (не показан в топ-5)
    L.append("## Неверный топ-1 (фильм в топ-5, но не первым) — по профилям"); L.append("")
    for pk in profiles:
        wrong = [r for r in rows if r['profile'] == pk and r['top5_rank'] and r['top5_rank'] > 1]
        L.append(f"**{profiles[pk][3]}** — {len(wrong)}:")
        for r in wrong:
            L.append(f"- #{r['n']} «{r['title']}» ({r['year']}) [{r['class']}/{r['style']}]: место {r['top5_rank']} [{r['conf_target']}], кандидат {r['cand_rank'] or '—'}/{r['n_cand']}, топ-1 {r['top1']}" + (f" [{r['top1_conf']}]" if r['top1_conf'] else ''))
        L.append("")
    L.append("## Провалы (фильм не показан в топ-5) — по профилям"); L.append("")
    for pk in profiles:
        fails = [r for r in rows if r['profile'] == pk and not r['top5_rank']]
        L.append(f"**{profiles[pk][3]}** — {len(fails)}:")
        for r in fails:
            L.append(f"- #{r['n']} «{r['title']}» ({r['year']}) [{r['class']}/{r['style']}]: кандидат {r['cand_rank'] or '—'}/{r['n_cand']}, топ-1 {r['top1']}" + (f" [{r['top1_conf']}]" if r['top1_conf'] else '') + (f", ошибка: {r['error']}" if r['error'] else ''))
        L.append("")
    alts = [r for r in rows if r.get('alt_hit')]
    if alts:
        L.append("## Засчитано по альтернативному ответу (also_ok в наборе)"); L.append("")
        for r in alts:
            L.append(f"- #{r['n']} «{r['title']}» ({r['year']}) [{r['profile']}]: засчитан «{r['alt_hit']}» на месте {r['top5_rank']}; сама цель — место {r['target_top5_rank'] or '—'} в топ-5, {r['target_cand_rank'] or '—'} среди кандидатов")
        L.append("")
    md = "\n".join(L)
    open(f'bench_results_{stamp}.md', 'w', encoding='utf-8').write(md)
    json.dump({'meta': {'stamp': stamp, 'db': args.db, 'set': args.set, 'profiles': {k: v for k, v in profiles.items()}, 'repeat': args.repeat, 'fresh': args.fresh, 'k_rrf': 60,
                        'settings': settings},
               'rows': rows, 'channels': channels, 'usage_total': client.snapshot()}, open(f'bench_results_{stamp}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(f'bench_results_{stamp}.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['n', 'класс', 'стиль', 'название', 'год', 'профиль', 'повтор', 'кандидат', 'кандидатов', 'топ-5', 'уверенность цели', 'топ-1', 'уверенность топ-1', 'топ-1 верен', 'засчитан альтернативный', 'сек', 'сек реранкер', 'ошибка'])
        for r in rows:
            w.writerow([r['n'], r['class'], r['style'], r['title'], r['year'], r['profile'], r['rep'], r['cand_rank'], r['n_cand'], r['top5_rank'], r['conf_target'], r['top1'], r['top1_conf'], int(r['top1_correct']), r.get('alt_hit') or '', r['sec'], r['sec_rerank'], r['error']])
    print("\n" + md)
    print(f"\nСохранено: bench_results_{stamp}.md / .json / .csv")
    conn.close()


if __name__ == '__main__':
    main()
