#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Прогон поиска по эталонным фильмам во всех режимах → сводная таблица.

Кладётся в папку движка (рядом с film_search.py и gosfilmofond.db). Запуск:
    python test_search.py                 # два эталона по умолчанию, все 12 режимов, 1 прогон
    python test_search.py --repeat 3      # каждый режим 3 раза (реранкер и расширение недетерминированы)
    python test_search.py --fresh         # не переиспользовать расширение запроса между режимами
    python test_search.py --only-fast     # без режима thinking (быстрее и дешевле)

Режимы: расширение запроса (вкл/выкл) × FTS-гибрид (вкл/выкл) × реранкер (выкл / GPT-5.5 / GPT-5.5 thinking) = 12.
Пайплайн — тот же, что у веб-интерфейса (/search в film_search.py). По умолчанию расширение запроса и эмбеддинги
считаются один раз на запрос и переиспользуются во всех режимах, чтобы различия между режимами не тонули в случайности LLM.
Фиксируется: место фильма в показанном топ-5, место среди кандидатов до реранкера, уверенность реранкера, топ-1, время.
Результат: консоль + test_results_ГГГГММДД-ЧЧММ.md (таблица) и .json (подробности)."""
import argparse
import datetime
import json
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
import film_search as fs

TARGETS = [
    {"title": "Андрей Рублев", "year": 1966, "query": "средневековый живописец странствует по Руси и видит жестокость"},
    {"title": "Охотник из Лалвара", "year": 1966, "query": "охотник убивает дочь"},
]
RERANK_MODES = [("off", "выкл"), ("fast", "GPT-5.5"), ("thinking", "GPT-5.5 thinking")]


def find_target(conn, title, year):
    rows = conn.execute("SELECT film_id, title, year, studio FROM films WHERE title = ? ORDER BY year", (title,)).fetchall()
    if not rows:
        rows = conn.execute("SELECT film_id, title, year, studio FROM films WHERE title LIKE ? ORDER BY year", (f"%{title}%",)).fetchall()
    if not rows:
        sys.exit(f"Фильм «{title}» в базе не найден")
    if len(rows) > 1:
        exact = [r for r in rows if r[2] == year]
        rows = exact or rows
        if len(rows) > 1:
            print(f"  ! «{title}»: несколько записей {[(r[1], r[2]) for r in rows]} — беру первую")
    return rows[0]


def rank_of(items, film_id):
    for i, r in enumerate(items):
        if r.get("film_id") == film_id:
            return i + 1
    return None


def run_one(conn, client, query, expand, do_fts, rerank_mode):
    """Повторяет логику api_search из film_search.py."""
    do_rerank = rerank_mode != "off"
    effort = "medium" if rerank_mode == "thinking" else "none"
    fts_w, sem_w = fs.fusion_weights(do_rerank) if hasattr(fs, "fusion_weights") else ((0.3, 0.7) if do_rerank else (0.6, 0.4))
    t0 = time.time()
    if do_fts:
        candidates, variants = fs.hybrid_search(conn, client, query, limit=50, expand=expand,
                                                fts_weight=fts_w, sem_weight=sem_w)
    else:
        variants = fs.expand_query(client, query)[1] if expand else [query]
        candidates = fs.semantic_search(conn, fs._embed_queries(client, variants), limit=50)
    if do_rerank and candidates:
        results = fs.rerank(client, query, candidates, top_k=fs.TOP_RESULTS, effort=effort)
        if results is None:
            raise RuntimeError("реранкер недоступен (3 неудачные попытки)")
    else:
        results = candidates[:fs.TOP_RESULTS]
    return candidates, results, variants, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=fs.DB_PATH)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--fresh", action="store_true", help="не кэшировать расширение/эмбеддинги между режимами")
    ap.add_argument("--only-fast", action="store_true", help="пропустить режим thinking")
    args = ap.parse_args()

    conn = fs.open_db(args.db, schema=False)
    client = fs.get_openai_client()
    fs._load_index(conn)
    fs._get_morph()

    if not args.fresh:   # один раз на запрос: расширение и эмбеддинги вариантов
        _exp, _emb = {}, {}
        real_expand, real_embed = fs.expand_query, fs._embed_queries
        def cached_expand(c, q):
            if q not in _exp:
                _exp[q] = real_expand(c, q)
            return _exp[q]
        def cached_embed(c, qs):
            key = tuple(qs)
            if key not in _emb:
                _emb[key] = real_embed(c, qs)
            return _emb[key]
        fs.expand_query, fs._embed_queries = cached_expand, cached_embed

    modes = [(e, f, m) for e in (True, False) for f in (True, False) for m, _ in RERANK_MODES if not (args.only_fast and m == "thinking")]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    report, details = [], []
    for tg in TARGETS:
        fid, title, year, studio = find_target(conn, tg["title"], tg["year"])
        print(f"\n=== «{title}» ({year}, {studio}) — film_id {fid}\n    запрос: {tg['query']}")
        # диагностика каналов по отдельности (без реранкера)
        fts_raw = rank_of(fs.fts_search(conn, tg["query"], limit=150), fid)
        fq, variants = fs.expand_query(client, tg["query"])
        fts_exp = rank_of(fs.fts_search(conn, fq, limit=150), fid)
        sem_raw = rank_of(fs.semantic_search(conn, fs._embed_queries(client, [tg["query"]]), limit=50), fid)
        sem_exp = rank_of(fs.semantic_search(conn, fs._embed_queries(client, variants), limit=50), fid)
        print(f"    каналы: FTS по запросу → {fts_raw or '—'}; FTS по ключевым словам расширения ({fq!r}) → {fts_exp or '—'}; "
              f"семантика по запросу → {sem_raw or '—'}; семантика по {len(variants)} вариантам → {sem_exp or '—'}")
        rows = []
        for expand, do_fts, mode in modes:
            label = dict(RERANK_MODES)[mode]
            reps = []
            for k in range(args.repeat):
                cands, results, variants_used, dt = run_one(conn, client, tg["query"], expand, do_fts, mode)
                r_top = rank_of(results, fid); r_cand = rank_of(cands, fid)
                conf = next((r.get("confidence") for r in results if r.get("film_id") == fid), None)
                top1 = f"{results[0]['title']} ({results[0]['year']})" if results else "—"
                reps.append({"top5": r_top, "cand": r_cand, "conf": conf, "top1": top1, "sec": round(dt, 1), "n_cand": len(cands)})
                print(f"    расширение={'да' if expand else 'нет':3} FTS={'да' if do_fts else 'нет':3} реранкер={label:16} → "
                      f"топ-5: {r_top or '—'}  кандидаты: {r_cand or '—'}/{len(cands)}  {conf or ''}  топ-1: {top1}  [{dt:.1f} с]")
            rows.append({"expand": expand, "fts": do_fts, "rerank": label, "reps": reps})
        report.append({"title": title, "year": year, "film_id": fid, "query": tg["query"], "rows": rows,
                       "channels": {"fts_raw": fts_raw, "fts_expanded": fts_exp, "fts_query": fq, "sem_raw": sem_raw, "sem_expanded": sem_exp}})

    # ── сводная таблица ──
    def cell(reps, key):
        vals = [r[key] for r in reps]
        return "/".join("—" if v is None else str(v) for v in vals)
    L = [f"# Прогон поиска — {stamp}", "",
         f"База: {args.db}; режимов: {len(modes)}; повторов: {args.repeat}; расширение/эмбеддинги {'считались заново в каждом режиме' if args.fresh else 'считались один раз на запрос'}.",
         "Место — позиция фильма в показанном топ-5 («—» = не показан); «канд.» — позиция среди кандидатов до реранкера (их 50–70); «/» разделяет повторы.", ""]
    head = "| Расширение | FTS | Реранкер | " + " | ".join(f"{r['title']}: место | канд. | уверенность | с" for r in report) + " |"
    L += [head, "|" + "---|" * (3 + 4 * len(report))]
    for i in range(len(modes)):
        r0 = report[0]["rows"][i]
        line = f"| {'да' if r0['expand'] else 'нет'} | {'да' if r0['fts'] else 'нет'} | {r0['rerank']} | "
        line += " | ".join(f"**{cell(r['rows'][i]['reps'], 'top5')}** | {cell(r['rows'][i]['reps'], 'cand')} | "
                           f"{'/'.join((x['conf'] or '—') for x in r['rows'][i]['reps'])} | {cell(r['rows'][i]['reps'], 'sec')}" for r in report)
        L.append(line + " |")
    L += [""]
    for r in report:
        hits = sum(1 for row in r["rows"] for x in row["reps"] if x["top5"])
        total = sum(len(row["reps"]) for row in r["rows"])
        ch = r["channels"]
        L.append(f"- **{r['title']}** ({r['year']}), запрос «{r['query']}»: в топ-5 в {hits} из {total} прогонов. "
                 f"Каналы по отдельности: FTS по запросу — {ch['fts_raw'] or '—'}, FTS по ключевым словам расширения «{ch['fts_query']}» — {ch['fts_expanded'] or '—'}, "
                 f"семантика по запросу — {ch['sem_raw'] or '—'}, семантика по вариантам расширения — {ch['sem_expanded'] or '—'}.")
    L += ["", "## Топ-1 по режимам", ""]
    for r in report:
        L.append(f"**{r['title']}**")
        for row in r["rows"]:
            L.append(f"- расширение {'да' if row['expand'] else 'нет'}, FTS {'да' if row['fts'] else 'нет'}, реранкер {row['rerank']}: " + "; ".join(x["top1"] for x in row["reps"]))
        L.append("")
    md = "\n".join(L)
    open(f"test_results_{stamp}.md", "w", encoding="utf-8").write(md)
    json.dump(report, open(f"test_results_{stamp}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n" + md)
    print(f"\nСохранено: test_results_{stamp}.md, test_results_{stamp}.json")
    conn.close()


if __name__ == "__main__":
    main()
