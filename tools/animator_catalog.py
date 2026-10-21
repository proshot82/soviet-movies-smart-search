#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выгрузка мультфильмов 1917–1991 из базы animator.ru: название, год, студии, техника, длительность,
аннотация, режиссёры, сценаристы, роли озвучивали, URL карточки.

    python tools/animator_catalog.py                     # → imports/animator_catalog.jsonl.gz, с докачкой
    python tools/animator_catalog.py --years 1984 1984   # проба на одном годе

Условия сайта: «© Аниматор.ру, при перепечатке материалов ссылка обязательна» — ссылка на карточку
(/db/?p=show_film&fid=…) пишется в поле url и потом в films.source. robots.txt раздел /db/ не закрывает.
Запросы строго по одному, с паузой --pause секунд. Шаг 1 — списки по годам (/db/?p=films&year=Г, по 50
на странице), шаг 2 — карточки фильмов. Готовые карточки дописываются в файл сразу: повторный запуск
продолжит с первой недокачанной.
"""
import argparse
import gzip
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://animator.ru/db/"
UA = "SovietMoviesSearch/0.1 (+https://github.com/proshot82/soviet-movies-smart-search)"


def fetch(query, pause, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(BASE + "?" + query, headers={"User-Agent": UA})
            body = urllib.request.urlopen(req, timeout=60).read().decode("cp1251", errors="replace")
            time.sleep(pause)
            return body
        except (urllib.error.URLError, TimeoutError) as e:
            wait = 10 * 2 ** attempt
            print(f"  {query}: {e}; повтор через {wait} с", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"{query} не скачалось за {tries} попыток — перезапустите позже, докачка продолжится")


def text_of(fragment):
    t = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t).strip()


def list_year(year, pause):
    """[(fid, название, год)] из списка за год; страницы — cPage=1,2,… (ссылки NB1, NB2, … на первой)."""
    first = fetch(f"p=films&year={year}", pause)
    pages = [first] + [fetch(f"p=films&year={year}&cPage={n}", pause)
                       for n in sorted({int(x) for x in re.findall(r'id="NB(\d+)"', first)})]
    out = {}
    for page in pages:
        for fid, title in re.findall(r'onclick="showFilm\((\d+)\)">\s*(«.*?)</span>', page, re.S):
            out[int(fid)] = text_of(title)
    return out


def parse_film(fid, page):
    def cls(name):
        m = re.search(rf'class="{name}">(.*?)</td>', page, re.S)
        return text_of(m.group(1)) if m else None
    title = cls("FilmName")
    if not title:
        return None
    rec = {"fid": fid, "url": f"{BASE}?p=show_film&fid={fid}", "title": title.strip("«» "),
           "film_type": (cls("FilmType") or "").strip("() ") or None}
    types = re.findall(r'class="FilmType">(.*?)</td>', page, re.S)
    for t in types[1:]:
        if "showStudia" in t or "year=" in t:
            rec["studios"] = [text_of(s) for s in re.findall(r'onclick="showStudia\(\d+\)">(.*?)</span>', t, re.S)]
            y = re.search(r"(\d{4}) г\.", t)
            rec["year"] = int(y.group(1)) if y else None
        else:
            rec["technique"] = text_of(t)
    rec["annotation"] = cls("FilmComments")
    people = {}
    for prof, plist in re.findall(r'class="PProf">(.*?)</td>\s*<td class="PersonsList">(.*?)</td>', page, re.S):
        people[text_of(prof)] = [text_of(p) for p in re.findall(r'<span[^>]*>(.*?)</span>', plist, re.S)]
    rec["people"] = people
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "imports" / "animator_catalog.jsonl.gz"))
    ap.add_argument("--years", nargs=2, type=int, default=(1917, 1991), metavar=("С", "ПО"))
    ap.add_argument("--pause", type=float, default=2.0, help="пауза между запросами, с")
    args = ap.parse_args()

    out = Path(args.out)
    index_path = out.with_name(out.name.replace(".jsonl.gz", "_index.json"))
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    for year in range(args.years[0], args.years[1] + 1):
        if str(year) not in index:
            index[str(year)] = list_year(year, args.pause)
            index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            print(f"  {year}: {len(index[str(year)])} фильмов в списке")
    fids = sorted({int(f) for y in range(args.years[0], args.years[1] + 1) for f in index[str(y)]})

    done = set()
    if out.exists():
        with gzip.open(out, "rt", encoding="utf-8") as f:
            done = {json.loads(line)["fid"] for line in f if line.strip()}
    todo = [f for f in fids if f not in done]
    print(f"Фильмов в списках: {len(fids)}; карточек уже есть: {len(done)}; скачать: {len(todo)}")
    for n, fid in enumerate(todo, start=1):
        rec = parse_film(fid, fetch(f"p=show_film&fid={fid}", args.pause))
        if rec:
            with gzip.open(out, "at", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        else:
            print(f"  fid {fid}: карточка не разобрана", file=sys.stderr)
        if n % 200 == 0 or n == len(todo):
            print(f"  карточек {n}/{len(todo)}")
    print(f"Файл: {out}")


if __name__ == "__main__":
    main()
