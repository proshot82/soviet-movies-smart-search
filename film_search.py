#!/usr/bin/env python3
"""
Семантический поиск фильмов Госфильмофонда — SQLite + FTS5 + Embeddings.

Команды:
  python film_search.py import catalog.json          # Импорт JSON → SQLite
  python film_search.py import cat1.json cat2.json   # Несколько каталогов
  python film_search.py embed                        # Генерация эмбеддингов
  python film_search.py embed --resume               # Продолжить прерванную генерацию
  python film_search.py search "описание фильма"     # Поиск из CLI (--expand включает расширение запроса)
  python film_search.py serve                        # Веб-интерфейс
  python film_search.py stats                        # Статистика базы
  python film_search.py reindex-fts                  # Пересобрать FTS-индекс по леммам (без re-embed)

Требования: pip install openai numpy flask pymorphy3 pymorphy3-dicts-ru
"""

import argparse
import json
import os
import re
import sys
import time
import sqlite3
import logging
from pathlib import Path

import numpy as np

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


class _NoAnsi(logging.Filter):
    """Убирает ANSI-коды цвета из записей (werkzeug красит лог; cmd.exe и файл лога показывают их как «←[31m»)."""
    def filter(self, record):
        if isinstance(record.msg, str) and '\x1b' in record.msg:
            record.msg = _ANSI_RE.sub('', record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_ANSI_RE.sub('', a) if isinstance(a, str) else a for a in record.args)
        return True


_log_handlers = [logging.FileHandler("film_search.log", encoding="utf-8"), logging.StreamHandler()]
for _h in _log_handlers:
    _h.addFilter(_NoAnsi())
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=_log_handlers)
log = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────────────

DB_PATH = "gosfilmofond.db"
EMBEDDING_MODEL = "text-embedding-3-large"
DIMENSIONS = 3072
EMBEDDING_BATCH = 100
RATE_LIMIT_PAUSE = 0.3
RERANK_MODEL = "gpt-5.5"
QUERY_EXPAND_MODEL = "gpt-5.4-nano"

# ── Настройки поиска (подобраны на бенчмарке bench/bench_search.py, 85 запросов, 04.09.2026) ──
# Расширение запроса (переформулировка через QUERY_EXPAND_MODEL) по умолчанию ВЫКЛЮЧЕНО:
# на 85 запросах оно не улучшило ни одной метрики (Hit@1 94% против 95% без него), один фильм
# из-за него потерялся, а каждый запрос шёл на 3–5 с дольше. Включается галочкой в интерфейсе
# или флагом --expand в командной строке.
EXPAND_DEFAULT = False
# Веса слияния RRF (FTS / семантика). Без реранкера FTS должен вести: сам по себе он ставит
# искомый фильм на 1-е место в 86% случаев, семантика — в 65%; при 0.6 слияние давало 81%,
# при 0.8 — 86% (офлайн на снимках каналов bench_tune.py). С реранкером порядок кандидатов
# почти не важен (фильм попадает в список кандидатов в 100% случаев при любом весе).
FTS_WEIGHT_RERANK = 0.3
FTS_WEIGHT_NORERANK = 0.8
# Сколько символов аннотации видит реранкер. Было 500 — а медиана аннотации 830 символов,
# 81% аннотаций длиннее 500: реранкер судил по половине текста, и в двух проверочных запросах
# решающие события («заболевает и умирает», «начинает тренироваться самостоятельно») были
# отрезаны. 1500 символов вмещают 89% аннотаций целиком; входных токенов на запрос ≈ в 1.8 раза
# больше (≈ 19–20 тыс. вместо ≈ 11 тыс. при 65 кандидатах).
RERANK_ANN_CHARS = 1500


def fusion_weights(do_rerank):
    """Веса (FTS, семантика) для слияния RRF в зависимости от того, будет ли реранкер."""
    w = FTS_WEIGHT_RERANK if do_rerank else FTS_WEIGHT_NORERANK
    return w, 1.0 - w


# ─── OpenAI client ──────────────────────────────────────────────────

def get_openai_client():
    try:
        from openai import OpenAI
    except ImportError:
        print("pip install openai", file=sys.stderr)
        sys.exit(1)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        for name in ("openai_key.txt", ".openai_key"):
            p = Path(__file__).parent / name
            if p.exists():
                key = p.read_text(encoding='utf-8-sig').strip()   # UTF-8 с BOM из Блокнота тоже
                break
    if not key:
        print("Установите OPENAI_API_KEY или создайте openai_key.txt", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=key)


# ─── Database schema ────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS films (
    film_id   INTEGER PRIMARY KEY,
    title     TEXT,
    genre     TEXT,
    year      INTEGER,
    studio    TEXT,
    director  TEXT,
    screenwriter TEXT,
    annotation TEXT,
    cast_text TEXT,
    color     TEXT,
    format    TEXT,
    release_date TEXT,
    source    TEXT,
    kind      TEXT,     -- тип: кинофильм, телефильм, фильм-спектакль, мультфильм, не игровое, фильм-опера/балет
    country   TEXT,
    episodes  INTEGER   -- число серий (сериалы)
);

-- FTS5 по ЛЕММАМ: standalone-таблица, rowid = film_id.
-- Заполняется из Python (build_fts), т.к. лемматизация недоступна в SQL-триггерах.
CREATE VIRTUAL TABLE IF NOT EXISTS films_fts USING fts5(lemmas);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    film_id   INTEGER NOT NULL REFERENCES films(film_id),
    chunk_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id  INTEGER PRIMARY KEY REFERENCES chunks(chunk_id),
    model     TEXT NOT NULL,
    embedding BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_film ON chunks(film_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk ON embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_films_title_year ON films(title, year);

-- Служебные пары ключ/значение (режим FTS-индекса и т.п.)
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _lc(s):
    """lower() с поддержкой кириллицы для SQL (встроенный lower()/LIKE в SQLite
    регистронезависимы только для ASCII: 'драма' не совпадает с 'Драма')."""
    return s.lower() if isinstance(s, str) else s


# Колонки films, появившиеся после первой версии схемы: в старой базе добавляются при открытии
_FILMS_ADDED_COLUMNS = {"kind": "TEXT", "country": "TEXT", "episodes": "INTEGER"}

# Типы фильмов (значения films.kind) — в порядке, в котором они показываются в фильтре
KINDS = ("кинофильм", "телефильм", "фильм-спектакль", "мультфильм", "не игровое", "фильм-опера/балет")


def open_db(path=None, schema=True):
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.create_function("lc", 1, _lc, deterministic=True)
    if schema:
        conn.executescript(SCHEMA)
        have = {r[1] for r in conn.execute("PRAGMA table_info(films)")}
        for col, typ in _FILMS_ADDED_COLUMNS.items():
            if col not in have:
                conn.execute(f"ALTER TABLE films ADD COLUMN {col} {typ}")
        conn.commit()
    return conn


def _meta_get(conn, key, default=None):
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default
    except sqlite3.Error:
        return default


def _meta_set(conn, key, value):
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, str(value)))


# ─── Лемматизация (FTS по леммам) ───────────────────────────────────

_morph = None
_morph_failed = False
_word_re = re.compile(r'\w+', re.UNICODE)

# Стоп-леммы для FTS: служебные слова (предлоги, союзы, частицы, местоимения,
# связки). Фильтр в fts_search работает уже по леммам, поэтому достаточно
# начальной формы — она ловит все словоформы. Числа и счётные слова сюда НЕ входят.
_RU_STOP = frozenset(
    "а без будто бы быть в ваш весь вот всё вы да даже для до если есть ещё её "
    "же и из или к как когда который кто ли либо лишь между мы на над наш не "
    "неужели ни но о он она они оно от по под потому при про разве с сам свой "
    "себя стать также такой тоже только тот ты у уже хотя чей через что чтобы "
    "это этот я".split()
)


def _get_morph():
    """Ленивый MorphAnalyzer. При отсутствии pymorphy3 — один варн и откат."""
    global _morph, _morph_failed
    if _morph is None and not _morph_failed:
        try:
            import pymorphy3
            _morph = pymorphy3.MorphAnalyzer()
        except Exception as e:
            _morph_failed = True
            log.warning(
                "pymorphy3 недоступен — FTS работает без лемматизации. "
                f"Установи: pip install pymorphy3 pymorphy3-dicts-ru ({e})"
            )
    return _morph


def lemmatize_text(text):
    """Привести строку к леммам (нижний регистр, начальные формы слов).
    Применяется ОДИНАКОВО при индексации и при запросе, чтобы словоформы
    совпадали. Без pymorphy3 — откат к нижнему регистру (как раньше)."""
    if not text:
        return ""
    m = _get_morph()
    if m is None:
        return text.lower()
    try:
        return ' '.join(m.parse(t)[0].normal_form for t in _word_re.findall(text.lower()))
    except Exception:
        return text.lower()


def build_fts(conn):
    """(Пере)собрать лемматизированный FTS-индекс из таблицы films.
    Сносит старый films_fts и его триггеры (миграция со старой схемы),
    создаёт standalone FTS5 по леммам и заполняет. Эмбеддинги не трогает."""
    # Леммы считаются до начала транзакции (это самая долгая часть), а снос старого индекса и запись
    # нового идут одной транзакцией: если окно закроют посреди пересборки, остаётся прежний индекс,
    # а не пустой (executescript фиксировал DROP/CREATE сразу, отдельно от заполнения).
    rows = conn.execute("SELECT film_id, title, annotation FROM films").fetchall()
    lemmas = [(film_id, lemmatize_text(((title or "") + " " + (annotation or "")).strip()))
              for film_id, title, annotation in rows]
    mode = 'lemmas' if _get_morph() is not None else 'lower'
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN")
    try:
        for stmt in ("DROP TRIGGER IF EXISTS films_ai", "DROP TRIGGER IF EXISTS films_ad",
                     "DROP TRIGGER IF EXISTS films_au", "DROP TABLE IF EXISTS films_fts",
                     "CREATE VIRTUAL TABLE films_fts USING fts5(lemmas)"):
            conn.execute(stmt)
        conn.executemany("INSERT INTO films_fts(rowid, lemmas) VALUES (?, ?)", lemmas)
        _meta_set(conn, 'fts_mode', mode)
        _meta_set(conn, 'fts_built_at', time.strftime('%Y-%m-%d %H:%M:%S'))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if mode == 'lemmas':
        log.info(f"FTS-индекс по леммам построен: {len(rows)} фильмов")
    else:
        log.warning(f"FTS-индекс построен БЕЗ лемматизации ({len(rows)} фильмов) — pymorphy3 не установлен. "
                    "После установки: python film_search.py reindex-fts (или просто запусти serve — пересоберёт сам).")
    return len(rows)


