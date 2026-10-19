#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Список работ по сюжетным аннотациям (этап 2 плана) и применение заполненного списка.

    python tools/annotation_worklist.py export --estimate                 # сколько стоит классификация
    python tools/annotation_worklist.py export --classify --out imports/аннотации_список_работ.xlsx
    python tools/annotation_worklist.py apply imports/аннотации_список_работ.xlsx --out imports/аннотации_правки.json
    python film_search.py import imports/аннотации_правки.json --dry-run
    python film_search.py import imports/аннотации_правки.json
    python film_search.py embed --resume

export — xlsx по фильмам film_id ≥ 7175 (аннотации каталогов ГФФ 1–7174 закрыты). Порядок:
  1) аннотация обрывается на «…» / «...»;
  2) «не сюжет» — текст не говорит, что происходит в фильме (только о литературной основе,
     судьбе фильма, актёрах, жанре). Определяет дешёвая модель (FLAG_MODEL), ответы кешируются
     в imports/аннотации_классы.json по хешу аннотации — повторный запуск платит только за новые;
  3) остальные — от коротких к длинным.
  Колонки «Новая аннотация» и «Источник новой аннотации» заполняются вручную.

apply — заполненный xlsx → JSON-правки [{"film_id", "annotation", "source"}] для film_search.py import.
  Ошибка в любой строке (film_id < 7175 или нет в базе, название не совпадает с базой — строки
  сдвинуты, нет источника, обрыв на многоточие, film_id дважды) — JSON не пишется.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import urllib.parse
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from film_search import DB_PATH, get_openai_client  # noqa: E402

FIRST_OPEN_ID = 7175        # film_id 1–7174 — каталоги ГФФ, аннотации не трогаем (PLAN.md, раздел 2)
SHORT_CHARS = 300
CLASSES_PATH = ROOT / "imports" / "аннотации_классы.json"

# Проба на 50 + 8 трудных аннотациях 19.10.2026: gpt-5.4-nano и с "none", и с "low" считал сюжетом
# «Семнадцать мгновений весны» (8327: только время действия и слава фильма), gpt-5.4-mini — нет
FLAG_MODEL = "gpt-5.4-mini"
FLAG_EFFORT = "low"
FLAG_BATCH = 25             # аннотаций в одном запросе
FLAG_CLIP = 1500            # для решения «сюжет / не сюжет» хватает начала текста
# Оценка стоимости: цены gpt-5.4-mini $0,75 / $4,50 за 1 млн входных / выходных токенов — по сводкам
# цен на 19.10.2026, на странице OpenAI не проверены. ~2 символа на токен — по эмбеддингам этих
# же аннотаций (2,28 млн символов чанков = 1,16 млн токенов); выходных ~30 на аннотацию — на пробе
# (ответ + рассуждение при "low").
PRICE_IN, PRICE_OUT = 0.75, 4.50
CHARS_PER_TOKEN = 2.0
PROMPT_TOKENS, ANSWER_TOKENS = 450, 30      # на запрос / на одну аннотацию в ответе

FLAG_PROMPT = """Ниже аннотации советских фильмов, телефильмов и телеспектаклей. Для каждой определи, \
рассказывает ли она СЮЖЕТ: из текста понятно, кто герои и что с ними происходит — есть хотя бы одно \
событие или действие героев. Для концерта, документального или научно-популярного фильма вместо сюжета \
годится конкретное содержание: кто участвует и что именно показано.

"plot": false — если в тексте нет ни одного события, а есть только: литературная основа («По одноимённой \
пьесе …»), жанр («военная драма», «водевиль»), общая тема («о любви к природе», «о быте чабанов»), время \
и место действия, судьба и слава фильма, история съёмок, актёры, театр-постановщик, оценки.
"plot": true — если есть хоть одно событие с героями, даже в одной фразе («у влюблённых сваты всё \
перепутали»).

Верни СТРОГО JSON-массив без пояснений: [{{"id": <номер>, "plot": true|false}}, ...] — по одному элементу \
на каждую аннотацию.

{items}"""

HEADERS = ["Приоритет", "Группа", "film_id", "Название", "Год", "Тип", "Студия", "Длина", "Обрыв",
           "Не сюжет", "Текущая аннотация", "Текущий источник", "Поиск в Википедии",
           "Новая аннотация", "Источник новой аннотации"]
WIDTHS = [9, 12, 8, 36, 6, 15, 24, 7, 7, 9, 70, 30, 14, 70, 40]


def ann_hash(text):
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


def is_truncated(text):
    return bool(re.search(r"(…|\.\.\.)\s*$", text or ""))


