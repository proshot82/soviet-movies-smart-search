#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка данных для статической версии поиска (GitHub Pages) из gosfilmofond.db.

    python pages/build_site.py                 # база gosfilmofond.db в корне репозитория → docs/data/
    python pages/build_site.py --db путь.db --out docs/data

Что получается (всё сжато gzip, браузер распаковывает сам через DecompressionStream):
  films.*.json.gz    — фильмы (id, название, жанр, год, студия, режиссёр, аннотация), отсортированы по film_id
  fts.*.json.gz      — лемматизированный индекс FTS5, вынутый из films_fts через fts5vocab: термы и постинги
                       (документ, частота), длины документов — ровно то, по чему SQLite считает bm25
  lemmas.*.txt.gz    — словоформа → лемма (pymorphy3) для лемматизации запроса в браузере: формы из текста
                       каталога + все формы лемм каталога + написания через «е» вместо «ё»
  vectors.*.bin.gz   — эмбеддинги чанков, усечённые до DIMS измерений (text-embedding-3-large обучена так, что
                       усечение + нормировка ≈ запрос с dimensions=DIMS), 4 бита на число + масштаб на вектор
  manifest.json      — имена файлов (с хешем содержимого — браузер не возьмёт устаревшую копию), размеры, параметры

Требования: pip install numpy pymorphy3 pymorphy3-dicts-ru
"""
import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import film_search as fs  # noqa: E402  — та же лемматизация и стоп-слова, что у движка

DIMS = 1024      # 1024 × 4 бита: семантика как у 1024 float (бенчмарк 85 запросов), ~23 МБ вместо 563 МБ
INT4_MAX = 7

_word_re = re.compile(r'\w+', re.UNICODE)


def write_gz(out_dir, stem, ext, data: bytes):
    gz = gzip.compress(data, compresslevel=9, mtime=0)
    name = f"{stem}.{hashlib.sha256(gz).hexdigest()[:10]}.{ext}.gz"
    for old in out_dir.glob(f"{stem}.*.{ext}.gz"):
        old.unlink()
    (out_dir / name).write_bytes(gz)
    print(f"  {name}: {len(data) / 1e6:.1f} МБ → {len(gz) / 1e6:.1f} МБ gzip")
    return {"file": name, "bytes": len(gz)}


def load_films(conn):
    rows = conn.execute("""SELECT film_id, title, genre, year, studio, director, annotation
                           FROM films ORDER BY film_id""").fetchall()
    return [[fid, t or "", g or "", y, s or "", d or "", a or ""] for fid, t, g, y, s, d, a in rows]


def build_fts_index(conn, film_index):
    """Постинги из самого FTS5 (fts5vocab 'instance'), чтобы токенизация совпала с SQLite один в один."""
    conn.execute("CREATE VIRTUAL TABLE temp.fts_inst USING fts5vocab(main, films_fts, 'instance')")
    postings = {}
    doclen = [0] * len(film_index)
    for term, rowid in conn.execute("SELECT term, doc FROM temp.fts_inst"):
        d = film_index[rowid]
        doclen[d] += 1
        p = postings.setdefault(term, {})
        p[d] = p.get(d, 0) + 1
    terms = sorted(postings)
    assert all(ord(ch) < 0x10000 for t in terms for ch in t), "термы вне BMP: сортировка JS разойдётся с Python"
    offsets, docs, tfs = [0], [], []
    for t in terms:
        for d, tf in sorted(postings[t].items()):
            docs.append(d)
            tfs.append(tf)
        offsets.append(len(docs))
    n_rows = conn.execute("SELECT COUNT(*) FROM films_fts").fetchone()[0]
    assert n_rows == len(film_index), (n_rows, len(film_index))
    return {"terms": terms, "offsets": offsets, "docs": docs, "tfs": tfs, "doclen": doclen}, set(terms)


def build_lemma_map(conn, vocab):
    """Словоформа → лемма, как её дала бы lemmatize_text() в Python (m.parse(w)[0].normal_form).
    Хранятся только формы, отличные от леммы; формы, чья лемма не встречается в каталоге, не нужны —
    по ним поиск по словам всё равно ничего не найдёт."""
    morph = fs._get_morph()
    if morph is None:
        sys.exit("pymorphy3 не установлен: pip install pymorphy3 pymorphy3-dicts-ru")
    cache = {}

    def lemma(w):
        if w not in cache:
            cache[w] = morph.parse(w)[0].normal_form
        return cache[w]

    forms = set()
    # 1) все слова из текста каталога — ровно то, что лемматизировалось при сборке индекса
    for title, ann in conn.execute("SELECT title, annotation FROM films"):
        forms.update(_word_re.findall(((title or "") + " " + (ann or "")).lower()))
    # 2) все формы парадигм лемм каталога — чтобы находилась и форма, которой в тексте нет
    for lem in vocab:
        for p in morph.parse(lem):
            if p.normal_form == lem:
                forms.update(f.word for f in p.lexeme)
    # 3) написание через «е» (pymorphy сам понимает «елка» как «ёлка»)
    forms.update([w.replace('ё', 'е') for w in forms if 'ё' in w])
    forms.update(lem.replace('ё', 'е') for lem in vocab if 'ё' in lem)

    by_lemma = {}
    for w in forms:
        lem = lemma(w)
        if lem != w and lem in vocab:
            by_lemma.setdefault(lem, []).append(w)
    lines = [lem + "\t" + "\t".join(sorted(ws)) for lem, ws in sorted(by_lemma.items())]
    print(f"  словоформ: {sum(len(v) for v in by_lemma.values())} для {len(by_lemma)} лемм")
    return "\n".join(lines).encode("utf-8")


def build_vectors(conn, film_index):
    rows = conn.execute("""SELECT c.film_id, e.embedding FROM embeddings e
                           JOIN chunks c ON c.chunk_id = e.chunk_id ORDER BY e.chunk_id""").fetchall()
    n = len(rows)
    full_dim = len(rows[0][1]) // 4
    vecs = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32).reshape(n, full_dim)[:, :DIMS].copy()
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    scales = (np.abs(vecs).max(axis=1) / INT4_MAX).astype(np.float32)
    q = np.clip(np.round(vecs / scales[:, None]), -8, INT4_MAX).astype(np.int8)
    nib = (q.astype(np.uint8) & 0x0F)
    packed = (nib[:, 0::2] | (nib[:, 1::2] << 4)).astype(np.uint8)   # чётное измерение — младшие 4 бита
    film_of = np.array([film_index[r[0]] for r in rows], dtype=np.uint16)
    # порядок: масштабы float32 (выравнивание 4), номера фильмов uint16, затем упакованные векторы
    blob = scales.tobytes() + film_of.tobytes() + packed.tobytes()
    print(f"  векторов: {n}, {full_dim}D → {DIMS}D × 4 бита")
    return blob, n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=str(ROOT / fs.DB_PATH))
    ap.add_argument("--out", default=str(ROOT / "docs" / "data"))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists() or db.stat().st_size < 1_000_000:
        sys.exit(f"{db}: базы нет или это указатель Git LFS — выполни git lfs pull")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    if fs._fts_mode(conn) != 'lemmas':
        sys.exit("FTS-индекс в базе не по леммам — сначала python film_search.py reindex-fts")
    t0 = time.time()

    films = load_films(conn)
    film_index = {f[0]: i for i, f in enumerate(films)}
    print("Фильмы…")
    files = {"films": write_gz(out, "films", "json",
                               json.dumps(films, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))}
    print("Индекс по словам…")
    fts_index, vocab = build_fts_index(conn, film_index)
    files["fts"] = write_gz(out, "fts", "json",
                            json.dumps(fts_index, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print("Словоформы…")
    files["lemmas"] = write_gz(out, "lemmas", "txt", build_lemma_map(conn, vocab))
    print("Векторы…")
    blob, n_chunks = build_vectors(conn, film_index)
    files["vectors"] = write_gz(out, "vectors", "bin", blob)

    years = [f[3] for f in films if f[3]]
    manifest = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "films": len(films), "chunks": n_chunks,
        "year_min": min(years), "year_max": max(years),
        "embedding_model": fs.EMBEDDING_MODEL, "dims": DIMS, "quant": "int4",
        "rerank_model": fs.RERANK_MODEL,
        "files": files,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(f["bytes"] for f in files.values())
    print(f"Готово за {time.time() - t0:.0f} с: {total / 1e6:.1f} МБ в {out}")


if __name__ == "__main__":
    main()
