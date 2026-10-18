# -*- coding: utf-8 -*-
"""Ф6-П1 — независимая приёмка результата (читает файлы с диска, apply не использует).
Запуск из корня: python3 scripts/f6_p1_check.py
Логика db_check: счётчики, точные дубли title+year, гистограмма лет; плюс: пустые поля == реестр,
страёв 0, биекция каталог ↔ alignment ↔ мастер, состав удалённого/восстановленного == диспозиция."""
import json, hashlib, re
from collections import Counter
cat = json.load(open('state/catalog_f6_p1.json', encoding='utf-8'))
al = json.load(open('state/alignment_f6_p1.json', encoding='utf-8'))
m = json.load(open('state/index_master_f6_p1.json', encoding='utf-8'))
reg = json.load(open('state/Ф5_стабы_реестр.json', encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
disp = json.load(open('state/Ф6_страи_диспозиция.json', encoding='utf-8'))
cat0 = json.load(open('backups/catalog_f5.json', encoding='utf-8'))
prot = json.load(open('scripts/_f6_p1_sanction.json', encoding='utf-8'))
N = len(cat)
sha = hashlib.sha256(open('state/catalog_f6_p1.json', 'rb').read()).hexdigest()
print(f'=== РАЗМЕР === записей {N}; sha256 {sha[:16]}…; ключи {dict(Counter(k for r in cat for k in r))}')
assert N == 7173 == disp['_meta']['summary']['expected_catalog_after']
print('=== ПО ТОМАМ ===', dict(Counter(r['source'] for r in cat)))
# страи
strays = [a['cat_pos'] for a in al if a['xlsx_row'] is None]
print('=== СТРАИ === alignment xlsx_row=None:', len(strays), '; master strays:', len(m['strays']))
assert strays == [] and m['strays'] == []
# биекция
cards = [r for r in m['rows'] if r['kind'] == 'card']
print(f"=== МАСТЕР === rows {len(m['rows'])}: {dict(Counter(r['kind'] for r in m['rows']))}; card cat_pos биекция: {sorted(r['cat_pos'] for r in cards) == list(range(N))}")
assert len(al) == N and all(a['cat_pos'] == i for i, a in enumerate(al))
assert len({a['xlsx_row'] for a in al}) == N and len({r['xlsx_row'] for r in m['rows']}) == len(m['rows'])
assert {r['cat_pos']: r['xlsx_row'] for r in cards} == {a['cat_pos']: a['xlsx_row'] for a in al}
assert all(r['vol'] == cat[r['cat_pos']]['source'] for r in cards)
# пустые поля vs реестр
none = {f: sorted(i for i, r in enumerate(cat) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
regn = {f: sorted(e['cat'] for e in reg['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
print('=== ПУСТЫЕ ПОЛЯ === каталог:', {f: len(v) for f, v in none.items()}, '; реестр none:', {f: len(v) for f, v in regn.items()}, '; совпадение позиций:', all(none[f] == regn[f] for f in regn))
assert all(none[f] == regn[f] for f in regn) and none['year'] == []
assert len(reg['entries']) == 114 and all(cat[e['cat']]['title'] == e['title'] for e in reg['entries']), 'реестр: title ↔ cat'
# очередь
print('=== ОЧЕРЕДЬ ===', {k: (len(v) if isinstance(v, list) else '…') for k, v in q.items()})
assert q['year_empty'] == [] and [e['cat_f5'] for e in q['annotation']] == [3876, 3877]
assert all(cat[e['cat']]['title'] == e['title'] for k in ('genre', 'studio_empty', 'annotation') for e in q[k]), 'очередь: title ↔ cat'
# точные дубли title+year
dups = [(k, c) for k, c in Counter((r['title'], r['year']) for r in cat).items() if c > 1]
print('=== ТОЧНЫЕ ДУБЛИ title+year ===', len(dups))
for (t, y), c in sorted(dups, key=lambda x: (x[0][1] or 0)):
    pos = [i for i, r in enumerate(cat) if (r['title'], r['year']) == (t, y)]
    print(f'  {c}x {t!r} ({y}) cat{pos} студии {[cat[i]["studio"] for i in pos]}')
# состав удалённого/восстановленного
deleted = {x['cat'] for x in prot['delete']}
kept_titles = [(cat0[i]['title'], cat0[i]['source']) for i in range(len(cat0)) if i not in deleted]
assert kept_titles == [(r['title'], r['source']) for r in cat], 'И5′ повторно'
for x in prot['set']:
    assert cat[x['cat_new']][x['field']] == x['after'] and cat[x['cat_new']]['title'] == x['title']
    assert cat0[x['cat']][x['field']] == x['before']
print('=== САНКЦИЯ === set', len(prot['set']), 'подтверждён в каталоге; delete', len(deleted), '; перенумерованных позиций', len(prot['renumbering']))
# ничего вне санкции: остальные поля байт-в-байт
new_of = {int(k): v for k, v in prot['renumbering'].items()}
setpos = {(x['cat'], x['field']) for x in prot['set']}
cnt = 0
for old in range(len(cat0)):
    if old in deleted: continue
    new = new_of.get(old, old)
    for k in set(cat0[old]) | set(cat[new]):
        if (old, k) in setpos: continue
        assert cat0[old].get(k) == cat[new].get(k), f'вне санкции: cat{old}/{k}'
        cnt += 1
print('   прочих полей сверено байт-в-байт:', cnt)
# маркеры титров в аннотациях целей
MARK = re.compile(r'(Авт\. сцен|реж\.-пост|звукоопер|В ролях|Библиография|дир\. картины)')
print('   маркеры титров в аннотациях 14 целей + cat1197:', [x['cat_new'] for x in prot['set'] if x['field'] == 'annotation' and MARK.search(cat[x['cat_new']]['annotation'])])
# гистограмма
yc = Counter(r['year'] for r in cat if r['year'] is not None)
print('=== ГОДЫ === по десятилетиям:', {d: sum(c for y, c in yc.items() if y // 10 * 10 == d) for d in sorted({y // 10 * 10 for y in yc})}, '; вне 1915–1992:', sorted(y for y in yc if y < 1915 or y > 1992))
VOL = {'v1': (1918, 1935), 'v2': (1930, 1957), 'v3': (1958, 1963), 'v4': (1964, 1965), 'v5': (1966, 1967), 'v6': (1968, 1969), 'v7': (1970, 1971), 'v8': (1972, 1973), 'v9': (1974, 1975), 'v10': (1976, 1977), 'v11': (1978, 1979), 'v12': (1980, 1981), 'v13': (1982, 1983), 'v14': (1984, 1985), 'v15': (1986, 1987)}
out = [(i, r['title'][:30], r['year'], r['source']) for i, r in enumerate(cat) if r['year'] is not None and not (VOL[r['source'].split('_')[0]][0] - 1 <= r['year'] <= VOL[r['source'].split('_')[0]][1] + 1)]
print('   годы вне диапазона тома ±1:', len(out), out)
# короткие аннотации
short = [i for i, r in enumerate(cat) if r['annotation'] is not None and len(r['annotation']) < 100]
print('=== АННОТАЦИИ < 100 зн. (не None) ===', len(short))
print('=== ИНВЕНТАРЬ === уникальных genre:', len({r['genre'] for r in cat if r['genre']}), '; studio:', len({r['studio'] for r in cat if r['studio']}))
# cat1197 → строка мастера
r2106 = [r for r in m['rows'] if r['xlsx_row'] == 2106][0]
print('=== cat1197 → row 2106 ===', {k: r2106[k] for k in ('kind', 'num', 'title_canon', 'cat_pos', 'cat_pos_f5', 'xlsx_title')}, '; каталог:', {k: cat[r2106['cat_pos']][k] for k in ('title', 'genre', 'year', 'studio')})
print('OK: приёмка Ф6-П1 пройдена')