def load_films(db):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute("""SELECT film_id, title, year, kind, studio, annotation, source FROM films
                               WHERE film_id >= ? ORDER BY film_id""", (FIRST_OPEN_ID,)).fetchall()
    finally:
        conn.close()
    keys = ("film_id", "title", "year", "kind", "studio", "annotation", "source")
    return [dict(zip(keys, r)) for r in rows]


def load_classes():
    if CLASSES_PATH.exists():
        return {int(k): v for k, v in json.loads(CLASSES_PATH.read_text(encoding="utf-8")).items()}
    return {}


def save_classes(classes):
    CLASSES_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {str(k): classes[k] for k in sorted(classes)}
    CLASSES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")


def cached_plot(classes, film):
    """True / False из кеша, None — если фильм не классифицирован или аннотация с тех пор изменилась."""
    c = classes.get(film["film_id"])
    return c["plot"] if c and c.get("hash") == ann_hash(film["annotation"]) else None


def estimate(films):
    chars = sum(min(len(f["annotation"] or ""), FLAG_CLIP) for f in films)
    batches = -(-len(films) // FLAG_BATCH)
    t_in = chars / CHARS_PER_TOKEN + batches * PROMPT_TOKENS
    t_out = len(films) * ANSWER_TOKENS
    return t_in, t_out, (t_in * PRICE_IN + t_out * PRICE_OUT) / 1e6


def classify(films, classes):
    """Классифицировать аннотации моделью FLAG_MODEL; кеш сохраняется после каждого запроса."""
    client = get_openai_client()
    used_in = used_out = 0
    for start in range(0, len(films), FLAG_BATCH):
        batch = films[start:start + FLAG_BATCH]
        items = "\n\n".join(f"[{f['film_id']}] «{f['title']}» ({f['year']}): "
                            f"{(f['annotation'] or '')[:FLAG_CLIP]}" for f in batch)
        answer = None
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=FLAG_MODEL,
                    messages=[{"role": "user", "content": FLAG_PROMPT.format(items=items)}],
                    reasoning_effort=FLAG_EFFORT,
                    max_completion_tokens=8000,
                )
                used_in += resp.usage.prompt_tokens
                used_out += resp.usage.completion_tokens
                text = resp.choices[0].message.content.strip().replace("```json", "").replace("```", "")
                answer = {int(it["id"]): bool(it["plot"]) for it in json.loads(text)}
                break
            except Exception as e:      # сбой сети или формата ответа — повтор
                print(f"  запрос {start // FLAG_BATCH + 1}: {e}", file=sys.stderr)
        if answer is None:
            print(f"  film_id {batch[0]['film_id']}–{batch[-1]['film_id']} не классифицированы", file=sys.stderr)
            continue
        for f in batch:
            if f["film_id"] in answer:
                classes[f["film_id"]] = {"plot": answer[f["film_id"]], "hash": ann_hash(f["annotation"]),
                                         "model": FLAG_MODEL}
        save_classes(classes)
        done = min(start + FLAG_BATCH, len(films))
        if done % 500 < FLAG_BATCH or done == len(films):
            print(f"  классифицировано {done}/{len(films)}")
    cost = (used_in * PRICE_IN + used_out * PRICE_OUT) / 1e6
    print(f"Токенов: {used_in:,} входных, {used_out:,} выходных; ≈ ${cost:.3f}")


