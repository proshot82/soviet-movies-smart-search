# -*- coding: utf-8 -*-
"""Ф6-П2-б: полная сверка title каталога ↔ мастер (title_canon / xlsx_title) — нормализованное сравнение и классификация."""
import json, re, difflib
from collections import Counter
cat = json.load(open('state/catalog_f6_p1.json', encoding='utf-8'))
al = json.load(open('state/alignment_f6_p1.json', encoding='utf-8'))
m = json.load(open('state/index_master_f6_p1.json', encoding='utf-8'))
card = {r['cat_pos']: r for r in m['rows'] if r['kind'] == 'card'}
def norm(s):
    s = (s or '').lower().replace('ё', 'е')
    return re.sub(r'[^а-яa-z0-9]+', '', s)
def norm_sp(s):
    s = (s or '').lower().replace('ё', 'е')
    return re.sub(r'[^а-яa-z0-9]+', ' ', s).strip()
# печатные головы: строки томов, начинающиеся с ЗАГЛАВНЫХ (голова статьи)
heads = {}
for v in range(1, 16):
    lines = json.load(open(f'work/v{v}_lines.json', encoding='utf-8'))
    heads[f'v{v}'] = [(n, t) for n, t, p in lines]
def find_head(vol, title):
    """ищем строку тома, в которой нормализованный титул встречается как начало (после возможного OCR-мусора) и далее идёт жанр/точка"""
    nt = norm_sp(title)
    if not nt: return []
    hits = []
    for n, t in heads[vol]:
        if t[:1].isupper() or True:
            s = norm_sp(t)
            if s.startswith(nt) or (' ' + nt + ' ') in (' ' + s[:len(nt) + 40] + ' '):
                # голова: титул в верхнем регистре в исходной строке
                up = re.sub(r'[^А-ЯЁA-Z0-9]+', ' ', t.upper()).strip()
                hits.append((n, t[:120]))
    return hits
out = []
cls = Counter()
for i, r in enumerate(cat):
    t = r['title']; c = card[i]['title_canon']; x = card[i]['xlsx_title']; mt = al[i]['master_title']
    if norm(t) == norm(c):
        continue
    nt, nc = norm(t), norm(c)
    rec = {'cat': i, 'cat_f5': al[i]['cat_pos_f5'], 'source': r['source'], 'year': r['year'], 'title': t, 'title_canon': c, 'xlsx_title': x, 'master_title': mt, 'title_source': card[i]['title_source'], 'num': card[i]['num'], 'xlsx_row': card[i]['xlsx_row']}
    if nc and nt.startswith(nc) and re.match(r'^\s*\(', t[len(t) - (len(t) - len(c)):]) if False else False:
        pass
    # класс ALT: title = canon + ' (…)' (альтернативные названия / серии в скобках)
    if nc and nt.startswith(nc) and t[:len(c)] == c and re.match(r'^\s*[\(\[«]', t[len(c):]):
        k = 'ALT'
    elif nc and nt.startswith(nc):
        k = 'EXT'   # расширение без скобок
    elif nt and nc.startswith(nt):
        k = 'SHORT'  # каталог короче мастера
    else:
        ratio = difflib.SequenceMatcher(None, nt, nc).ratio()
        k = 'OCR?' if ratio >= 0.8 else 'DIFF'
        rec['ratio'] = round(ratio, 3)
    rec['class'] = k
    cls[k] += 1
    out.append(rec)
json.dump(out, open('work/f6_p2_titles_scan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(cls, len(out))
