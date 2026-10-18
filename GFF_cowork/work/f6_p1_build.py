# -*- coding: utf-8 -*-
"""Ф6-П1: сборка резолюции scripts/f6_p1_resolution.json из state/Ф6_страи_диспозиция.json.
Запуск из корня: python3 work/f6_p1_build.py
Тексты RESTORE/APPEND/KEEP берутся из диспозиции как есть (verbatim по печати, проверены в финале Ф5
и повторно здесь: каждый печатный сегмент @строк присутствует в after; остаток — только заголовки
новелл по правилу k4). before сверяется с каталогом байт-в-байт."""
import json, re, sys
d = json.load(open('state/Ф6_страи_диспозиция.json', encoding='utf-8'))
cat = json.load(open('state/catalog_f5.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a['xlsx_row'] is None}
assert len(cat) == 7232 and len(strays) == 60
LINES = {}
def lines(vol):
    v = vol.split('_')[0]
    if v not in LINES: LINES[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    return LINES[v]
def norm(s):
    s = (s or '').lower().replace('ё', 'е')
    return re.sub(r'[^а-яa-z0-9]+', ' ', s).strip()
def segments(vol, nums):
    L = lines(vol); byn = {n: t for n, t, p in L}
    segs, cur, prev = [], '', None
    for n in nums:
        t = byn[n]
        if cur and prev is not None and n == prev + 1:
            cur = (cur[:-1] + t) if cur.endswith('-') else (cur + ' ' + t)
        else:
            if cur: segs.append(cur)
            cur = t
        prev = n
    if cur: segs.append(cur)
    return segs
def print_check(after, vol, nums):
    """все печатные сегменты присутствуют в after (пофразно); вернуть остаток after вне печати"""
    resid = ' ' + norm(after) + ' '
    for s in segments(vol, nums):
        parts = [norm(x) for x in re.split(r'(?<=[.!?…])\s+', s) if norm(x)]
        for p in parts:
            assert ' ' + p + ' ' in resid, f'сегмент печати не найден в after: {p[:80]!r}'
            resid = resid.replace(' ' + p + ' ', ' ', 1)
    return re.sub(r'\s+', ' ', resid).strip()

SET = []
strays_by_cat = {s['cat']: s for s in d['strays']}
for tgt, v in d['actions']['restore'].items():
    c = int(tgt)
    assert c not in strays and cat[c]['annotation'] == v['before'], f'restore cat{c}: before'
    resid = print_check(v['after'], v['vol'], v['lines'])
    SET.append({'cat': c, 'title': cat[c]['title'], 'source': cat[c]['source'], 'field': 'annotation',
                'before': v['before'], 'after': v['after'], 'vol': v['vol'], 'lines': v['lines'],
                'class': 'restore', 'from_strays': v['from_strays'],
                'residual_outside_print': resid or None, 'note': v['note']})
for tgt, v in d['actions']['append'].items():
    c = int(tgt)
    assert c not in strays and cat[c]['annotation'] == v['before'], f'append cat{c}: before'
    assert v['after'].startswith(v['before']), f'append cat{c}: after не начинается с before'
    resid = print_check(v['after'][len(v['before']):], v['vol'], v['lines'])
    assert resid == '', f'append cat{c}: хвост не из печати: {resid!r}'
    SET.append({'cat': c, 'title': cat[c]['title'], 'source': cat[c]['source'], 'field': 'annotation',
                'before': v['before'], 'after': v['after'], 'vol': v['vol'], 'lines': v['lines'],
                'class': 'append', 'from_strays': [v['from_stray']], 'residual_outside_print': None,
                'note': v['note']})
k = d['actions']['keep']['1197']
assert 1197 in strays and cat[1197]['title'] == 'Рядом с нами'
st = k['fields']['studio']
assert cat[1197]['studio'] == st['before'] and st['before'].startswith(st['after'])
SET.append({'cat': 1197, 'title': 'Рядом с нами', 'source': cat[1197]['source'], 'field': 'studio',
            'before': st['before'], 'after': st['after'], 'vol': 'v2_1936-1957', 'lines': [124],
            'class': 'studio', 'from_strays': [], 'residual_outside_print': None, 'note': st['note']})
an = k['fields']['annotation']
assert cat[1197]['annotation'] == an['before']
resid = print_check(an['after'], 'v2_1936-1957', an['lines'])
assert resid == ''
SET.append({'cat': 1197, 'title': 'Рядом с нами', 'source': cat[1197]['source'], 'field': 'annotation',
            'before': an['before'], 'after': an['after'], 'vol': 'v2_1936-1957', 'lines': an['lines'],
            'class': 'restore', 'from_strays': [], 'residual_outside_print': None, 'note': an['note']})
assert k['fields']['genre']['value'] == cat[1197]['genre'] == 'Драма'
assert k['fields']['year']['value'] == cat[1197]['year'] == 1931

DEL = []
for c in sorted(d['actions']['delete']):
    s = strays_by_cat[c]
    assert s['verdict'].startswith('delete') and c in strays
    DEL.append({'cat': c, 'title': cat[c]['title'], 'source': cat[c]['source'], 'year': cat[c]['year'],
                'stray_class': s['class'], 'verdict': s['verdict'], 'target': s['target'],
                'target_title': s.get('target_title'), 'target_num': s.get('target_num'),
                'vol': s['vol'], 'lines': s['lines'], 'note': s['note']})
assert {x['cat'] for x in DEL} == strays - {1197} and len(DEL) == 59

MASTER = {'1197': {**k['master_row'], 'kind': 'card', 'xlsx_num': '1184а',
                   'title_source': 'печатная голова v2 @124 («1184 а. РЯДОМ С НАМИ…»)',
                   'provenance': 'xlsx row 2106 (склейка «Рядовой Александр Матросов 1888 Рядом с нами» разделена в Ф6-П1: '
                                 '№1888 → row 7182/cat1901; хвост «Рядом с нами» №1184а → эта запись) + печатная голова v2 @124'}}
res = {'_meta': {'package': 'Ф6-П1 страи', 'generated': '2026-09-02',
                 'input_catalog': 'state/catalog_f5.json (7232)',
                 'disposition': 'state/Ф6_страи_диспозиция.json',
                 'expected_after': {'catalog': 7173, 'master_card': 7173, 'master_rows': 7203,
                                    'master_noncard': 30, 'strays': 0},
                 'classes': {'restore': 'аннотация цели по печати (RESTORE/слияние новелл k4); vol/@строки; маркеров титров нет',
                             'append': 'after = before + печатное примечание после прозы (verbatim @строки)',
                             'studio': 'cat1197: снять хвост «, 1931 г» (правило П2/П5), печатно @124',
                             'delete': 'страи по диспозиции (verdict delete*), 59'},
                 'decisions': {'D1': 'cat3405 «Внимание! В городе волшебник» — по умолчанию: v3 без изменений (владелец не решал иначе)'},
                 'renumbering': 'cat_new = cat_old − |{удалённые страи с индексом < cat_old}|; карта — alignment_f6_p1.json (cat_pos_f5 → cat_pos)'},
       'set': SET, 'delete': DEL, 'master': MASTER}
json.dump(res, open('scripts/f6_p1_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
from collections import Counter
print('set', len(SET), dict(Counter((x['field'], x['class']) for x in SET)), '; delete', len(DEL),
      dict(Counter(x['stray_class'] for x in DEL)))
for x in SET:
    if x['residual_outside_print']: print(f"  cat{x['cat']} остаток вне @строк (заголовки новелл k4): {x['residual_outside_print']!r}")