def cmd_export(args):
    films = load_films(args.db)
    classes = load_classes()
    todo = [f for f in films if f["annotation"] and cached_plot(classes, f) is None]
    t_in, t_out, cost = estimate(todo)
    print(f"Фильмов film_id ≥ {FIRST_OPEN_ID}: {len(films)}; без классификации «сюжет / не сюжет»: {len(todo)}")
    if todo:
        print(f"  классификация {FLAG_MODEL}: ≈ {t_in:,.0f} входных и {t_out:,.0f} выходных токенов, ≈ ${cost:.2f}")
    if args.estimate:
        return
    if args.classify and todo:
        classify(todo, classes)

    rows = []
    for f in films:
        ann = f["annotation"] or ""
        plot = cached_plot(classes, f)
        trunc = is_truncated(ann)
        group = ("обрыв" if trunc else "не сюжет" if plot is False
                 else "короткая" if len(ann) < SHORT_CHARS else "")
        rank = (0 if trunc else 1 if plot is False else 2, len(ann), f["film_id"])
        rows.append((rank, group, f, ann, trunc, plot))
    rows.sort(key=lambda r: r[0])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Аннотации"
    ws.append(HEADERS)
    for n, (_, group, f, ann, trunc, plot) in enumerate(rows, start=1):
        query = urllib.parse.quote(f"{f['title']} {f['year'] or ''} фильм".strip())
        ws.append([n, group, f["film_id"], f["title"], f["year"], f["kind"], f["studio"], len(ann),
                   "да" if trunc else "", "да" if plot is False else "" if plot else "?",
                   ann, f["source"], f'=HYPERLINK("https://ru.wikipedia.org/w/index.php?search={query}","искать")',
                   None, None])
    wrap = Alignment(wrap_text=True, vertical="top")
    top = Alignment(vertical="top")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap if cell.column in (4, 11, 14) else top
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for i, w in enumerate(WIDTHS, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = ws.dimensions

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    groups = {}
    for r in rows:
        groups[r[1] or "остальные"] = groups.get(r[1] or "остальные", 0) + 1
    unknown = sum(1 for r in rows if r[5] is None)
    print("Группы: " + ", ".join(f"{k} {v}" for k, v in groups.items())
          + (f"; не классифицировано: {unknown}" if unknown else ""))
    print(f"Список работ: {out}")


def clean_annotation(text):
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def cmd_apply(args):
    db = {f["film_id"]: f for f in load_films(args.db)}
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    max_id = conn.execute("SELECT MAX(film_id) FROM films").fetchone()[0]
    conn.close()

    edits, errors, warnings, seen = [], [], [], {}
    unchanged = 0
    for path in args.xlsx:
        ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
        rows = ws.iter_rows(values_only=True)
        header = [str(h or "").strip().lower() for h in next(rows)]

        def col(prefix):
            return next((i for i, h in enumerate(header) if h.startswith(prefix)), None)
        c_id, c_title = col("film_id"), col("название")
        c_new, c_src = col("новая аннотация"), col("источник новой")
        if None in (c_id, c_new, c_src):
            sys.exit(f"{path}: нужны колонки film_id, «Новая аннотация», «Источник новой аннотации»")
        for n, r in enumerate(rows, start=2):
            new = clean_annotation(r[c_new] if c_new < len(r) else None)
            src = str((r[c_src] if c_src < len(r) else None) or "").strip()
            if not new and not src:
                continue
            where = f"{Path(path).name}, строка {n}"
            try:
                fid = int(r[c_id])
            except (TypeError, ValueError):
                errors.append(f"{where}: film_id «{r[c_id]}» — не число")
                continue
            if fid < FIRST_OPEN_ID:
                errors.append(f"{where}: film_id {fid} — каталог ГФФ, аннотации 1–{FIRST_OPEN_ID - 1} не меняются")
                continue
            film = db.get(fid)
            if film is None:
                errors.append(f"{where}: film_id {fid} нет в базе (последний — {max_id})")
                continue
            title = str(r[c_title] or "").strip() if c_title is not None else None
            if title is not None and title != (film["title"] or "").strip():
                errors.append(f"{where}: film_id {fid} в базе — «{film['title']}», в строке — «{title}» "
                              "(строки сдвинуты?)")
                continue
            if fid in seen:
                errors.append(f"{where}: film_id {fid} уже был в {seen[fid]}")
                continue
            seen[fid] = where
            if not new:
                errors.append(f"{where}: film_id {fid} — источник есть, а новой аннотации нет")
                continue
            if not src:
                errors.append(f"{where}: film_id {fid} — не указан источник новой аннотации")
                continue
            if is_truncated(new):
                errors.append(f"{where}: film_id {fid} — новая аннотация обрывается на многоточие")
                continue
            old = film["annotation"] or ""
            if new == old.strip():
                unchanged += 1
                continue
            if len(new) < len(old):
                warnings.append(f"{where}: film_id {fid} «{film['title']}» — новая аннотация короче старой "
                                f"({len(new)} против {len(old)} символов)")
            edits.append({"film_id": fid, "annotation": new, "source": src})

    for w in warnings:
        print("Внимание: " + w)
    for e in errors:
        print("Ошибка: " + e)
    print(f"Правок: {len(edits)}; совпадают с базой: {unchanged}; ошибок: {len(errors)}")
    if errors and not args.skip_errors:
        sys.exit("JSON не записан: исправьте ошибки или запустите с --skip-errors")
    if not edits:
        return
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(edits, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"JSON: {out}\nДальше: python film_search.py import {out} --dry-run")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=str(ROOT / DB_PATH))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export", help="выгрузить список работ xlsx")
    p.add_argument("--out", default=str(ROOT / "imports" / "аннотации_список_работ.xlsx"))
    p.add_argument("--classify", action="store_true",
                   help=f"классифицировать «сюжет / не сюжет» моделью {FLAG_MODEL} (платно, см. --estimate)")
    p.add_argument("--estimate", action="store_true", help="только оценить стоимость классификации")
    p = sub.add_parser("apply", help="заполненный xlsx → JSON-правки для film_search.py import")
    p.add_argument("xlsx", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--skip-errors", action="store_true", help="записать правки без строк с ошибками")
    args = ap.parse_args()
    {"export": cmd_export, "apply": cmd_apply}[args.cmd](args)


if __name__ == "__main__":
    main()