def _fts_mode(conn):
    """Состояние FTS-индекса: 'old' (старая схема без колонки lemmas), 'lower' (собран без pymorphy3 —
    просто нижний регистр), 'lemmas' (собран по леммам), 'stale' (не совпадает с текущими данными/словарём).
    Колонка 'lemmas' есть у обоих новых вариантов, поэтому режим проверяется по содержимому: берём
    несколько фильмов и сравниваем сохранённую строку с тем, что даёт lemmatize_text сейчас."""
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(films_fts)").fetchall()]
    except Exception:
        return 'old'
    if 'lemmas' not in cols:
        return 'old'
    # Индекс должен покрывать все фильмы: пустой или неполный (прерванная сборка, фильмы добавлены
    # в обход import) — устарел, иначе поиск по словам молча не находит часть каталога
    n_films = conn.execute("SELECT COUNT(*) FROM films").fetchone()[0]
    if conn.execute("SELECT COUNT(*) FROM films_fts").fetchone()[0] != n_films:
        return 'stale'
    recorded = _meta_get(conn, 'fts_mode')
    rows = conn.execute("""SELECT f.film_id, f.title, f.annotation, x.lemmas FROM films f
                           JOIN films_fts x ON x.rowid = f.film_id
                           WHERE f.annotation IS NOT NULL AND length(f.annotation) > 200
                           ORDER BY f.film_id LIMIT 5""").fetchall()
    if not rows:
        return recorded or 'lemmas'
    same_lemmas = same_lower = True
    for _, title, ann, stored in rows:
        text = ((title or "") + " " + (ann or "")).strip()
        if stored != lemmatize_text(text):
            same_lemmas = False
        if stored != text.lower():
            same_lower = False
    if _get_morph() is None:
        # без pymorphy3 не отличить леммы от «старых» лемм; верим записи в meta
        return recorded or ('lower' if same_lower else 'lemmas')
    if same_lemmas:
        return 'lemmas'
    if same_lower:
        return 'lower'
    return 'stale'


def _fts_is_lemmatized(conn):
    return _fts_mode(conn) == 'lemmas'


# ─── Import catalog ─────────────────────────────────────────────────

# Поля JSON-записи → колонки films (cast принимается и как cast_text)
_IMPORT_FIELDS = ("title", "genre", "year", "studio", "director", "screenwriter", "annotation", "cast_text",
                  "color", "format", "release_date", "source", "kind", "country", "episodes")
# От этих полей зависят чанки (make_chunks) и эмбеддинги: при их правке чанки фильма пересобираются
_CHUNK_FIELDS = ("title", "year", "annotation")


def _import_values(film, catalog_path):
    """Запись каталога → {колонка: значение} только для полей, которые в записи есть.
    Строки обрезаются по краям, пустая строка — это NULL."""
    vals = {}
    for key in _IMPORT_FIELDS:
        src = key
        if key == "cast_text" and "cast_text" not in film:
            src = "cast"
        if src not in film:
            continue
        v = film[src]
        if isinstance(v, str):
            v = v.strip() or None
        vals[key] = v
    for key in ("year", "episodes"):
        if vals.get(key) is not None:
            try:
                vals[key] = int(vals[key])
            except (TypeError, ValueError):
                vals[key] = None
    return vals


def cmd_import(args):
    """Импортировать JSON-каталоги в SQLite.

    Запись без film_id — новый фильм. Дублем (пропуск) считается только полное совпадение
    названия, года, студии и аннотации: так повторный импорт того же файла ничего не удваивает,
    а разные фильмы с одним названием и годом (телефильм и телеспектакль, два «Соседи» 1979)
    не теряются. Такие совпадения по названию и году перечисляются в логе — для проверки.

    Запись с film_id — правка существующего фильма: меняются только поля, которые в записи есть.
    Если поменялись название, год или аннотация, чанки фильма пересобираются, а его эмбеддинги
    удаляются — их досчитает `embed --resume`.

    --dry-run: всё то же, но ничего не записывается — только отчёт."""
    conn = open_db(args.db)
    dry = getattr(args, 'dry_run', False)

    try:
        stats = {"new": 0, "dup": 0, "empty": 0, "updated": 0, "unchanged": 0, "missing_id": 0}
        same_title = []      # (новая запись, film_id уже имеющихся с тем же названием и годом)
        rechunk = set()      # film_id, у которых надо пересобрать чанки

        for catalog_path in args.catalogs:
            log.info(f"Импорт {catalog_path}...")
            with open(catalog_path, encoding='utf-8-sig') as f:
                films = json.load(f)
            if not isinstance(films, list):
                log.error(f"  {catalog_path}: ожидается JSON-массив записей")
                continue

            for film in films:
                if not isinstance(film, dict):
                    stats["empty"] += 1
                    continue
                vals = _import_values(film, catalog_path)
                film_id = film.get("film_id")

                if film_id is not None:
                    row = conn.execute(f"SELECT {', '.join(_IMPORT_FIELDS)} FROM films WHERE film_id = ?",
                                       (film_id,)).fetchone()
                    if row is None:
                        stats["missing_id"] += 1
                        log.warning(f"  film_id {film_id} нет в базе — запись пропущена")
                        continue
                    old = dict(zip(_IMPORT_FIELDS, row))
                    if vals.get("title", old["title"]) is None:
                        stats["empty"] += 1
                        continue
                    changed = {k: v for k, v in vals.items() if old[k] != v}
                    if not changed:
                        stats["unchanged"] += 1
                        continue
                    conn.execute(f"UPDATE films SET {', '.join(k + ' = ?' for k in changed)} WHERE film_id = ?",
                                 (*changed.values(), film_id))
                    if any(k in changed for k in _CHUNK_FIELDS):
                        rechunk.add(film_id)
                    stats["updated"] += 1
                    continue

                title = vals.get("title")
                if not title:
                    stats["empty"] += 1
                    continue
                vals.setdefault("source", catalog_path)
                if conn.execute("""SELECT 1 FROM films WHERE title = ? AND year IS ? AND studio IS ?
                                   AND annotation IS ?""",
                                (title, vals.get("year"), vals.get("studio"), vals.get("annotation"))).fetchone():
                    stats["dup"] += 1
                    continue
                similar = [r[0] for r in conn.execute("SELECT film_id FROM films WHERE title = ? AND year IS ?",
                                                     (title, vals.get("year")))]
                cols = list(vals)
                cur = conn.execute(f"INSERT INTO films ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                                   [vals[c] for c in cols])
                if similar:
                    same_title.append((cur.lastrowid, title, vals.get("year"), similar))
                stats["new"] += 1

        # Пересборка чанков у исправленных фильмов: старые чанки и их эмбеддинги удаляются,
        # новые создаются ниже вместе с чанками новых фильмов
        for fid in rechunk:
            conn.execute("DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE film_id = ?)",
                         (fid,))
            conn.execute("DELETE FROM chunks WHERE film_id = ?", (fid,))

        films_without_chunks = conn.execute("""
            SELECT film_id, title, year, annotation
            FROM films
            WHERE film_id NOT IN (SELECT DISTINCT film_id FROM chunks)
        """).fetchall()
        chunk_count = 0
        for film_id, title, year, annotation in films_without_chunks:
            for chunk_text in make_chunks(title, year, annotation):
                conn.execute("INSERT INTO chunks (film_id, chunk_text) VALUES (?, ?)", (film_id, chunk_text))
                chunk_count += 1

        log.info(f"Новых фильмов: {stats['new']}, исправлено: {stats['updated']} "
                 f"(из них с новыми чанками: {len(rechunk)}), без изменений: {stats['unchanged']}, "
                 f"дублей пропущено: {stats['dup']}, пустых: {stats['empty']}, "
                 f"film_id не найден: {stats['missing_id']}; новых чанков: {chunk_count}")
        if same_title:
            log.info(f"Добавлены фильмы, у которых в базе уже есть фильм с тем же названием и годом "
                     f"({len(same_title)}) — проверьте, что это разные фильмы:")
            for new_id, title, year, ids in same_title[:50]:
                log.info(f"  {new_id}: «{title}» ({year}) — уже есть film_id {', '.join(map(str, ids))}")
            if len(same_title) > 50:
                log.info(f"  … и ещё {len(same_title) - 50}")

        if dry:
            conn.rollback()
            log.info("--dry-run: ничего не записано")
            return
        conn.commit()

        # Построить лемматизированный FTS-индекс по всем фильмам
        build_fts(conn)

        total_films = conn.execute("SELECT COUNT(*) FROM films").fetchone()[0]
        total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        log.info(f"База: {total_films} фильмов, {total_chunks} чанков. "
                 "Эмбеддинги для новых чанков: python film_search.py embed --resume")
    finally:
        conn.close()


# ─── Sentence chunking ─────────────────────────────────────────────

def split_sentences(text):
    """Разбить текст на предложения."""
    parts = re.split(r'(?<=[.!?])\s+(?=[А-ЯЁA-Z«"(]|\.\.\.)', text)
    return [p.strip() for p in parts if p.strip()]


MAX_CHUNK_CHARS = 4000  # ~1000 tokens, beyond this embedding quality degrades anyway


def make_chunks(title, year, annotation):
    """Создать чанки для одного фильма. Возвращает список строк."""
    prefix_parts = []
    if title:
        prefix_parts.append(title)
    if year:
        prefix_parts.append(f"{year} год")
    prefix = '. '.join(prefix_parts)
    
    if not annotation:
        return [prefix] if prefix else []
    
    full_text = f"{prefix}. {annotation}" if prefix else annotation
    if len(full_text) > MAX_CHUNK_CHARS:
        full_text = full_text[:MAX_CHUNK_CHARS]
    chunks = [full_text]
    
    sentences = split_sentences(annotation)
    # Sub-chunks only useful with 4+ sentences (with 2-3 sentences, sub-chunk ≈ full text)
    if len(sentences) >= 4:
        for i in range(0, len(sentences) - 1, 2):
            chunk_sents = sentences[i:i + 3]
            chunk_text = ' '.join(chunk_sents)
            if len(chunk_text) > 40:
                chunks.append(f"{prefix}. {chunk_text}" if prefix else chunk_text)
    
    return chunks


# ─── Embedding generation ──────────────────────────────────────────

def cmd_embed(args):
    """Генерация эмбеддингов для чанков."""
    conn = open_db(args.db)
    client = get_openai_client()
    
    try:
        if args.resume:
            # Validate dimensions
            sample = conn.execute("SELECT embedding FROM embeddings LIMIT 1").fetchone()
            if sample:
                existing_dim = len(sample[0]) // 4
                if existing_dim != DIMENSIONS:
                    log.error(f"Dimension mismatch: existing={existing_dim}D, expected={DIMENSIONS}D. "
                              "Run without --resume to rebuild.")
                    sys.exit(1)
            
            done_ids = set(r[0] for r in conn.execute("SELECT chunk_id FROM embeddings").fetchall())
            log.info(f"Resuming: {len(done_ids)} already embedded")
        else:
            # Полная пересборка стирает все эмбеддинги — сначала убеждаемся, что API отвечает
            # (ключ, сеть, модель), иначе база осталась бы без смыслового поиска
            try:
                client.embeddings.create(model=EMBEDDING_MODEL, input=["проверка"], dimensions=DIMENSIONS)
            except Exception as e:
                log.error(f"API эмбеддингов недоступен ({e}) — существующие эмбеддинги не тронуты")
                sys.exit(1)
            conn.execute("DELETE FROM embeddings")
            conn.commit()
            done_ids = set()
        
        # Get chunks needing embeddings
        rows = conn.execute("SELECT chunk_id, chunk_text FROM chunks").fetchall()
        to_embed = [(cid, text) for cid, text in rows if cid not in done_ids]
        total = len(to_embed)
        log.info(f"Chunks to embed: {total}")
        
        if total == 0:
            log.info("Nothing to embed.")
            return
        
        embedded = 0
        skipped = 0
        total_tokens = 0
        uncommitted = 0
        
        for batch_start in range(0, total, EMBEDDING_BATCH):
            batch = to_embed[batch_start:batch_start + EMBEDDING_BATCH]
            batch_ids = [cid for cid, _ in batch]
            batch_texts = [text for _, text in batch]
            
            tokens, stored = _embed_batch(client, conn, batch_ids, batch_texts, commit=False)
            total_tokens += tokens
            embedded += stored
            skipped += len(batch_ids) - stored
            if stored:
                uncommitted += 1
            
            if uncommitted >= 10:
                conn.commit()
                uncommitted = 0
            
            processed = embedded + skipped
            if processed % 500 == 0 or processed >= total:
                log.info(f"  Embedded {embedded}/{total} (skipped: {skipped}, tokens: {total_tokens:,})")
            
            if batch_start + EMBEDDING_BATCH < total:
                time.sleep(RATE_LIMIT_PAUSE)
        
        conn.commit()
        log.info(f"Done. Embedded {embedded}/{total} chunks, {total_tokens:,} tokens.")
        if skipped:
            log.warning(f"  {skipped} chunks skipped. Use --resume to retry.")
        
        cost = total_tokens / 1_000_000 * 0.13
        log.info(f"Estimated cost: ${cost:.4f}")
    finally:
        if conn.in_transaction:
            conn.commit()   # готовые батчи сохраняются и при остановке (Ctrl+C, отказ ключа) — их подхватит --resume
        conn.close()


def _embed_batch(client, conn, ids, texts, commit=True):
    """Call OpenAI API, store BLOBs. Возвращает (токены, сколько чанков сохранено).

    Повторяет только то, что лечится ожиданием: лимит запросов (429), сбой сервера (5xx), сеть.
    Отказ ключа (401/403) прерывает всю генерацию; ошибка в самом запросе (400/404/422 — модель,
    размерность, текст) сразу пропускает батч — ждать её бессмысленно."""
    for attempt in range(5):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
                dimensions=DIMENSIONS,
            )
            break
        except Exception as e:
            status = getattr(e, 'status_code', None)
            if status in (401, 403):
                raise
            if status is not None and 400 <= status < 500 and status != 429:
                log.error(f"Батч из {len(ids)} чанков отклонён ({e}) — пропускаю")
                return 0, 0
            wait = 10 * (attempt + 1)
            log.warning(f"API error ({attempt+1}/5): {e} — waiting {wait}s")
            time.sleep(wait)
    else:
        log.error(f"Failed batch of {len(ids)} after 5 retries")
        return 0, 0
    
    tokens = response.usage.total_tokens
    # Вектор привязывается к своему входу по полю index, а не по порядку в ответе
    vec_by_pos = {item.index: item.embedding for item in response.data}
    if len(vec_by_pos) != len(ids):
        log.warning(f"API returned {len(vec_by_pos)} embeddings for {len(ids)} inputs")
    
    rows = [(ids[i], EMBEDDING_MODEL, np.asarray(vec_by_pos[i], dtype=np.float32).tobytes())
            for i in range(len(ids)) if i in vec_by_pos]
    conn.executemany(
        "INSERT OR REPLACE INTO embeddings (chunk_id, model, embedding) VALUES (?,?,?)",
        rows,
    )
    if commit:
        conn.commit()
    return tokens, len(rows)


