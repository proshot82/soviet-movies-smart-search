#!/usr/bin/env python3
"""
Семантический поиск фильмов Госфильмофонда — SQLite + FTS5 + Embeddings.

Команды:
  python film_search.py import catalog.json          # Импорт JSON → SQLite
  python film_search.py import cat1.json cat2.json   # Несколько каталогов
  python film_search.py embed                        # Генерация эмбеддингов
  python film_search.py embed --resume               # Продолжить прерванную генерацию
  python film_search.py stats                        # Статистика базы
  python film_search.py reindex-fts                  # Пересобрать FTS-индекс по леммам (без re-embed)

Поиск для пользователей — только сайт на GitHub Pages (docs/, движок docs/engine.js). Здесь — пополнение
базы и эталонная реализация того же поиска для pages/check_parity.py и bench/bench_search.py.

Требования: pip install openai numpy pymorphy3 pymorphy3-dicts-ru
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
RERANK_MODEL = "gpt-5.6-terra"
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
                    "После установки: python film_search.py reindex-fts.")
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
            "source": source_url(src), **extra}


def source_url(src):
    """Первый URL в films.source («список.xlsx; https://animator.ru/…») или пустая строка."""
    m = re.search(r"https?://\S+", src or "")
    return m.group(0).rstrip(";,") if m else ""


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
    reasoning-моделью (gpt-5.x): temperature у таких не поддерживается,
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


# ─── Delete ─────────────────────────────────────────────────────────

def cmd_delete(args):
    """Удалить фильмы (вместе с чанками и эмбеддингами) — например, иностранные записи, попавшие в базу по ошибке.
    Фильмы каталогов ГФФ (film_id < 7175) не удаляются."""
    conn = open_db(args.db)
    try:
        rows = conn.execute(f"SELECT film_id, title, year, kind, country FROM films WHERE film_id IN "
                            f"({','.join('?' * len(args.ids))}) ORDER BY film_id", args.ids).fetchall()
        missing = sorted(set(args.ids) - {r[0] for r in rows})
        if missing:
            print(f"film_id нет в базе: {missing}", file=sys.stderr)
        closed = [r for r in rows if r[0] < 7175]
        if closed:
            print(f"Фильмы каталогов ГФФ (film_id < 7175) не удаляются: {[r[0] for r in closed]}", file=sys.stderr)
            sys.exit(1)
        for fid, title, year, kind, country in rows:
            print(f"  {fid}  {title} ({year}, {kind}, {country or '—'})")
        if args.dry_run:
            print(f"--dry-run: к удалению {len(rows)}, ничего не удалено")
            return
        for fid, *_ in rows:
            conn.execute("DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE film_id = ?)", (fid,))
            conn.execute("DELETE FROM chunks WHERE film_id = ?", (fid,))
            conn.execute("DELETE FROM films WHERE film_id = ?", (fid,))
        conn.commit()
        build_fts(conn)
        print(f"Удалено фильмов: {len(rows)}; FTS-индекс пересобран")
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
    
    sub.add_parser('stats', help='Статистика базы')
    p_reindex = sub.add_parser('reindex-fts', help='Пересобрать лемматизированный FTS-индекс (без re-embed)')
    p_reindex.add_argument('--force', action='store_true', help='Собрать даже без pymorphy3 (по словоформам)')
    p_delete = sub.add_parser('delete', help='Удалить фильмы по film_id (только film_id >= 7175)')
    p_delete.add_argument('ids', nargs='+', type=int)
    p_delete.add_argument('--dry-run', action='store_true')
    
    args = parser.parse_args()
    
    if args.cmd == 'import':
        cmd_import(args)
    elif args.cmd == 'embed':
        cmd_embed(args)
    elif args.cmd == 'stats':
        cmd_stats(args)
    elif args.cmd == 'reindex-fts':
        cmd_reindex_fts(args)
    elif args.cmd == 'delete':
        cmd_delete(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
