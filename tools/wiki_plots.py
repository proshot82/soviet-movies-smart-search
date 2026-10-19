#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Раздел «Сюжет» из русской Википедии для фильмов базы (film_id ≥ 7175).

    python tools/wiki_plots.py                          # → imports/wiki_plots.jsonl.gz, с докачкой
    python tools/wiki_plots.py --ids 8327 8463          # только эти фильмы

Шаг 1 — поиск статьи: для каждого фильма проверяются названия «Х (фильм, Г)», «Х (телефильм)», «Х (телесериал)»,
«Х (телеспектакль)», «Х (мультфильм)», «Х (фильм)», «Х» — набор зависит от типа фильма (SUFFIXES); по 10 фильмов
(≤ 50 названий) в запросе к API (prop=categories). Статья
подходит, если среди её категорий есть категория с годом фильма (±1) и словом «СССР» / «советск» —
так «Х» о книге или городе не принимается. Шаг 2 — викитекст выбранных статей (пачками по 50),
из него раздел «Сюжет» без разметки, сносок и шаблонов.

Посерийные подзаголовки раздела («=== 1-я серия ===») отмечаются в поле episodes: для сериала со сквозным
сюжетом такой текст не подходит (нужен общий сюжет), для сериала из отдельных историй — подходит.

Лицензия текстов — CC BY-SA 4.0: в url — постоянная ссылка на версию статьи (oldid), это и указание авторства.
API: User-Agent с контактом, запросы по одному, при 429 — пауза по Retry-After (правила Wikimedia).
"""
import argparse
import gzip
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from film_search import DB_PATH  # noqa: E402

API = "https://ru.wikipedia.org/w/api.php"
UA = "SovietMoviesSearch/0.1 (https://github.com/proshot82/soviet-movies-smart-search) python-urllib"
FIRST_OPEN_ID = 7175
BATCH = 50
# Варианты названия статьи по типу фильма (меньше вариантов — больше фильмов в одном запросе к API)
SUFFIXES = {
    "телефильм": ["фильм, {year}", "телефильм", "телесериал", "фильм", None],
    "фильм-спектакль": ["телеспектакль", "фильм-спектакль", "фильм, {year}", "фильм", None],
    "мультфильм": ["мультфильм, {year}", "мультфильм", "фильм", None],
}
SUFFIXES_DEFAULT = ["фильм, {year}", "фильм", "телефильм", None]
PLOT_HEADINGS = re.compile(r"^(сюжет|сюжет фильма|содержание|синопсис)$", re.I)


def api(params, tries=30):
    data = urllib.parse.urlencode(dict(params, format="json", formatversion=2)).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
            # Retry-After бывает 1 с при длящемся 429 (общий облачный адрес) — ждём не меньше растущей паузы
            wait = max(int(e.headers.get("Retry-After") or 0) + 1, 5 * 2 ** min(attempt, 6))
        except (urllib.error.URLError, TimeoutError):
            wait = 5 * 2 ** attempt
        time.sleep(min(wait, 300))
    raise SystemExit("API Википедии не отвечает — перезапустите позже, докачка продолжится")


def candidates(title, year, kind=None):
    base = re.sub(r"\s+", " ", title).strip()
    out = []
    for s in SUFFIXES.get(kind, SUFFIXES_DEFAULT):
        t = base if s is None else f"{base} ({s.format(year=year)})"
        if t not in out:
            out.append(t)
    return out


def fits(categories, year):
    years = {str(year + d) for d in (-1, 0, 1)} if year else set()
    for c in categories:
        c = c.lower()
        if ("ссср" in c or "советск" in c) and any(y in c for y in years):
            return True
    return False


def strip_templates(text):
    out, depth, i = [], 0, 0
    while i < len(text):
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i) and depth:
            depth -= 1
            i += 2
        else:
            if not depth:
                out.append(text[i])
            i += 1
    return "".join(out)


def strip_files(text):
    """[[Файл:…|…[[ссылка]]…]] целиком — с учётом вложенных [[ ]] в подписи."""
    out, i = [], 0
    pat = re.compile(r"\[\[(?:файл|file|изображение|image|категория|category):", re.I)
    while True:
        m = pat.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:m.start()])
        depth, j = 0, m.start()
        while j < len(text):
            if text.startswith("[[", j):
                depth += 1
                j += 2
            elif text.startswith("]]", j):
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        i = j


def wikitext_to_plain(text):
    text = re.sub(r"(?s)<!--.*?-->", "", text)
    text = re.sub(r"(?is)<ref[^>/]*/>|<ref[^>]*>.*?</ref>", "", text)
    text = strip_templates(text)
    text = strip_files(text)
    text = re.sub(r"(?is)<gallery.*?</gallery>", "", text)
    text = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^=+\s*(.*?)\s*=+\s*$", lambda m: m.group(1).rstrip(".:") + ".", text, flags=re.M)
    text = re.sub(r"^[*#:;]+\s*", "", text, flags=re.M)
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.;:!?])", r"\1", text)
    return re.sub(r"\n\s*\n*", "\n", text).strip()


def plot_section(wikitext):
    """(текст раздела «Сюжет», есть ли подзаголовки внутри раздела) или (None, False)."""
    lines = wikitext.split("\n")
    start = None
    for i, line in enumerate(lines):
        m = re.match(r"^==\s*([^=].*?)\s*==\s*$", line)
        if m and start is None and PLOT_HEADINGS.match(m.group(1).strip()):
            start = i + 1
        elif m and start is not None:
            body = "\n".join(lines[start:i])
            return wikitext_to_plain(body), bool(re.search(r"^===", body, re.M))
    if start is not None:
        body = "\n".join(lines[start:])
        return wikitext_to_plain(body), bool(re.search(r"^===", body, re.M))
    return None, False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=str(ROOT / DB_PATH))
    ap.add_argument("--out", default=str(ROOT / "imports" / "wiki_plots.jsonl.gz"))
    ap.add_argument("--ids", nargs="*", type=int)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    films = conn.execute("SELECT film_id, title, year, kind FROM films WHERE film_id >= ? ORDER BY film_id",
                         (FIRST_OPEN_ID,)).fetchall()
    conn.close()
    if args.ids:
        films = [f for f in films if f[0] in set(args.ids)]
    out = Path(args.out)
    done = set()
    if out.exists():
        with gzip.open(out, "rt", encoding="utf-8") as f:
            done = {json.loads(line)["film_id"] for line in f if line.strip()}
    films = [f for f in films if f[0] not in done]
    print(f"Фильмов: {len(films)} (уже обработано: {len(done)})")

    # Шаг 1: какие названия существуют и подходят по категориям. Пачки — по фильмам, чтобы докачка шла по фильмам.
    per_batch = 10
    for start in range(0, len(films), per_batch):
        chunk = [(fid, t, y) for fid, t, y, _ in films[start:start + per_batch]]
        want = {fid: candidates(t, y, k) for fid, t, y, k in films[start:start + per_batch]}
        titles = sorted({t for c in want.values() for t in c})
        d = api({"action": "query", "titles": "|".join(titles), "redirects": 1, "prop": "categories",
                 "cllimit": "max", "clshow": "!hidden"})
        q = d.get("query", {})
        norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
        redir = {x["from"]: x["to"] for x in q.get("redirects", [])}
        pages = {p["title"]: p for p in q.get("pages", []) if not p.get("missing") and not p.get("invalid")}
        chosen = {}
        for fid, t, y in chunk:
            for cand in want[fid]:
                name = redir.get(norm.get(cand, cand), norm.get(cand, cand))
                p = pages.get(name)
                if p and fits([c["title"] for c in p.get("categories", [])], y):
                    chosen[fid] = p["title"]
                    break
        # Шаг 2: викитекст выбранных статей
        texts = {}
        if chosen:
            d = api({"action": "query", "titles": "|".join(sorted(set(chosen.values()))), "prop": "revisions",
                     "rvprop": "ids|content", "rvslots": "main"})
            for p in d.get("query", {}).get("pages", []):
                if p.get("revisions"):
                    rev = p["revisions"][0]
                    texts[p["title"]] = (rev["revid"], rev["slots"]["main"]["content"])
        with gzip.open(out, "at", encoding="utf-8") as f:
            for fid, t, y in chunk:
                rec = {"film_id": fid, "title": t, "year": y}
                page = chosen.get(fid)
                if page and page in texts:
                    revid, wt = texts[page]
                    plot, episodes = plot_section(wt)
                    rec.update(page=page, revid=revid, plot=plot, episodes=episodes,
                               url=f"https://ru.wikipedia.org/w/index.php?"
                                   + urllib.parse.urlencode({"title": page.replace(" ", "_"), "oldid": revid}))
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n = start + len(chunk)
        if n % 300 < per_batch or n == len(films):
            print(f"  {n}/{len(films)}")
        time.sleep(3)
    print(f"Файл: {out}")


if __name__ == "__main__":
    main()
