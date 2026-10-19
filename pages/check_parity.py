#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка браузерного движка (docs/engine.js) с Python-движком (film_search.py) на собранных данных.

    python pages/check_parity.py          # нужен node ≥ 22 и база gosfilmofond.db

Проверяется без обращений к API:
  лемматизация — запрос → леммы, как lemmatize_text();
  FTS          — списки film_id из fts_search() (с фильтрами и без) должны совпасть один в один;
  семантика    — semantic_search() по тем же 4-битным векторам, что лежат в docs/data
                 (вектор запроса — эмбеддинг случайного чанка), совпадение порядка и косинусов;
  гибрид       — hybrid_search(): кандидаты и их места в каналах.
"""
import gzip
import json
import random
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import film_search as fs  # noqa: E402

DATA = ROOT / "docs" / "data"
manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
conn = sqlite3.connect(f"file:{ROOT / fs.DB_PATH}?mode=ro&immutable=1", uri=True, check_same_thread=False)
conn.create_function("lc", 1, fs._lc, deterministic=True)
rnd = random.Random(42)

# ── Векторы из docs/data → кэш индекса Python-движка (те же числа, что видит браузер) ──
n, dims = manifest["chunks"], manifest["dims"]
blob = gzip.decompress((DATA / manifest["files"]["vectors"]["file"]).read_bytes())
scales = np.frombuffer(blob, np.float32, n, 0)
film_of = np.frombuffer(blob, np.uint16, n, n * 4)
packed = np.frombuffer(blob, np.uint8, n * dims // 2, n * 6).reshape(n, dims // 2)
lo, hi = (packed & 15).astype(np.int8), (packed >> 4).astype(np.int8)
q = np.empty((n, dims), np.int8)
q[:, 0::2] = np.where(lo >= 8, lo - 16, lo)
q[:, 1::2] = np.where(hi >= 8, hi - 16, hi)
vecs = q.astype(np.float32) * scales[:, None]
film_ids = [r[0] for r in conn.execute("SELECT film_id FROM films ORDER BY film_id")]
chunk_to_film = {i: film_ids[f] for i, f in enumerate(film_of)}
fs._cached_vecs, fs._cached_chunk_ids, fs._cached_chunk_to_film = vecs, list(range(n)), chunk_to_film
fs._build_film_index(fs._cached_chunk_ids, chunk_to_film)

# ── Запросы ──
bench = json.loads((ROOT / "GFF_cowork/scripts/p4/bench/bench_set.json").read_text(encoding="utf-8"))
queries = [b["query"] for b in bench]
anns = [a for (a,) in conn.execute("SELECT annotation FROM films WHERE length(annotation) > 200")]
for _ in range(300):   # случайные обрывки аннотаций: 2–7 слов, в разных формах
    words = re.findall(r"\w+", rnd.choice(anns))
    i = rnd.randrange(max(1, len(words) - 7))
    queries.append(" ".join(words[i:i + rnd.randint(2, 7)]))
queries += ["Ёлка", "елка", "ёжик в тумане", "Иван Грозный", "1941", "кот", "по на в", "", "!!!", "Мосфильм 1973"]
filter_sets = [{}, {"year": 1960}, {"studio": "Мосфильм"}, {"genre": "комедия"},
               {"year": 1930, "studio": "Ленфильм", "genre": "драма"}, {"kind": "телефильм"},
               {"kind": "фильм-спектакль", "year": 1980}, {"year": 1990}]

fts_tasks = [{"query": q, "limit": 150, "filters": filter_sets[i % len(filter_sets)]} for i, q in enumerate(queries)]
sem_tasks, hybrid_tasks = [], []
for i in range(60):
    c = rnd.randrange(n)
    v = vecs[c] + np.random.default_rng(i).normal(0, 0.02, dims).astype(np.float32)   # «похожий» запрос
    f = filter_sets[i % len(filter_sets)]
    sem_tasks.append({"vec": v.tolist(), "limit": 50, "filters": f})
    hybrid_tasks.append({"query": queries[i], "vec": v.tolist(), "filters": f, "w": list(fs.fusion_weights(i % 2 == 0))})

tasks = {"lemmas": queries, "fts": fts_tasks, "sem": sem_tasks, "hybrid": hybrid_tasks}
res = subprocess.run(["node", str(ROOT / "pages" / "parity.mjs")], input=json.dumps(tasks),
                     capture_output=True, text=True, encoding="utf-8")
if res.returncode:
    sys.exit(res.stderr)
js = json.loads(res.stdout)

fails = 0


def report(name, total, bad, examples):
    global fails
    fails += bad
    print(f"{name:12s} {total - bad}/{total} совпало" + ("" if not bad else f"  ← расхождения, примеры: {examples[:3]}"))


# Словарь словоформ в браузере знает только слова, чья лемма есть в каталоге; у остальных слов лемма
# может разойтись, но поиску это безразлично, если ни один терм индекса не начинается с леммы Python.
vocab = json.loads(gzip.decompress((DATA / manifest["files"]["fts"]["file"]).read_bytes()))["terms"]


def has_prefix(p):
    import bisect
    i = bisect.bisect_left(vocab, p)
    return i < len(vocab) and vocab[i].startswith(p)


bad, harmless, ex = 0, 0, []
for qtext, got in zip(queries, js["lemmas"]):
    want = fs.lemmatize_text(re.sub(r"[_\W]+", " ", qtext))
    if got != want:
        diff = [w for w, g in zip(want.split(), got.split()) if w != g]
        if len(want.split()) == len(got.split()) and not any(has_prefix(w) for w in diff):
            harmless += 1
            continue
        bad += 1
        ex.append((qtext, want, got))
report("леммы", len(queries), bad, ex)
if harmless:
    print(f"{'':12s} ещё в {harmless} запросах лемма другая у слов, которых нет в каталоге (на поиск не влияет)")

bad, ex = 0, []
for t, got in zip(fts_tasks, js["fts"]):
    want = [r["film_id"] for r in fs.fts_search(conn, t["query"], limit=t["limit"], **t["filters"])]
    if got != want:
        bad += 1
        k = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
        ex.append((t["query"], t["filters"], f"с позиции {k}", want[k:k + 3], got[k:k + 3], len(want), len(got)))
report("FTS", len(fts_tasks), bad, ex)

bad, ex = 0, []
for t, got in zip(sem_tasks, js["sem"]):
    want = fs.semantic_search(conn, [np.array(t["vec"], np.float32)], limit=t["limit"], **t["filters"])
    ids_w, ids_g = [r["film_id"] for r in want], [g[0] for g in got]
    diff = max((abs(r["sem_score"] - g[1]) for r, g in zip(want, got)), default=0)
    # порядок может разойтись только на почти равных косинусах (float32 в numpy против float64 в JS)
    if ids_w != ids_g or diff > 1e-4:
        close = len(ids_w) == len(ids_g) and set(ids_w) == set(ids_g) and diff <= 1e-4
        if not close:
            bad += 1
            ex.append((ids_w[:5], ids_g[:5], diff))
report("семантика", len(sem_tasks), bad, ex)

bad, ex = 0, []
for t, got in zip(hybrid_tasks, js["hybrid"]):
    fs._embed_queries = lambda client, variants, v=t["vec"]: [np.array(v, np.float32)]
    want, _ = fs.hybrid_search(conn, None, t["query"], limit=50, expand=False,
                               fts_weight=t["w"][0], sem_weight=t["w"][1], **t["filters"])
    w = [[r["film_id"], r["fts_rank"], r["sem_rank"]] for r in want]
    if w != got:
        bad += 1
        ex.append((t["query"], w[:3], got[:3]))
report("гибрид", len(hybrid_tasks), bad, ex)

print("OK" if not fails else f"РАСХОЖДЕНИЙ: {fails}")
sys.exit(1 if fails else 0)