# ─── Index loading (cached) ────────────────────────────────────────

_cached_vecs = None
_cached_chunk_ids = None
_cached_chunk_to_film = None
_cached_film_ids_arr = None
_cached_n_films = None
_cached_idx_to_fid = None


def _load_index(conn):
    """Load embeddings into memory. Cached after first call."""
    global _cached_vecs, _cached_chunk_ids, _cached_chunk_to_film
    if _cached_vecs is not None:
        return _cached_vecs, _cached_chunk_ids, _cached_chunk_to_film
    
    conn.execute("BEGIN")
    try:
        count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        if count == 0:
            vecs = np.array([]).reshape(0, 0)
            chunk_ids = []
            chunk_to_film = {}
            dim = 0
            actual = 0
        else:
            sample = conn.execute("SELECT embedding FROM embeddings LIMIT 1").fetchone()
            dim = len(sample[0]) // 4
            
            vecs = np.empty((count, dim), dtype=np.float32)
            chunk_ids = []
            chunk_to_film = {}
            
            cursor = conn.execute("""
                SELECT e.chunk_id, c.film_id, e.embedding
                FROM embeddings e JOIN chunks c ON e.chunk_id = c.chunk_id
            """)
            actual = 0
            for chunk_id, film_id, blob in cursor:
                if actual >= count:
                    break
                chunk_ids.append(chunk_id)
                chunk_to_film[actual] = film_id
                vecs[actual] = np.frombuffer(blob, dtype=np.float32)
                actual += 1
            
            if actual < count:
                vecs = vecs[:actual]
    finally:
        conn.execute("ROLLBACK")
    
    # Normalize in-place (skip if empty)
    if actual > 0:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vecs /= norms
    
    _cached_vecs = vecs
    _cached_chunk_ids = chunk_ids
    _cached_chunk_to_film = chunk_to_film
    _build_film_index(chunk_ids, chunk_to_film)
    
    log.info(f"Index loaded: {actual} vectors ({dim}D), {vecs.nbytes // 1024 // 1024} MB")
    return _cached_vecs, _cached_chunk_ids, _cached_chunk_to_film


def _build_film_index(chunk_ids, chunk_to_film):
    """Отображение чанк → компактный индекс фильма для np.maximum.at (строится один раз при загрузке индекса)."""
    global _cached_film_ids_arr, _cached_n_films, _cached_idx_to_fid
    film_id_list = [chunk_to_film[i] for i in range(len(chunk_ids))]
    unique_fids = sorted(set(film_id_list))
    fid_to_idx = {fid: idx for idx, fid in enumerate(unique_fids)}
    _cached_n_films = len(unique_fids)
    _cached_film_ids_arr = np.array([fid_to_idx[fid] for fid in film_id_list], dtype=np.int32)
    _cached_idx_to_fid = unique_fids


# ─── Фильтры и строки результатов (общие для обоих каналов) ─────────

RRF_K = 60  # константа слияния Reciprocal Rank Fusion (hybrid_search, fallback_order)
_FILM_COLS = "film_id, title, genre, year, studio, director, annotation, cast_text, source"


def _like_escape(s):
    """Подстрока для LIKE … ESCAPE '\\': символы % и _ из ввода ищутся буквально, а не как шаблоны."""
    return s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _filter_sql(year=None, studio=None, genre=None, alias="", kind=None):
    """Условия фильтров (десятилетие, подстрока студии и жанра без учёта регистра, тип фильма)
    → (список SQL, параметры)."""
    parts, params = [], []
    if kind:
        parts.append(f"{alias}kind = ?")
        params.append(kind)
    if year:
        decade = (year // 10) * 10
        parts.append(f"{alias}year BETWEEN ? AND ?")
        params.extend([decade, decade + 9])
    if studio:
        parts.append(f"lc({alias}studio) LIKE ? ESCAPE '\\'")
        params.append(f"%{_like_escape(studio.lower())}%")
    if genre:
        parts.append(f"lc({alias}genre) LIKE ? ESCAPE '\\'")
        params.append(f"%{_like_escape(genre.lower())}%")
    return parts, params


def _film_dict(row, **extra):
    """Строка (_FILM_COLS) → словарь результата поиска."""
    film_id, title, genre, year, studio, director, ann, cast_t, src = row
    return {"film_id": film_id, "title": title or "", "genre": genre or "",
            "year": year, "studio": studio or "", "director": director or "",
            "annotation": ann or "", "cast": cast_t or "",
            "source": src if (src or "").startswith(("http://", "https://")) else "", **extra}


# ─── FTS search ─────────────────────────────────────────────────────

def fts_search(conn, query, limit=20, year=None, studio=None, genre=None, kind=None):
    """Full-text search with optional filters. Two-tier: AND first, then OR for recall."""
    # Strip everything except letters, digits, spaces (FTS5 tokenizer splits on _ too)
    cleaned = re.sub(r'[_\W]+', ' ', query, flags=re.UNICODE)
    cleaned = lemmatize_text(cleaned)  # леммы — как и индекс films_fts
    tokens = cleaned.split()
    tokens = [t for t in tokens
              if t and len(t) >= 2 and t not in _RU_STOP
              and t.upper() not in ('AND', 'OR', 'NOT', 'NEAR')]
    if not tokens:
        return []
    
    # Build filter clauses (reused for both tiers)
    where_parts, filter_params = _filter_sql(year, studio, genre, alias="f.", kind=kind)
    filter_sql = (" AND " + " AND ".join(where_parts)) if where_parts else ""
    
    sql_template = f"""
        SELECT {", ".join("f." + c for c in _FILM_COLS.split(", "))}, rank
        FROM films_fts fts
        JOIN films f ON f.film_id = fts.rowid
        WHERE films_fts MATCH ?{{filter}}
        ORDER BY rank
        LIMIT ?
    """.replace("{filter}", filter_sql)
    
    def _run(match_expr, n):
        params = [match_expr] + filter_params + [n]
        try:
            return conn.execute(sql_template, params).fetchall()
        except Exception as e:
            log.warning(f"FTS search error: {e} (query={match_expr!r})")
            return []
    
    def _to_results(rows):
        return [_film_dict(r[:-1], score=-r[-1]) for r in rows]
    
    # Tier 1: AND (implicit) — high precision, all terms must match
    if len(tokens) >= 2:
        and_q = ' '.join(f'{t}*' for t in tokens)
        and_rows = _run(and_q, limit)
        results = _to_results(and_rows)
        if len(results) >= limit:
            return results
    else:
        results = []
    
    # Tier 2: OR — fill remaining slots for recall
    or_q = ' OR '.join(f'{t}*' for t in tokens)
    or_rows = _run(or_q, limit * 2)  # wider pool to dedup against tier 1
    seen = {r["film_id"] for r in results}
    for r in _to_results(or_rows):
        if r["film_id"] not in seen:
            results.append(r)
            seen.add(r["film_id"])
            if len(results) >= limit:
                break
    
    return results


# ─── Semantic search ────────────────────────────────────────────────

def _embed_queries(client, queries):
    """Embed multiple queries in one API call with retry."""
    for attempt in range(3):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=queries,
                dimensions=DIMENSIONS,
            )
            return [np.array(item.embedding, dtype=np.float32) for item in response.data]
        except Exception as e:
            if attempt < 2:
                log.warning(f"Query embed retry {attempt+1}/3: {e}")
                time.sleep(1)
            else:
                raise


