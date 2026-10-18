# db_check.py  (редакция Ф6-П3, 04.09.2026)
# Диагностика живой базы движка. Кроме gosfilmofond.db ничего не нужно.
# Показывает: размер базы, какие слои-каталоги в ней лежат, точные дубли
# и гистограмму по годам (видно дыры). Эталон — финальный каталог Ф6:
# catalog_final_v2.json = 7174 фильма; дублей title+year — 3 законные пары
# (разные фильмы разных студий), дублей title+year+studio — 0.
#
# Запуск:  python db_check.py
# (положи рядом с gosfilmofond.db; если база в другом месте - впиши путь в строке DB)

import sqlite3, os
from collections import Counter

DB = "gosfilmofond.db"
EXPECTED_FILMS = 7174
LEGIT_DUPS = {("Красная звезда", 1919), ("Интернационал", 1932), ("Клиника", 1987)}
if not os.path.exists(DB):
    raise SystemExit("[ОШИБКА] нет gosfilmofond.db рядом со скриптом. "
                     "Положи скрипт в папку движка или впиши полный путь в строке DB вверху.")

conn = sqlite3.connect(DB)

def count(table):
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return "(нет таблицы)"

print("=== РАЗМЕР БАЗЫ ===")
films = count('films')
print(f"фильмов: {films} | чанков: {count('chunks')} | "
      f"эмбеддингов: {count('embeddings')} | в FTS: {count('films_fts')}")
print(f"(эталон: чистая сборка из catalog_final_v2.json = {EXPECTED_FILMS} фильмов; "
      f"{'СОВПАДАЕТ' if films == EXPECTED_FILMS else 'НЕ СОВПАДАЕТ - база не чистая или импорт неполный'})")
emb, ch = count('embeddings'), count('chunks')
if isinstance(emb, int) and isinstance(ch, int) and emb != ch:
    print(f"(ВНИМАНИЕ: эмбеддингов {emb} при {ch} чанках - embed не завершён, запусти embed --resume)")

print("\n=== СЛОИ В БАЗЕ (source -> сколько фильмов) ===")
for src, c in conn.execute("SELECT source, COUNT(*) FROM films GROUP BY source ORDER BY 1"):
    print(f"  {src}: {c}")
print("(должна быть ровно одна строка - catalog_final_v2.json; если строк несколько -")
print(" база собрана поверх старой; это и есть причина дублей и обрезанных заглавий)")

print("\n=== ТОЧНЫЕ ДУБЛИ (полностью совпадают название+год) ===")
dups = conn.execute("""
    SELECT title, year, COUNT(*) c FROM films
    GROUP BY title, year HAVING c > 1 ORDER BY c DESC LIMIT 20
""").fetchall()
if dups:
    print(f"найдено {len(dups)} (показываю до 20):")
    for t, y, c in dups:
        tag = "  [законная пара: разные фильмы разных студий]" if (t, y) in LEGIT_DUPS and c == 2 else "  <-- ЛИШНИЙ ДУБЛЬ"
        print(f"  {c}x  {t}  ({y}){tag}")
else:
    print("точных дублей нет (ожидались 3 законные пары - проверь, не схлопнул ли их импорт).")

print("\n=== ДУБЛИ название+год+студия (ключ дедупликации импорта) ===")
dups3 = conn.execute("""
    SELECT title, year, studio, COUNT(*) c FROM films
    GROUP BY title, year, studio HAVING c > 1 ORDER BY c DESC LIMIT 20
""").fetchall()
if dups3:
    print("найдено (эталон - 0):")
    for t, y, s, c in dups3:
        print(f"  {c}x  {t}  ({y}) {s}")
else:
    print("нет (как в эталоне).")

print("\n=== ПУСТЫЕ ПОЛЯ (эталон: genre 12, studio 1, annotation 8, year 0) ===")
for col in ("genre", "studio", "annotation", "year"):
    n = conn.execute(f"SELECT COUNT(*) FROM films WHERE {col} IS NULL OR {col} = ''").fetchone()[0]
    print(f"  {col}: {n}")

print("\n=== ФИЛЬМОВ ПО ГОДАМ (видно дыры) ===")
yc = Counter()
for (y,) in conn.execute("SELECT year FROM films WHERE year IS NOT NULL"):
    yc[y] += 1
if yc:
    lo = max(min(yc), 1915)
    hi = min(max(yc), 1992)
    for y in range(lo, hi + 1):
        n = yc.get(y, 0)
        mark = "   <-- ПУСТО" if n == 0 else ""
        bar = "#" * (n // 10)
        print(f"  {y}: {n:4d} {bar}{mark}")
    weird = sorted(y for y in yc if y < 1915 or y > 1992)
    if weird:
        print(f"\nгоды вне 1915-1992 (вероятно битый год в исходнике): {weird}")
