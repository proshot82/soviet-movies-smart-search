#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сведение мультфильмов 1917–1991: база animator.ru + список владельца (xlsx) → xlsx для tools/xlsx_to_json.py.

    python tools/cartoons_merge.py imports/2026-10_мультфильмы_список_владельца.xlsx
    python tools/xlsx_to_json.py imports/2026-10_мультфильмы.xlsx --out imports/2026-10_мультфильмы.json

Основа — animator.ru (tools/animator_catalog.py): советские студии, совместные постановки (например, «Лоло»:
Союзмультфильм + японские студии). Реклама не берётся. Строки списка владельца сопоставляются с animator.ru по
названию (номер выпуска / части / фильма учитывается отдельно) и году ±1.

Из двух аннотаций берётся более полная: у списка владельца отрезается хвост «©Студия, 1983 г.Режиссёр:…»,
у animator.ru пустой считается «фильм из серии «…»». Название — из списка владельца (в нём строчные буквы),
иначе из animator.ru (там ПРОПИСНЫЕ — переводятся в обычный регистр). Источник — карточка animator.ru;
если аннотация из списка владельца, впереди имя файла.

Сопоставление по очереди: название целиком с номером; без номера; подзаголовок после последней точки
(«Простоквашино. 1. Трое из Простоквашино» → «Трое из Простоквашино»; у animator.ru так же: «КОТ ЛЕОПОЛЬД.
ТЕЛЕВИЗОР КОТА ЛЕОПОЛЬДА»); нечётко — похожее на 90 % название того же года ±1. Берётся единственный кандидат (при
нескольких — единственный с тем же годом). Строки владельца, которых нет на animator.ru, НЕ берутся: в списке
есть зарубежные мультфильмы без страны («Болек и Лёлек», «Крот»), а сверка — по animator.ru. Решение по каждой
строке владельца — в …_сведение.xlsx.
"""
import argparse
import difflib
import gzip
import json
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from xlsx_to_json import norm  # noqa: E402

YEAR_MAX = 1991
FOREIGN = re.compile(r"^(сша|япония|чехословакия|франция|польша|венгрия|испания|канада|великобритания|англия|"
                     r"болгария|гдр|фрг|германия|швеция|нидерланды|австралия|италия|югославия|китай|дания|"
                     r"финляндия|румыния|бельгия|швейцария|австрия|норвегия|корея|индия|куба)\b", re.I)
NUM_WORDS = {"фильм", "ч", "часть", "выпуск", "серия", "n", "no", "номер", "вып"}


def title_key(title):
    """(слова без номеров, номера) — «Бюро находок. ч.1» и «БЮРО НАХОДОК (Фильм 1)» совпадают."""
    words = norm(title).split()
    nums = tuple(w for w in words if w.isdigit())
    base = " ".join(w for w in words if not w.isdigit() and w not in NUM_WORDS)
    return base, nums


def sentence_case(title):
    if title != title.upper():
        return title
    t = title.lower()
    return re.sub(r"(^|[.!?«\"(]\s*)(\w)", lambda m: m.group(1) + m.group(2).upper(), t)


def split_owner_annotation(text):
    """«Текст©Студия, 1983 г.Режиссёр:Имя» → (текст, студия, год, режиссёр)."""
    text = str(text or "").strip()
    m = re.search(r"©\s*(.*?),\s*(\d{4})\s*г\.?\s*(?:Режисс[её]р\s*:\s*(.*))?$", text, re.S)
    if not m:
        return text, None, None, None
    return text[:m.start()].strip(), m.group(1).strip(), int(m.group(2)), (m.group(3) or "").strip() or None


def animator_annotation(rec):
    a = (rec.get("annotation") or "").strip()
    return "" if re.match(r"(?i)фильм из серии", a) else a


def drop_known(rows, report, db, no_brackets, last_part):
    """Убрать мультфильмы, которые уже есть в базе под тем же названием (варианты — как при сведении) и годом ±1.
    Мультфильм базы считается тем же; фильм другого типа — только если сверка моделью скажет «тот же фильм»."""
    import sqlite3
    from annotation_worklist import verify_matches
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    keys = lambda t: {k for k in (title_key(t)[0], title_key(no_brackets(t))[0], last_part(t)) if k}
    index = {}
    films = {}
    for fid, t, y, kind, ann, studio in conn.execute("SELECT film_id, title, year, kind, annotation, studio FROM films"):
        films[fid] = {"film_id": fid, "title": t, "year": y, "kind": kind, "annotation": ann, "studio": studio}
        for k in keys(t or ""):
            index.setdefault(k, []).append(fid)
    conn.close()
    hits = {}
    for i, r in enumerate(rows):
        cands = {fid for k in keys(r[0]) for fid in index.get(k, [])
                 if films[fid]["year"] and abs(films[fid]["year"] - r[1]) <= 1}
        if cands:
            hits[i] = cands
    # пары с фильмами не-мультфильмами — на сверку; ключ сверки — film_id базы
    to_check = {}
    for i, cands in hits.items():
        if not any(films[f]["kind"] == "мультфильм" for f in cands):
            for f in cands:
                to_check.setdefault(f, (rows[i][4] or rows[i][0], rows[i][8], f"мультфильм «{rows[i][0]}» {rows[i][1]}"))
    verdict = verify_matches(films, to_check) if to_check else {}
    kept, dropped = [], 0
    for i, r in enumerate(rows):
        cands = hits.get(i, set())
        same = [f for f in cands if films[f]["kind"] == "мультфильм" or verdict.get(f) == "yes"]
        if same:
            dropped += 1
            report.append(["—", r[0], r[1], "уже в базе", "film_id " + ", ".join(map(str, sorted(same)))])
        else:
            kept.append(r)
    print(f"  уже в базе (название и год ±1; не-мультфильмы — по сверке моделью): {dropped}")
    return kept


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("owner_xlsx")
    ap.add_argument("--animator", default=str(ROOT / "imports" / "animator_catalog.jsonl.gz"))
    ap.add_argument("--out", default=str(ROOT / "imports" / "2026-10_мультфильмы.xlsx"))
    ap.add_argument("--db", default=str(ROOT / "gosfilmofond.db"))
    args = ap.parse_args()
    owner_name = Path(args.owner_xlsx).name

    anim = [json.loads(line) for line in gzip.open(args.animator, "rt", encoding="utf-8")]
    anim = [a for a in anim if a.get("film_type") != "реклама" and a.get("year") and a["year"] <= YEAR_MAX]
    def no_brackets(title):
        return re.sub(r"\s*\([^)]*\)", "", title)

    def last_part(title):
        """Подзаголовок после последней точки без скобок: «КОТ ЛЕОПОЛЬД. ТЕЛЕВИЗОР КОТА ЛЕОПОЛЬДА» → «телевизор…»."""
        parts = [p for p in re.split(r"\.\s+", re.sub(r"\s*\([^)]*\)", "", title)) if p.strip()]
        return title_key(parts[-1])[0] if len(parts) > 1 else None

    by_full, by_base, by_year = {}, {}, {}
    for a in anim:
        by_full.setdefault(title_key(a["title"]), []).append(a)
        by_base.setdefault(title_key(a["title"])[0], []).append(a)
        by_base.setdefault(title_key(no_brackets(a["title"]))[0], []).append(a)
        if last_part(a["title"]):
            by_base.setdefault(last_part(a["title"]), []).append(a)
        by_year.setdefault(a["year"], []).append(a)

    def fuzzy(title, year):
        """Нечёткое совпадение названия (окончания: «Масленкино» / «Масленкина») среди мультфильмов того же года."""
        base = title_key(title)[0]
        return [a for y in (year - 1, year, year + 1) for a in by_year.get(y, [])
                if difflib.SequenceMatcher(None, base, title_key(a["title"])[0]).ratio() >= 0.9]

    def find(title, year):
        lookups = [by_full.get(title_key(title), []), by_base.get(title_key(title)[0], []),
                   by_base.get(title_key(no_brackets(title))[0], [])]
        if last_part(title):
            lookups.append(by_base.get(last_part(title), []))
        lookups.append(fuzzy(title, year))
        for found in lookups:
            found = list({a["fid"]: a for a in found}.values())
            cands = [a for a in found if abs(a["year"] - year) <= 1]
            exact = [a for a in cands if a["year"] == year]
            pick = exact if len(exact) == 1 else cands if len(cands) == 1 else []
            if pick:
                return pick[0], len(cands)
        return None, 0

    report = []
    matched = {}                                     # fid → строка владельца
    ws = openpyxl.load_workbook(args.owner_xlsx, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip().lower() for h in next(rows)]
    col = {name: header.index(name) for name in ("название", "год", "аннотация", "страна")}
    for n, r in enumerate(rows, start=2):
        title = str(r[col["название"]] or "").strip()
        if not title:
            continue
        text, studio, c_year, director = split_owner_annotation(r[col["аннотация"]])
        y = re.match(r"\d{4}", str(r[col["год"]] or ""))
        year = int(y.group()) if y else c_year
        if c_year and c_year != year:
            year = c_year       # год из «©…» точнее колонки «Год» в обе стороны: «Пряник» 1988 по колонке, 1993 по «©»
        country = str(r[col["страна"]] or "").strip()
        why = None
        if not year:
            why = "нет года"
        elif year > YEAR_MAX:
            why = f"после {YEAR_MAX}"
        elif country:
            why = f"страна: {country}"
        elif studio and FOREIGN.match(studio):
            why = f"студия: {studio}"
        if why:
            report.append([n, title, year, "не берётся", why])
            continue
        found, _ = find(title, year)
        rec = {"row": n, "title": title, "year": year, "text": text, "studio": studio, "director": director}
        if found and found["fid"] not in matched:
            matched[found["fid"]] = rec
            report.append([n, title, year, "animator.ru", found["url"]])
        elif found:
            report.append([n, title, year, "не берётся", f"та же карточка, что строка {matched[found['fid']]['row']}"])
        else:
            report.append([n, title, year, "не берётся", "нет на animator.ru" + ("" if text else " (аннотации нет)")])

    out_rows = []
    for a in anim:
        own = matched.get(a["fid"])
        a_text, o_text = animator_annotation(a), (own or {}).get("text") or ""
        use_owner = len(o_text) > len(a_text)
        technique = (a.get("technique") or "").split(",")[0].strip()
        if re.match(r"\d", technique):          # «10 мин.» — техники нет, только длительность
            technique = ""
        genre = "мультфильм" + (f", {technique}" if technique else "")
        if a.get("film_type", "").startswith("сюжет из киножурнала"):
            genre += ", сюжет киножурнала «Фитиль»"
        studios = ", ".join(a.get("studios") or []) or (own or {}).get("studio")
        people = a.get("people", {})
        directors = ", ".join(dict.fromkeys(p for role in ("режиссер", "режиссеры", "режиссер-постановщик",
                                                          "режиссеры-постановщики") for p in people.get(role, []))) \
            or (own or {}).get("director")
        out_rows.append([own["title"] if own else sentence_case(a["title"]), a["year"], genre, studios,
                         o_text if use_owner else a_text, "мультфильм", "СССР", directors,
                         f"{owner_name}; {a['url']}" if use_owner else a["url"],
                         "animator.ru + список владельца" if own else "animator.ru"])
    out_rows = drop_known(out_rows, report, args.db, no_brackets, last_part)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Мультфильмы"
    ws.append(["Название", "Год", "Жанр", "Студия", "Аннотация", "Тип (уточнённый)", "Страна", "Режиссёр",
               "Источник", "Происхождение"])
    for r in out_rows:
        ws.append(r)
    out = Path(args.out)
    wb.save(out)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Строка", "Название", "Год", "Решение", "Примечание"])
    for r in report:
        ws.append(r)
    rep = out.with_name(out.stem + "_сведение.xlsx")
    wb.save(rep)

    from collections import Counter
    print(f"animator.ru: {len(anim)} мультфильмов ≤ {YEAR_MAX} (без рекламы); список владельца: {len(report)} строк")
    print("  решения по строкам владельца: " + ", ".join(f"{k} {v}" for k, v in Counter(r[3] for r in report).items()))
    print(f"  аннотация из списка владельца длиннее: {sum(1 for r in out_rows if str(r[8]).startswith(owner_name))}")
    print(f"Итого строк: {len(out_rows)} → {out}\nОтчёт: {rep}")


if __name__ == "__main__":
    main()