def semantic_search(conn, query_vecs, limit=20, year=None, studio=None, genre=None, kind=None):
    """Semantic search across chunk embeddings. Returns film-level results."""
    vecs, chunk_ids, chunk_to_film = _load_index(conn)
    if len(chunk_ids) == 0:
        return []
    
    if _cached_film_ids_arr is None:
        _build_film_index(chunk_ids, chunk_to_film)
    
    n_films = _cached_n_films
    film_ids_arr = _cached_film_ids_arr
    idx_to_fid = _cached_idx_to_fid
    
    # Max cosine per film across all query variants — scan ALL chunks
    best_film_scores = np.full(n_films, -np.inf, dtype=np.float32)
    for q_vec in query_vecs:
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            continue
        q_vec = q_vec / q_norm
        scores = vecs @ q_vec
        # np.maximum.at: for each chunk, update film's best score
        np.maximum.at(best_film_scores, film_ids_arr, scores)
    
    # Collect film_id → score for films above threshold
    above = np.nonzero(best_film_scores > 0)[0]
    film_scores = {idx_to_fid[i]: float(best_film_scores[i]) for i in above}
    
    # Apply filters: фильтр по всей таблице films, без списка id в запросе (до ~7 тыс. параметров)
    where_parts, params = _filter_sql(year, studio, genre, kind=kind)
    if where_parts and film_scores:
        valid_ids = set(r[0] for r in conn.execute(
            f"SELECT film_id FROM films WHERE {' AND '.join(where_parts)}", params
        ).fetchall())
        film_scores = {fid: s for fid, s in film_scores.items() if fid in valid_ids}
    
    # Top films
    sorted_films = sorted(film_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    if not sorted_films:
        return []
    
    # Fetch metadata
    fids = [fid for fid, _ in sorted_films]
    ph = ",".join("?" * len(fids))
    meta_rows = conn.execute(f"SELECT {_FILM_COLS} FROM films WHERE film_id IN ({ph})", fids).fetchall()
    meta = {r[0]: r for r in meta_rows}
    
    return [_film_dict(meta[film_id], score=score, sem_score=score)
            for film_id, score in sorted_films if film_id in meta]


# ─── Query expansion ───────────────────────────────────────────────

def expand_query(client, query):
    """Расширить запрос через QUERY_EXPAND_MODEL.

    Возвращает (fts_query, variants):
      fts_query — денойз-строка из редких содержательных слов сюжета для FTS-канала
                  (без шума про просмотр/камеру/телепередачи);
      variants  — [оригинал] + перефразы сюжета для семантического канала.
    При сбое — (query, [query]).
    """
    prompt = f"""Пользователь ищет фильм по нечёткому описанию из памяти: "{query}"

Сделай две вещи и верни СТРОГО JSON-объект без пояснений и без Markdown.

1. "keywords": строка из 4–10 самых характерных СОДЕРЖАТЕЛЬНЫХ слов сюжета (предметы, персонажи, места, действия), которые вероятно встречаются в аннотации фильма. Через пробел, в начальной форме.
   ВЫБРОСИ всё, чего не бывает в описании сюжета: как смотрел ("показывали", "помню", "кажется", "вроде"), названия телепередач и каналов, операторские термины ("крупный план", "панорама", "кадр", "картинка"), вводные слова.
   Оставляй редкое и конкретное (пример: пираты, карта, чердак, подзорная труба), убирай общее (пример: трое, нашли, решили, стоят, вокруг).

2. "paraphrases": массив из 5–7 коротких альтернативных описаний ТОГО ЖЕ фильма (по одному предложению), с учётом типичных ошибок памяти:
   - роли перепутаны: кто совершает действие, кто жертва;
   - родственные связи неточны (дочь↔сын, отец↔брат, жених↔муж);
   - причинность упрощена ("убил" вместо "стал причиной гибели");
   - детали обобщены ("охотник" вместо "лесник").

Формат ответа:
{{"keywords": "слово1 слово2 ...", "paraphrases": ["вариант 1", "вариант 2", ...]}}"""
    try:
        response = client.chat.completions.create(
            model=QUERY_EXPAND_MODEL,
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort="none",
            max_completion_tokens=1000,
        )
        text = response.choices[0].message.content.strip()
        text = text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        if isinstance(data, dict):
            kw = (data.get("keywords") or "").strip()
            paras = data.get("paraphrases")
            fts_query = kw if kw else query
            variants = [query]
            if isinstance(paras, list):
                variants += [v for v in paras if isinstance(v, str) and v.strip()]
            return fts_query, variants
    except Exception as e:
        log.warning(f"Query expansion failed: {e}")
    return query, [query]


# ─── Hybrid search ─────────────────────────────────────────────────

def hybrid_search(conn, client, query, limit=50, expand=True,
                  year=None, studio=None, genre=None,
                  fts_weight=0.3, sem_weight=0.7, status=None, kind=None):
    """Hybrid FTS + semantic search with RRF fusion.

    Returns (results, variants). У каждого результата есть fts_rank / sem_rank — место в
    канале (None, если канал фильм не нашёл); по ним fallback_order() пересчитывает порядок
    без реранкера. Если эмбеддинг запроса не удался (нет связи с API), поиск идёт только по
    словам, а в status (если передан словарь) пишется status['sem_failed'] = текст ошибки.
    """
    # Query expansion → денойз-запрос для FTS + перефразы для семантики
    if expand:
        fts_query, variants = expand_query(client, query)
        log.info(f"  Expansion: {len(variants)} variants; FTS-query={fts_query!r}")
    else:
        fts_query, variants = query, [query]

    # Embed all variants; при сбое — только FTS
    try:
        query_vecs = _embed_queries(client, variants)
    except Exception as e:
        log.warning(f"Эмбеддинг запроса не удался — ищу только по словам: {e}")
        query_vecs = None
        if status is not None:
            status['sem_failed'] = str(e)

    # Both search paths
    # FTS: денойз-запрос из ключевых слов (широкий OR-пул)
    # Semantic: narrow limit (np.maximum.at scans ALL chunks anyway,
    #   limit only controls metadata fetch; keeping it narrow prevents
    #   expansion-polluted results from dominating RRF)
    fts_pool = limit * 3
    fts_results = fts_search(conn, fts_query, limit=fts_pool, year=year, studio=studio, genre=genre, kind=kind)
    sem_results = (semantic_search(conn, query_vecs, limit=limit, year=year, studio=studio, genre=genre, kind=kind)
                   if query_vecs is not None else [])

    # RRF fusion
    rrf_scores = {}
    fts_rank_of, sem_rank_of = {}, {}
    k = RRF_K
    for rank, r in enumerate(fts_results):
        fid = r["film_id"]
        rrf_scores[fid] = rrf_scores.get(fid, 0) + fts_weight / (k + rank + 1)
        fts_rank_of[fid] = rank + 1
    for rank, r in enumerate(sem_results):
        fid = r["film_id"]
        rrf_scores[fid] = rrf_scores.get(fid, 0) + sem_weight / (k + rank + 1)
        sem_rank_of[fid] = rank + 1

    # Merge metadata — semantic first (has cosine score)
    all_meta = {}
    for r in sem_results + fts_results:
        if r["film_id"] not in all_meta:
            all_meta[r["film_id"]] = r
    
    sem_score_map = {r["film_id"]: r.get("sem_score", 0) for r in sem_results}
    
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    ranked_ids = {fid for fid, _ in ranked}
    
    # Guarantee: FTS top-20 always reach the reranker,
    # even if RRF fusion pushed them out (expansion can poison semantic scores)
    fts_guaranteed = 20
    for r in fts_results[:fts_guaranteed]:
        fid = r["film_id"]
        if fid not in ranked_ids:
            rrf = rrf_scores.get(fid, 0)
            ranked.append((fid, rrf))
            ranked_ids.add(fid)
    
    results = []
    for fid, rrf in ranked:
        m = all_meta.get(fid)
        if m:
            result = dict(m)
            result["rrf_score"] = rrf
            result["fts_rank"] = fts_rank_of.get(fid)
            result["sem_rank"] = sem_rank_of.get(fid)
            if fid in sem_score_map:
                result["sem_score"] = sem_score_map[fid]
            results.append(result)
    return results, variants


def fallback_order(candidates):
    """Порядок показа БЕЗ реранкера: слияние пересчитывается весом FTS_WEIGHT_NORERANK по местам
    в каналах (fts_rank / sem_rank из hybrid_search). Используется, когда реранкер недоступен.
    Кандидаты без рангов (чистая семантика) остаются в исходном порядке."""
    w_fts, w_sem = fusion_weights(False)
    k = RRF_K
    def score(c):
        fr, sr = c.get('fts_rank'), c.get('sem_rank')
        if not fr and not sr:
            return c.get('rrf_score', 0.0)
        return (w_fts / (k + fr) if fr else 0.0) + (w_sem / (k + sr) if sr else 0.0)
    return sorted(candidates, key=score, reverse=True)


# ─── Reranker ──────────────────────────────────────────────────────

TOP_RESULTS = 5  # сколько результатов показываем (реранкер ранжирует и помечает уверенностью)


def clip_annotation(text, limit=RERANK_ANN_CHARS):
    """Обрезать аннотацию для реранкера до limit символов по границе предложения (не посреди слова)."""
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    cut = text.rfind('. ', 0, limit)
    if cut < limit // 2:
        cut = text.rfind(' ', 0, limit)
    if cut <= 0:
        return text[:limit] + '…'
    return text[:cut + 1].rstrip() + ' …'


def rerank(client, query, candidates, top_k=TOP_RESULTS, effort="none"):
    """Переранжировать через RERANK_MODEL.

    effort — reasoning_effort: "none" (быстро, без рассуждения) либо "medium"
    (thinking — медленнее, точнее на сложных случаях). RERANK_MODEL должна быть
    reasoning-моделью (gpt-5.5 и т.п.): temperature у таких не поддерживается,
    а бюджет задаётся через max_completion_tokens (reasoning-токены идут из него).

    Возвращает список top_k с полем confidence. Если модель недоступна (3 неудачные
    попытки) — возвращает None: вызывающий показывает fallback_order(candidates).
    """
    if not candidates:
        return []
    
    film_lines = []
    for i, c in enumerate(candidates):
        ann = clip_annotation(c.get('annotation'))
        title = c.get('title', '?')
        year = c.get('year', '?')
        film_lines.append(f"[{i}] «{title}» ({year}): {ann}")

    prompt = f"""Пользователь ищет фильм по описанию: "{query}"

Внимательно прочитай аннотации всех {len(film_lines)} фильмов-кандидатов. Определи, какие из них по СЮЖЕТУ соответствуют запросу. Обращай внимание на:
- Кто совершает действие (субъект), кто объект
- Конкретные сюжетные события, а не просто тематическое сходство
- Воспоминания неточны: роли могут быть перепутаны, связи упрощены, одна деталь (вид спорта, причина события, родство) может быть названа неверно — фильм, совпадающий по остальным событиям, включай в список
- Суди только по тексту аннотации: известность фильма — не довод. Если запрос называет литературный источник (автора, пьесу, роман), подходят и фильмы, у которых аннотация состоит из одной ссылки на этот источник

Верни до {top_k} самых подходящих фильмов по убыванию релевантности. Каждому проставь уверенность совпадения с запросом — одно из: "наиболее вероятно", "возможно", "маловероятно".
Слабые и сомнительные совпадения НЕ отбрасывай — включай их с пометкой "маловероятно". Пустой массив [] возвращай только если ни один фильм не подходит даже отдалённо.
Формат — JSON-массив объектов по убыванию релевантности, без пояснений: [{{"i": 0, "p": "наиболее вероятно"}}, {{"i": 5, "p": "возможно"}}]

ФИЛЬМЫ:

""" + "\n".join(film_lines)
    
    # У reasoning-моделей gpt-5.x reasoning-токены тратятся из max_completion_tokens,
    # поэтому в режиме thinking даём заметно больший бюджет под рассуждение + JSON.
    max_tok = 6000 if effort not in ("none", "minimal") else 1000
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=RERANK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                reasoning_effort=effort,
                max_completion_tokens=max_tok,
            )
            text = response.choices[0].message.content.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            items = json.loads(text)
            if not isinstance(items, list):
                # например {"results": [...]} — это сбой формата, а не «ничего не подходит»:
                # повтор, а после трёх попыток — порядок без реранкера (fallback_order)
                raise ValueError(f"ответ не JSON-массив: {text[:80]!r}")

            reranked = []
            seen = set()
            VALID = {"наиболее вероятно", "возможно", "маловероятно"}
            for it in items:
                if isinstance(it, dict):
                    idx = it.get("i", it.get("index"))
                    conf = str(it.get("p") or it.get("conf") or "").strip().lower()
                else:
                    idx, conf = it, ""
                if conf not in VALID:
                    conf = "возможно"
                try:
                    idx = int(idx)
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(candidates) and idx not in seen:
                    seen.add(idx)
                    item = dict(candidates[idx])
                    item["confidence"] = conf
                    reranked.append(item)
                if len(reranked) >= top_k:
                    break
            return reranked  # top-N по релевантности, каждый с тегом уверенности
        except Exception as e:
            log.warning(f"Rerank error ({attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(1)
            else:
                log.warning("Реранкер недоступен — вызывающий покажет порядок без реранкера (fallback_order)")
                return None


# ─── Stats ─────────────────────────────────────────────────────────

def cmd_stats(args):
    conn = open_db(args.db)
    try:
        films = conn.execute("SELECT COUNT(*) FROM films").fetchone()[0]
        with_ann = conn.execute("SELECT COUNT(*) FROM films WHERE annotation IS NOT NULL AND length(annotation) > 20").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        embedded = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        studios = conn.execute("SELECT studio, COUNT(*) FROM films WHERE studio IS NOT NULL GROUP BY studio ORDER BY COUNT(*) DESC LIMIT 10").fetchall()
        decades = conn.execute("SELECT (year/10)*10 as decade, COUNT(*) FROM films WHERE year IS NOT NULL GROUP BY decade ORDER BY decade").fetchall()
        
        print(f"Фильмов:          {films}")
        print(f"С аннотацией:     {with_ann}")
        print(f"Чанков:           {chunks}")
        print(f"Эмбеддингов:      {embedded} ({'✅' if embedded == chunks else f'⚠ не хватает {chunks - embedded}'})")
        print(f"\nТоп студий:")
        for studio, cnt in studios:
            print(f"  {studio:40s} {cnt}")
        print(f"\nДесятилетия:")
        for decade, cnt in decades:
            print(f"  {decade}–{decade+9}: {cnt}")
    finally:
        conn.close()


# ─── CLI search ─────────────────────────────────────────────────────

def cmd_search(args):
    conn = open_db(args.db)
    client = get_openai_client()
    query = ' '.join(args.query)
    
    try:
        do_expand = (EXPAND_DEFAULT or args.expand) and not args.no_expand
        do_rerank = not args.no_rerank

        print(f"Запрос: {query}")
        if args.year: print(f"Фильтр: десятилетие {(args.year // 10) * 10}-х")
        if args.studio: print(f"Фильтр: студия «{args.studio}»")
        if args.kind: print(f"Фильтр: тип «{args.kind}»")

        fts_w, sem_w = fusion_weights(do_rerank)

        candidates, variants = hybrid_search(
            conn, client, query, limit=50, expand=do_expand,
            year=args.year, studio=args.studio, genre=args.genre, kind=args.kind,
            fts_weight=fts_w, sem_weight=sem_w,
        )
        
        if do_expand and len(variants) > 1:
            print(f"\nExpansion: {len(variants)} вариантов")
            for i, v in enumerate(variants):
                print(f"  {'ORIG' if i == 0 else f'v{i}'}: {v[:80]}")
        
        if do_rerank and candidates:
            effort = getattr(args, 'effort', 'none')
            print(f"\nРеранкинг {len(candidates)} кандидатов через {RERANK_MODEL} (effort={effort})...")
            results = rerank(client, query, candidates, top_k=args.top, effort=effort)
            if results is None:
                print("Реранкер недоступен — показываю порядок без реранкера (по словам и смыслу).")
                results = fallback_order(candidates)[:args.top]
        else:
            results = candidates[:args.top]
        
        for i, r in enumerate(results):
            print(f"\n{'─'*60}")
            tag = f"[{r['confidence']}] " if r.get('confidence') else ""
            print(f"  #{i+1}  {tag}{r.get('title','?')} ({r.get('year', '?')})")
            print(f"  {r.get('genre','')} | {r.get('studio','')} | реж. {r.get('director','')}")
            ann = r.get('annotation', '')
            if ann:
                print(f"  {ann[:300]}")
            scores = []
            if 'sem_score' in r: scores.append(f"cos:{r['sem_score']:.3f}")
            if 'rrf_score' in r: scores.append(f"rrf:{r['rrf_score']:.5f}")
            if scores: print(f"  [{', '.join(scores)}]")
    finally:
        conn.close()


# ─── Web Server ─────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Кинокаталог Госфильмофонда</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23cc2018'/%3E%3Crect x='6' y='5' width='4' height='22' fill='%23ece2cd'/%3E%3Crect x='14' y='5' width='4' height='22' fill='%23ece2cd'/%3E%3Crect x='22' y='5' width='4' height='22' fill='%23ece2cd'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=PT+Serif:ital,wght@0,400;0,700;1,400;1,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#ece2cd;
  --paper-2:#e3d7bc;
  --field:#f7f1e1;
  --ink:#1a1510;
  --ink-soft:#3a3026;
  --ink-dim:#7a6c55;
  --red:#cc2018;
  --red-deep:#a3160f;
  --border:#c3b491;
  --border-dark:#1a1510;
  --fd:'Oswald',-apple-system,sans-serif;
  --fb:'PT Serif',Georgia,'Times New Roman',serif;
  --fm:'JetBrains Mono','SFMono-Regular',Consolas,monospace;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  background:var(--paper);
  color:var(--ink);
  font-family:var(--fb);
  font-size:17px;
  line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.container{max-width:880px;margin:0 auto;padding:34px 26px 90px;}

/* ─── Шапка ─── */
.masthead{margin-bottom:0;}
.mh-top{display:flex;align-items:center;gap:18px;}
.mark{
  width:58px;height:58px;flex:0 0 auto;background:var(--red);position:relative;
}
.mark::before{
  content:"";position:absolute;top:8px;bottom:8px;left:11px;width:8px;
  background:var(--paper);box-shadow:14px 0 0 var(--paper),28px 0 0 var(--paper);
}
.logo{
  margin:0;font-family:var(--fd);font-weight:700;text-transform:uppercase;
  line-height:0.9;letter-spacing:0.005em;
}
.logo-1,.logo-2{display:block;font-size:2.6rem;}
.logo-1{color:var(--ink);}
.logo-2{color:var(--red);}
.mh-rule{height:5px;background:var(--ink);margin:14px 0 9px;}
.mh-sub{
  font-family:var(--fd);font-weight:500;text-transform:uppercase;
  letter-spacing:0.16em;font-size:0.74rem;color:var(--ink-soft);
}
.mh-sub .hl{color:var(--red);font-weight:600;}

/* ─── Плёночная лента ─── */
.filmstrip{
  height:30px;background:var(--ink);position:relative;margin:18px 0 26px;
}
.filmstrip::before,.filmstrip::after{
  content:"";position:absolute;left:0;right:0;height:7px;
  background-image:repeating-linear-gradient(to right,var(--paper) 0 10px,transparent 10px 20px);
}
.filmstrip::before{top:5px;}
.filmstrip::after{bottom:5px;}

/* ─── Примечание про телефильмы ─── */
.tvnote{
  border-left:6px solid var(--red);background:var(--paper-2);
  padding:12px 16px;margin:0 0 30px;font-size:0.95rem;color:var(--ink-soft);
}
.tvnote-h{
  font-family:var(--fd);font-weight:600;text-transform:uppercase;
  letter-spacing:0.05em;color:var(--red);font-size:0.9rem;margin-right:6px;
}

/* ─── Блок поиска ─── */
.ask{display:flex;gap:13px;align-items:stretch;margin-bottom:6px;}
.ask-bar{width:8px;flex:0 0 auto;background:var(--red);}
.ask-h{margin:0;font-family:var(--fd);font-weight:600;text-transform:uppercase;
  letter-spacing:0.01em;font-size:1.55rem;line-height:1.05;}
.ask-1{color:var(--ink);}
.ask-2{color:var(--red);}
.ask-note{margin:0 0 16px 21px;font-style:italic;color:var(--ink-dim);font-size:0.98rem;}
.search-row{display:flex;gap:12px;margin-bottom:13px;}
.q-input{
  flex:1;background:var(--field);border:2px solid var(--ink);color:var(--ink);
  font-family:var(--fb);font-size:1.05rem;padding:13px 16px;outline:none;border-radius:0;
}
.q-input::placeholder{color:#a99c82;font-style:italic;}
.q-input:focus{border-color:var(--red);}
.find-btn{
  background:var(--red);color:var(--field);border:none;cursor:pointer;
  font-family:var(--fd);font-weight:600;text-transform:uppercase;letter-spacing:0.08em;
  font-size:1.02rem;padding:0 30px;border-radius:0;transition:background .12s;
}
.find-btn:hover{background:var(--red-deep);}
.find-btn:disabled{background:var(--ink-dim);cursor:default;}
.examples{display:flex;flex-wrap:wrap;align-items:center;gap:14px;font-size:0.92rem;}
.ex-label{font-family:var(--fd);font-weight:500;text-transform:uppercase;
  letter-spacing:0.1em;font-size:0.74rem;color:var(--ink-dim);}
.ex{color:var(--ink-soft);text-decoration:underline;text-decoration-color:var(--border);
  text-underline-offset:3px;cursor:pointer;font-style:italic;}
.ex:hover{color:var(--red);text-decoration-color:var(--red);}

/* ─── Боксы-подсказки ─── */
.box{border:1.5px solid var(--border-dark);background:transparent;padding:20px 22px;margin:28px 0;}
.box-h{margin:0 0 12px;font-family:var(--fd);font-weight:600;text-transform:uppercase;
  letter-spacing:0.07em;font-size:0.96rem;color:var(--ink);}
.box-h .bullet{color:var(--red);margin-right:6px;font-size:0.7em;vertical-align:middle;}
.box-intro{margin:0 0 16px;font-size:0.97rem;color:var(--ink-soft);}
.box-foot{margin:16px 0 0;padding-top:13px;border-top:1px solid var(--border);
  font-size:0.9rem;font-style:italic;color:var(--ink-dim);}
.cols{display:flex;gap:30px;}
.col{flex:1;min-width:0;}
.badge{display:inline-block;font-family:var(--fd);font-weight:600;text-transform:uppercase;
  letter-spacing:0.08em;font-size:0.72rem;padding:3px 10px;margin-bottom:10px;color:var(--field);}
.badge-yes{background:var(--red);}
.badge-no{background:var(--ink);}
.tips{list-style:none;margin:0;padding:0;}
.tips li{position:relative;padding-left:20px;margin-bottom:9px;font-size:0.92rem;line-height:1.4;color:var(--ink-soft);}
.tips li::before{position:absolute;left:0;top:-1px;font-family:var(--fd);font-weight:700;font-size:1.05em;}
.tips-yes li::before{content:"+";color:var(--red);}
.tips-no li::before{content:"\2212";color:var(--ink);}
.sub-r{margin:16px 0 5px;font-family:var(--fd);font-weight:600;text-transform:uppercase;
  letter-spacing:0.07em;font-size:0.82rem;color:var(--red);}
.box-p{margin:0;font-size:0.93rem;color:var(--ink-soft);}

/* ─── Фильтры ─── */
.filters{margin:26px 0;}
.filter-selects{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px;}
.sel{
  appearance:none;-webkit-appearance:none;
  background-color:var(--field);
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='7' viewBox='0 0 10 7'%3E%3Cpath d='M0 0h10L5 7z' fill='%23cc2018'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 11px center;
  border:1.5px solid var(--ink);color:var(--ink);font-family:var(--fb);font-size:0.95rem;
  padding:9px 30px 9px 13px;border-radius:0;outline:none;cursor:pointer;
}
.sel:focus{border-color:var(--red);}

/* ─── Статус / прогресс / уведомление ─── */
.status{font-family:var(--fm);font-size:0.82rem;color:var(--ink-dim);margin:18px 0 6px;min-height:1em;}
.status.busy{color:var(--ink);}
.status.err{color:var(--red);}
.notice{font-size:0.9rem;color:var(--ink);background:var(--paper-2);border-left:3px solid var(--red);
  padding:8px 12px;margin:0 0 12px;}
.progress{height:4px;background:var(--paper-2);position:relative;overflow:hidden;margin:0 0 8px;display:none;}
.progress.on{display:block;}
.progress::after{content:"";position:absolute;top:0;left:-40%;width:40%;height:100%;background:var(--red);
  animation:slide 1.4s ease-in-out infinite;}
@keyframes slide{0%{left:-40%;}100%{left:100%;}}
.stages{font-family:var(--fd);font-weight:500;text-transform:uppercase;letter-spacing:0.06em;font-size:0.72rem;
  color:var(--ink-dim);margin:0 0 14px;display:none;}
.stages.on{display:block;}
.stages b{color:var(--red);font-weight:600;}
.empty{padding:16px 0;font-style:italic;color:var(--ink-dim);border-top:1px solid var(--border);border-bottom:1px solid var(--border);}

/* ─── Результаты ─── */
#results{margin-top:10px;}
.result{padding:20px 0;border-bottom:1px solid var(--border);}
.result:first-child{border-top:1px solid var(--border);}
.result-header{display:flex;justify-content:space-between;align-items:baseline;gap:16px;}
.result-title{font-family:var(--fd);font-weight:600;font-size:1.12rem;color:var(--ink);
  line-height:1.3;display:flex;align-items:baseline;flex-wrap:wrap;gap:4px;}
.rank-badge{display:inline-flex;align-items:center;justify-content:center;
  width:25px;height:25px;flex:0 0 auto;background:var(--red);color:var(--field);
  border-radius:50%;font-family:var(--fd);font-weight:600;font-size:0.8rem;
  margin-right:9px;transform:translateY(-1px);}
.conf{display:inline-block;font-family:var(--fd);font-weight:600;text-transform:uppercase;
  letter-spacing:0.06em;font-size:0.66rem;padding:2px 8px;margin-left:9px;
  transform:translateY(-2px);}
.conf-high{background:var(--red);color:var(--field);}
.conf-mid{background:var(--ink);color:var(--field);}
.conf-low{background:transparent;color:var(--ink-dim);border:1px solid var(--ink-dim);}

.result-meta{font-family:var(--fd);font-weight:400;text-transform:uppercase;letter-spacing:0.05em;
  font-size:0.75rem;color:var(--ink-dim);margin:7px 0 0 34px;}
.result-ann{margin:9px 0 0 34px;font-size:0.97rem;color:var(--ink-soft);line-height:1.55;}
.result-ann.collapsed{max-height:4.7em;overflow:hidden;
  -webkit-mask-image:linear-gradient(to bottom,#000 62%,transparent);
  mask-image:linear-gradient(to bottom,#000 62%,transparent);}
.toggle-ann{display:inline-block;margin:6px 0 0 34px;font-family:var(--fd);font-weight:500;
  text-transform:uppercase;letter-spacing:0.06em;font-size:0.72rem;color:var(--red);cursor:pointer;}
.sources-note{margin:14px 0 0;font-size:0.84rem;color:var(--ink-dim);}.sources-note a,.result-src a{color:var(--ink-soft);text-decoration:underline;text-decoration-color:var(--border);text-underline-offset:3px;}.result-src{margin:4px 0 0 34px;font-size:0.82rem;color:var(--ink-dim);}
.toggle-ann:hover{color:var(--red-deep);}

/* ─── Нижняя статистика ─── */
.stats-bar{margin-top:34px;padding-top:14px;border-top:2px solid var(--ink);
  font-family:var(--fm);font-size:0.78rem;color:var(--ink-dim);text-align:center;letter-spacing:0.02em;}

@media (max-width:620px){
  .container{padding:24px 16px 70px;}
  .logo-1,.logo-2{font-size:1.9rem;}
  .cols{flex-direction:column;gap:22px;}
  .search-row{flex-direction:column;}
  .find-btn{padding:13px 0;}
}
</style>
</head>
<body>
<div class="container">

  <header class="masthead">
    <div class="mh-top">
      <div class="mark" aria-hidden="true"></div>
      <h1 class="logo"><span class="logo-1">Кинокаталог</span><span class="logo-2">Госфильмофонда</span></h1>
    </div>
    <div class="mh-rule"></div>
    <div class="mh-sub">Советское кино и телевидение · <span class="hl">__YEARS__</span> · Кинофильмы, телефильмы, телеспектакли, мультфильмы</div>
  </header>

  <div class="filmstrip" aria-hidden="true"></div>

  <div class="tvnote">
    <span class="tvnote-h">Откуда аннотации.</span>Кинофильмы 1918&ndash;1987 &mdash; из печатных каталогов Госфильмофонда; телефильмы, телеспектакли, мультфильмы и фильмы 1988&ndash;1991 &mdash; из других источников, часть аннотаций краткие.
  </div>

  <section class="search">
    <div class="ask">
      <span class="ask-bar" aria-hidden="true"></span>
      <h2 class="ask-h"><span class="ask-1">Ищешь фильм?</span> <span class="ask-2">Опиши своими словами.</span></h2>
    </div>
    <p class="ask-note">Сюжет, сцена, профессия героя — как запомнилось. Память неточна, поиск делает на это поправку.</p>
    <div class="search-row">
      <input type="text" id="q" class="q-input" placeholder="например: лётчики поют в самодеятельном хоре" autocomplete="off" autofocus>
      <button id="btn" class="find-btn" onclick="doSearch()">Найти</button>
    </div>
    <div class="examples">
      <span class="ex-label">Например:</span>
      <span class="ex" onclick="setQ('средневековый живописец странствует по Руси и видит жестокость')">живописец на Руси</span>
      <span class="ex" onclick="setQ('охотник убил дочь')">охотник убил дочь</span>
      <span class="ex" onclick="setQ('мальчик дружит с лошадью в горах')">мальчик и лошадь</span>
    </div>
  </section>

  <section class="filters">
    <div class="filter-selects">
      <select id="f-year" class="sel" title="Десятилетие производства">
        <option value="">Все десятилетия</option>
        <option value="1910">1910-е</option>
        <option value="1920">1920-е</option>
        <option value="1930">1930-е</option>
        <option value="1940">1940-е</option>
        <option value="1950">1950-е</option>
        <option value="1960">1960-е</option>
        <option value="1970">1970-е</option>
        <option value="1980">1980-е</option>
        <option value="1990">1990–1991</option>
      </select>
      <select id="f-studio" class="sel" title="Студия">
        <option value="">Любая студия</option>
        <option value="Мосфильм">Мосфильм</option>
        <option value="Ленфильм">Ленфильм</option>
        <option value="Горького">им. Горького</option>
        <option value="Одесская">Одесская</option>
        <option value="Довженко">им. Довженко</option>
        <option value="Беларусьфильм">Беларусьфильм</option>
        <option value="Грузия-фильм">Грузия-фильм</option>
        <option value="Арменфильм">Арменфильм</option>
        <option value="Азербайджанфильм">Азербайджанфильм</option>
        <option value="Узбекфильм">Узбекфильм</option>
        <option value="Казахфильм">Казахфильм</option>
        <option value="Туркменфильм">Туркменфильм</option>
        <option value="Таджикфильм">Таджикфильм</option>
        <option value="Киргизфильм">Киргизфильм</option>
        <option value="Молдова-фильм">Молдова-фильм</option>
        <option value="Таллинфильм">Таллинфильм</option>
        <option value="Рижская">Рижская</option>
        <option value="Литовская">Литовская</option>
        <option value="Свердловская">Свердловская</option>
      </select>
      <select id="f-kind" class="sel" title="Тип">
        <option value="">Любой тип</option>
        <option value="кинофильм">кинофильмы</option>
        <option value="телефильм">телефильмы</option>
        <option value="фильм-спектакль">телеспектакли</option>
        <option value="мультфильм">мультфильмы</option>
        <option value="не игровое">неигровые (концерты, хроника)</option>
        <option value="фильм-опера/балет">фильмы-оперы и балеты</option>
      </select>
      <select id="f-genre" class="sel" title="Жанр">
        <option value="">Любой жанр</option>
        <option value="драма">драма</option>
        <option value="комедия">комедия</option>
        <option value="мелодрама">мелодрама</option>
        <option value="детектив">детектив</option>
        <option value="приключен">приключения</option>
        <option value="киноповесть">киноповесть</option>
        <option value="экраниз">экранизация</option>
        <option value="сказка">сказка</option>
        <option value="музык">музыкальный</option>
        <option value="военн">военный</option>
        <option value="историч">исторический</option>
        <option value="биограф">биографический</option>
        <option value="фантаст">фантастика</option>
        <option value="революцион">историко-революционный</option>
      </select>
    </div>
  </section>

  <!-- Результаты — сразу под полем поиска и фильтрами, чтобы не искать их внизу страницы -->
  <div id="status" class="status" aria-live="polite"></div>
  <div id="progress" class="progress" aria-hidden="true"></div>
  <div id="stages" class="stages"></div>
  <div id="notice" class="notice" hidden></div>
  <div id="results"></div>
  <p class="sources-note">Аннотации — из каталогов Госфильмофонда, с сайтов <a href="https://gosfilmofond.ru/films/">gosfilmofond.ru</a>, <a href="https://animator.ru/">Аниматор.ру</a>, kino-teatr.ru и из Википедии (тексты Википедии — по лицензии <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ru">CC BY-SA 4.0</a>). Ссылка на источник аннотации — у фильма.</p>

  <section class="box">
    <h3 class="box-h"><span class="bullet">&#9679;</span>Как искать: что писать в запросе</h3>
    <p class="box-intro">Поиск идёт по сюжетным аннотациям печатного каталога — описывай то, что происходит на экране, как пересказал бы сюжет своими словами. Сначала по словам и по смыслу отбираются несколько десятков похожих аннотаций, затем модель перечитывает их и показывает пять самых подходящих с пометкой уверенности: наиболее вероятно / возможно / маловероятно. Обычно это занимает 2–5 секунд.</p>
    <div class="cols">
      <div class="col">
        <span class="badge badge-yes">Работает</span>
        <ul class="tips tips-yes">
          <li>конкретные события и действия: «охотник случайно убивает дочь»</li>
          <li>профессии и роли героев: «председатель колхоза», «фронтовик», «студентка»</li>
          <li>место и обстановка: «полярная станция», «коммуналка», «целина»</li>
          <li>кто и над кем действует: «отец ищет сына», а не просто «поиски»</li>
          <li>слова из названия, если помнишь хотя бы часть</li>
        </ul>
      </div>
      <div class="col">
        <span class="badge badge-no">Не работает</span>
        <ul class="tips tips-no">
          <li>имена актёров и режиссёров — в аннотациях их нет</li>
          <li>цитаты и реплики из фильма</li>
          <li>музыка, цвет плёнки, операторская работа</li>
          <li>оценки и настроение: «добрый», «атмосферный», «культовый»</li>
          <li>вводные обороты: «помогите найти фильм, где…» — сразу к делу</li>
        </ul>
      </div>
    </div>
    <p class="box-foot">Одна точная деталь сильнее трёх размытых. Не уверен в детали — опусти её: память путает роли, реранкер делает на это поправку. Жанр и десятилетие задавай фильтрами под полем поиска, а не словами в запросе.</p>
  </section>

  <div class="stats-bar" id="statsBar">__STATS__ · аннотированный каталог Госфильмофонда и другие источники</div>

</div>

<script>
const q = document.getElementById('q');
function setQ(t) { q.value = t; doSearch(); }
q.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

let ticker = null;
function setBusy(on) {
  const btn = document.getElementById('btn');
  const bar = document.getElementById('progress');
  const stg = document.getElementById('stages');
  btn.disabled = on;
  btn.textContent = on ? 'Ищу…' : 'Найти';
  bar.classList.toggle('on', on);
  stg.classList.toggle('on', on);
  if (on) stg.innerHTML = '<b>Идёт поиск</b> · отбор по словам и смыслу → перечитывание кандидатов · обычно 2–5 с';
}
function ensureVisible(el) {
  // подкручиваем страницу только если строка статуса ушла за край экрана; поле поиска при этом остаётся видно
  const r = el.getBoundingClientRect();
  if (r.top < 0 || r.top > window.innerHeight - 60) el.scrollIntoView({behavior: 'smooth', block: 'center'});
}

async function doSearch() {
  const query = q.value.trim();
  if (!query) { q.focus(); return; }
  const btn = document.getElementById('btn');
  if (btn.disabled) return;   // поиск уже идёт — повторный клик игнорируем
  const statusEl = document.getElementById('status');
  const noticeEl = document.getElementById('notice');
  const resultsEl = document.getElementById('results');
  resultsEl.innerHTML = '';
  noticeEl.hidden = true; noticeEl.textContent = '';
  statusEl.className = 'status busy';
  const t0 = performance.now();
  statusEl.textContent = 'Ищу… 0.0 с';
  if (ticker) clearInterval(ticker);
  ticker = setInterval(() => { statusEl.textContent = 'Ищу… ' + ((performance.now() - t0) / 1000).toFixed(1) + ' с'; }, 100);

  // Один режим для всех: слова + смысл → перечитывание кандидатов. Настраиваются только фильтры.
  const body = {
    query,
    year: parseInt(document.getElementById('f-year').value) || null,
    studio: document.getElementById('f-studio').value.trim() || null,
    genre: document.getElementById('f-genre').value.trim() || null,
    kind: document.getElementById('f-kind').value || null,
  };

  setBusy(true);
  ensureVisible(statusEl);

  try {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (!resp.ok) throw new Error('сервер ответил ' + resp.status + ' ' + resp.statusText);
    const data = await resp.json();
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
    clearInterval(ticker); ticker = null;
    setBusy(false);
    statusEl.className = 'status';

    if (data.error) {
      statusEl.className = 'status err';
      statusEl.textContent = `Ошибка: ${data.error} (${elapsed} с)`;
      return;
    }

    const n = data.results.length;
    const word = n % 10 === 1 && n % 100 !== 11 ? 'результат' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'результата' : 'результатов');
    statusEl.textContent = `${n} ${word} · ${elapsed} с`;
    if (data.notice) { noticeEl.textContent = data.notice; noticeEl.hidden = false; }

    const confBadge = (c) => {
      if (!c) return '';
      const cls = c === 'наиболее вероятно' ? 'conf-high'
                : c === 'маловероятно' ? 'conf-low' : 'conf-mid';
      return '<span class="conf ' + cls + '">' + esc(c) + '</span>';
    };
    let html = '';
    data.results.forEach((r, i) => {
      const ann = r.annotation || '';
      const needCollapse = ann.length > 250;
      const meta = [r.genre, r.studio, r.director ? 'реж. ' + r.director : ''].filter(Boolean).join(' · ');

      html += '<div class="result">' +
        '<div class="result-header">' +
          '<div class="result-title"><span class="rank-badge">' + (i+1) + '</span>' +
            esc(r.title || '?') + ' (' + (r.year || '?') + ')' + confBadge(r.confidence) + '</div>' +
        '</div>' +
        (meta ? '<div class="result-meta">' + esc(meta) + '</div>' : '') +
        '<div class="result-ann' + (needCollapse ? ' collapsed' : '') + '" id="ann-' + i + '">' +
          esc(ann) + '</div>' +
        (needCollapse ? '<span class="toggle-ann" onclick="toggleAnn(' + i + ')">показать</span>' : '') +
        (r.source ? '<div class="result-src"><a href="' + esc(r.source).replace(/"/g, '&quot;') + '" target="_blank" rel="noopener">источник</a></div>' : '') +
      '</div>';
    });
    resultsEl.innerHTML = html || '<div class="empty">Ничего не нашлось. Попробуй другую деталь сюжета, убери сомнительные подробности или сними фильтры.</div>';
    ensureVisible(statusEl);
  } catch(e) {
    clearInterval(ticker); ticker = null;
    setBusy(false);
    statusEl.className = 'status err';
    statusEl.textContent = 'Ошибка: ' + e.message + ' — сервер запущен? (окно с film_search.py serve должно быть открыто)';
  }
}

function toggleAnn(i) { document.getElementById('ann-' + i).classList.toggle('collapsed'); }
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
</script>
</body>
</html>"""


def _flag(value, default):
    """Флаг из JSON: true/false, 1/0 или строки «true»/«false» («false» — это False, а не непустая строка)."""
    if value is None:
        return default
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ('true', '1', 'yes', 'on'):
            return True
        if v in ('false', '0', 'no', 'off', ''):
            return False
        return default
    return bool(value)


def cmd_serve(args):
    """Запустить веб-интерфейс."""
    try:
        from flask import Flask, request as flask_request, jsonify
    except ImportError:
        print("pip install flask", file=sys.stderr)
        sys.exit(1)
    
    db_path = args.db
    client = get_openai_client()
    
    # Startup: stats + preload index, then close conn
    startup_conn = open_db(db_path)
    _get_morph()  # прогрев словаря pymorphy — первый запрос не платит за загрузку
    mode = _fts_mode(startup_conn)
    if _get_morph() is None:
        log.warning("pymorphy3 не установлен: FTS-канал ищет только по точным словоформам. "
                    "Установи: python -m pip install pymorphy3 pymorphy3-dicts-ru — и перезапусти serve (индекс пересоберётся сам).")
    elif mode != 'lemmas':
        log.warning(f"FTS-индекс в состоянии «{mode}» (собран без лемм или устарел) — пересобираю по леммам, ~1–2 минуты (разово)...")
        build_fts(startup_conn)
    films_count = startup_conn.execute("SELECT COUNT(*) FROM films").fetchone()[0]
    year_span = startup_conn.execute("SELECT MIN(year), MAX(year) FROM films WHERE year IS NOT NULL").fetchone()
    chunks_count = startup_conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    embedded_count = startup_conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    if embedded_count < chunks_count:
        log.warning(f"Эмбеддингов {embedded_count} из {chunks_count} чанков — семантический канал неполный; "
                    "выполни: python film_search.py embed --resume")
    _load_index(startup_conn)
    startup_conn.close()
    
    app = Flask(__name__)
    
    stats_str = f"{films_count} фильмов · {chunks_count} чанков · {embedded_count} эмбеддингов"
    # Подпись внизу страницы — без технических слов (чанки, эмбеддинги): только объём базы и годы
    page_stats = f"{films_count} фильмов" + (f" {year_span[0]}–{year_span[1]} годов" if year_span and year_span[0] and year_span[1] else "")
    years = f"{year_span[0]}&ndash;{year_span[1]}" if year_span and year_span[0] and year_span[1] else ""
    html = HTML_TEMPLATE.replace('__STATS__', page_stats).replace('__YEARS__', years)

    @app.route('/')
    def index():
        return html

    @app.route('/search', methods=['POST'])
    def api_search():
        # Тело запроса проверяется по типам: [] или {"query": 123} — это пустой ответ, а не ошибка 500
        data = flask_request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        query = data.get('query')
        query = query.strip() if isinstance(query, str) else ''
        if not query:
            return jsonify({'results': [], 'variants': []})

        # Интерфейс работает в одном режиме: слова + смысл → реранкер. Параметры ниже интерфейс
        # не передаёт; они приняты только для скриптов и отладки (bench_search.py, curl).
        do_expand = _flag(data.get('expand'), EXPAND_DEFAULT)
        rerank_mode = data.get('rerank_mode', 'fast')   # 'fast' | 'thinking' | 'off'
        if rerank_mode not in ('fast', 'thinking', 'off'):
            rerank_mode = 'fast'
        do_rerank = rerank_mode != 'off'
        rerank_effort = 'medium' if rerank_mode == 'thinking' else 'none'
        do_fts = _flag(data.get('fts'), True)

        # Sanitize filter params
        year = data.get('year')
        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None
        studio = data.get('studio') if isinstance(data.get('studio'), str) else None
        genre = data.get('genre') if isinstance(data.get('genre'), str) else None
        studio, genre = (studio or '').strip() or None, (genre or '').strip() or None
        kind = data.get('kind') if data.get('kind') in KINDS else None
        
        # Per-request connection (thread-safe, no schema — already created at startup)
        conn = open_db(db_path, schema=False)
        try:
            t0 = time.time()
            status = {}      # hybrid_search пишет сюда sem_failed, если эмбеддинг запроса не удался
            degraded = []    # что отказало: 'semantic' и/или 'rerank'

            # Веса слияния: без реранкера FTS ведёт (см. FTS_WEIGHT_* в начале файла)
            fts_w, sem_w = fusion_weights(do_rerank)

            if do_fts:
                candidates, variants = hybrid_search(
                    conn, client, query, limit=50, expand=do_expand,
                    year=year, studio=studio, genre=genre, kind=kind,
                    fts_weight=fts_w, sem_weight=sem_w, status=status,
                )
                if status.get('sem_failed'):
                    degraded.append('semantic')
            else:
                if do_expand:
                    _, variants = expand_query(client, query)
                else:
                    variants = [query]
                query_vecs = _embed_queries(client, variants)
                candidates = semantic_search(
                    conn, query_vecs, limit=50, year=year, studio=studio, genre=genre, kind=kind,
                )

            if do_rerank and candidates:
                results = rerank(client, query, candidates, top_k=TOP_RESULTS, effort=rerank_effort)
                if results is None:
                    degraded.append('rerank')
                    results = fallback_order(candidates)[:TOP_RESULTS]
            else:
                results = candidates[:TOP_RESULTS]

            # Запасной ход (автоматический, не выбирается пользователем): без сервиса ИИ показываем
            # список по совпадению слов и честно говорим об этом.
            notice = None
            if 'rerank' in degraded:
                notice = ('Сервис переоценки (ИИ) сейчас недоступен — показан список по совпадению слов'
                          + (' и смысла' if 'semantic' not in degraded else '')
                          + ', без пометок уверенности. Повтори запрос через минуту.')
            elif 'semantic' in degraded:
                notice = 'Смысловой поиск сейчас недоступен — найдено только по совпадению слов.'

            elapsed = time.time() - t0
            log.info(f"  [{elapsed:.1f}s] '{query[:50]}' → {len(results)} results"
                     + (f" (запасной ход: {', '.join(degraded)})" if degraded else ''))

            return jsonify({
                'elapsed': round(elapsed, 1),
                'candidates': len(candidates),
                'degraded': degraded,
                'notice': notice,
                'results': [{
                    'title': r.get('title', ''),
                    'genre': r.get('genre', ''),
                    'year': r.get('year'),
                    'studio': r.get('studio', ''),
                    'director': r.get('director', ''),
                    'annotation': r.get('annotation', ''),
                    'sem_score': round(r.get('sem_score', 0), 4) if 'sem_score' in r else None,
                    'rrf_score': round(r.get('rrf_score', 0), 6) if 'rrf_score' in r else None,
                    'confidence': r.get('confidence'),
                } for r in results],
                'variants': variants,
            })
        except Exception as e:
            log.exception("Search error")
            return jsonify({'results': [], 'variants': [], 'error': str(e)})
        finally:
            conn.close()
    
    url = f"http://localhost:{args.port}"
    print(f"\n  {url}")
    print(f"  {stats_str}")
    if args.host not in ('127.0.0.1', 'localhost'):
        print(f"  (сервер открыт для локальной сети: {args.host}:{args.port})")
    if not args.no_browser:
        # Браузер открываем ИЗ сервера, когда порт уже слушается (bat-файл открывал его раньше старта —
        # Chrome показывал «не удаётся получить доступ к сайту» и страницу никто не обновлял).
        import threading
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=False)


# ─── Reindex FTS ────────────────────────────────────────────────────

def cmd_reindex_fts(args):
    """Пересобрать лемматизированный FTS-индекс из существующей базы (без re-embed)."""
    if _get_morph() is None and not args.force:
        print("pymorphy3 не установлен — индекс получился бы без лемм. Установи: python -m pip install pymorphy3 pymorphy3-dicts-ru "
              "(или запусти с --force, чтобы собрать по словоформам).", file=sys.stderr)
        sys.exit(1)
    conn = open_db(args.db)
    try:
        build_fts(conn)
        print("Готово: FTS-индекс по леммам пересобран. Повторный embed не нужен.")
    finally:
        conn.close()


# ─── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Госфильмофонд — поиск фильмов')
    parser.add_argument('--db', default=DB_PATH, help=f'Путь к БД (по умолчанию {DB_PATH})')
    sub = parser.add_subparsers(dest='cmd')
    
    p_import = sub.add_parser('import', help='Импорт JSON-каталогов в SQLite')
    p_import.add_argument('catalogs', nargs='+', help='JSON-файлы каталогов')
    p_import.add_argument('--dry-run', action='store_true', help='Только отчёт: что добавится и изменится, без записи в базу')
    
    p_embed = sub.add_parser('embed', help='Генерация эмбеддингов')
    p_embed.add_argument('--resume', action='store_true', help='Продолжить прерванную генерацию')
    
    p_search = sub.add_parser('search', help='Поиск из командной строки')
    p_search.add_argument('query', nargs='+', help='Описание фильма')
    p_search.add_argument('--top', type=int, default=10)
    p_search.add_argument('--expand', action='store_true', help='Включить расширение запроса (по умолчанию выключено)')
    p_search.add_argument('--no-expand', action='store_true', help=argparse.SUPPRESS)  # оставлен для совместимости
    p_search.add_argument('--no-rerank', action='store_true')
    p_search.add_argument('--effort', default='none', choices=['none', 'low', 'medium', 'high', 'xhigh'],
                          help='reasoning_effort реранкера (none=быстро, medium=thinking)')
    p_search.add_argument('--year', type=int, help='Фильтр по десятилетию')
    p_search.add_argument('--studio', help='Фильтр по студии')
    p_search.add_argument('--genre', help='Фильтр по жанру')
    p_search.add_argument('--kind', choices=KINDS, help='Фильтр по типу фильма')
    
    p_serve = sub.add_parser('serve', help='Веб-интерфейс')
    p_serve.add_argument('--port', type=int, default=8080)
    p_serve.add_argument('--host', default='127.0.0.1',
                         help='Адрес для прослушивания: 127.0.0.1 — только этот компьютер (по умолчанию); 0.0.0.0 — вся локальная сеть')
    p_serve.add_argument('--no-browser', action='store_true', help='Не открывать браузер автоматически')
    
    sub.add_parser('stats', help='Статистика базы')
    p_reindex = sub.add_parser('reindex-fts', help='Пересобрать лемматизированный FTS-индекс (без re-embed)')
    p_reindex.add_argument('--force', action='store_true', help='Собрать даже без pymorphy3 (по словоформам)')
    
    args = parser.parse_args()
    
    if args.cmd == 'import':
        cmd_import(args)
    elif args.cmd == 'embed':
        cmd_embed(args)
    elif args.cmd == 'search':
        cmd_search(args)
    elif args.cmd == 'serve':
        cmd_serve(args)
    elif args.cmd == 'stats':
        cmd_stats(args)
    elif args.cmd == 'reindex-fts':
        cmd_reindex_fts(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
