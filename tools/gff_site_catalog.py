#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выгрузка каталога фильмов с сайта gosfilmofond.ru (название, год, жанр, страна, описание, URL).

    python tools/gff_site_catalog.py                       # → imports/gff_site_catalog.jsonl.gz, с докачкой
    python tools/gff_site_catalog.py --pages 3             # проба: первые 3 страницы

Каталог на сайте подгружается запросом POST /wp-admin/admin-ajax.php (action=filter_films) —
этот адрес robots.txt сайта разрешает явно («Allow: /wp-admin/admin-ajax.php»); карта сайта
(/wp-sitemap*.xml) и поиск с параметрами в адресе — запрещены, их не трогаем. В выдаче по 100 фильмов
на страницу с полным описанием (сверено с карточкой /films/<id>/: тексты совпадают). Фильтр по годам
сервер не применяет, поэтому выгружается весь каталог (~600 страниц, ~60 тыс. фильмов).

Запросы строго по одному, с паузой --pause секунд; при ошибке — повтор с нарастающей паузой.
Готовые страницы дописываются в файл сразу: повторный запуск продолжит с первой недокачанной.
"""
import argparse
import gzip
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://gosfilmofond.ru/wp-admin/admin-ajax.php"
UA = "SovietMoviesSearch/0.1 (+https://github.com/proshot82/soviet-movies-smart-search)"
PAGE_SIZE = 100


def fetch_page(page, tries=5):
    data = urllib.parse.urlencode({"action": "filter_films", "paged": page, "page_count": PAGE_SIZE,
                                   "year_from": 1900, "year_to": 2019, "order": "", "search": ""}).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(URL, data=data, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=120).read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            wait = 10 * 2 ** attempt
            print(f"  страница {page}: {e}; повтор через {wait} с", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"страница {page} не скачалась за {tries} попыток — перезапустите позже, докачка продолжится")


def text_of(fragment):
    """HTML описания → текст: абзацы <p>/<br> — переводы строк, остальные теги убираются."""
    t = re.sub(r"(?i)<br\s*/?>|</p\s*>", "\n", fragment)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n*", "\n", t).strip()


def parse_page(page_html):
    films = []
    for block in re.split(r'<div class="film-item">', page_html)[1:]:
        m = re.search(r'<div class="title">\s*<a href="(https://gosfilmofond\.ru/films/(\d+)/)">(.*?)</a>', block, re.S)
        if not m:
            continue

        def span(cls):
            s = re.search(rf'<span class="{cls}">(.*?)</span>', block, re.S)
            return text_of(s.group(1)) if s else None
        ann = re.search(r'<div class="annonce">(.*?)</div>', block, re.S)
        year = span("year")
        films.append({"gff_id": int(m.group(2)), "url": m.group(1), "title": text_of(m.group(3)),
                      "year_raw": year, "year": int(year[:4]) if year and year[:4].isdigit() else None,
                      "genre": span("genre"), "country": span("country"),
                      "annotation": text_of(ann.group(1)) if ann else None})
    last = re.findall(r'class="page-numbers" href="(\d+)"', page_html)
    return films, max(map(int, last)) if last else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "imports" / "gff_site_catalog.jsonl.gz"))
    ap.add_argument("--pages", type=int, help="скачать не больше стольких страниц (проба)")
    ap.add_argument("--pause", type=float, default=2.0, help="пауза между запросами, с")
    args = ap.parse_args()

    out = Path(args.out)
    done = set()
    if out.exists():
        with gzip.open(out, "rt", encoding="utf-8") as f:
            done = {json.loads(line)["page"] for line in f if line.strip()}
    page, total, fetched = 1, None, 0
    while total is None or page <= total:
        if page in done and total is not None:
            page += 1
            continue
        films, last = parse_page(fetch_page(page))
        total = max(total or 0, last or page)
        if page not in done:
            with gzip.open(out, "at", encoding="utf-8") as f:
                for film in films:
                    f.write(json.dumps(dict(film, page=page), ensure_ascii=False) + "\n")
            fetched += 1
            if fetched % 25 == 0 or page == total:
                print(f"  страница {page}/{total}")
        page += 1
        if args.pages and fetched >= args.pages:
            break
        time.sleep(args.pause)
    print(f"Скачано страниц: {fetched}; файл: {out}")


if __name__ == "__main__":
    main()
