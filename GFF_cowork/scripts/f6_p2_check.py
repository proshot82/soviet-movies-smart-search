# -*- coding: utf-8 -*-
"""Ф6-П2 — независимая приёмка результата (читает файлы с диска, apply не использует).
Запуск из корня: python3 scripts/f6_p2_check.py
Логика db_check: счётчики, точные дубли title+year, гистограмма лет; плюс: пустые поля == реестр, страёв 0,
биекция каталог ↔ alignment ↔ мастер, синхронность титулов (§1.3), состав правок == санкция, прочее байт-в-байт,
маркеры титров в аннотациях, титул ↔ указатель (нормализованно)."""
import json, hashlib, re
from collections import Counter
cat = json.load(open('state/catalog_f6_p2.json', encoding='utf-8'))
al = json.load(open('state/alignment_f6_p2.json', encoding='utf-8'))
m = json.load(open('state/index_master_f6_p2.json', encoding='utf-8'))
reg = json.load(open('state/Ф5_стабы_реестр.json', encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
cat0 = json.load(open('backups/catalog_f6_p1.json', encoding='utf-8'))
al0 = json.load(open('backups/alignment_f6_p1.json', encoding='utf-8'))
m0 = json.load(open('backups/index_master_f6_p1.json', encoding='utf-8'))
prot = json.load(open('scripts/_f6_p2_sanction.json', encoding='utf-8'))
N = len(cat)
sha = hashlib.sha256(open('state/catalog_f6_p2.json', 'rb').read()).hexdigest()
print(f'=== РАЗМЕР === записей {N}; sha256 {sha[:16]}…; ключи {dict(Counter(k for r in cat for k in r))}')
assert N == 7173 == len(cat0)
print('=== ПО ТОМАМ ===', dict(Counter(r['source'] for r in cat)))
assert Counter(r['source'] for r in cat) == Counter(r['source'] for r in cat0)
# страи / биекция
assert [a['cat_pos'] for a in al if a['xlsx_row'] is None] == [] and m['strays'] == []
cards = [r for r in m['rows'] if r['kind'] == 'card']
print(f"=== МАСТЕР === rows {len(m['rows'])}: {dict(Counter(r['kind'] for r in m['rows']))}; card cat_pos биекция: {sorted(r['cat_pos'] for r in cards) == list(range(N))}")
assert len(al) == N and all(a['cat_pos'] == i for i, a in enumerate(al))
assert len({a['xlsx_row'] for a in al}) == N and len({r['xlsx_row'] for r in m['rows']}) == len(m['rows']) == 7203
assert {r['cat_pos']: r['xlsx_row'] for r in cards} == {a['cat_pos']: a['xlsx_row'] for a in al}
assert all(r['vol'] == cat[r['cat_pos']]['source'] for r in cards)
assert not [k for k, v in Counter((r['vol'], str(r['num'])) for r in cards).items() if v > 1]
bycat = {r['cat_pos']: r for r in cards}
assert all(al[i]['master_title'] == bycat[i]['title_canon'] for i in range(N) if al[i]['master_title'] is not None), 'master_title ≠ title_canon'
print('=== СТРАИ === 0; alignment.master_title == мастер.title_canon: OK')
# пустые поля vs реестр
none = {f: sorted(i for i, r in enumerate(cat) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
regn = {f: sorted(e['cat'] for e in reg['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
print('=== ПУСТЫЕ ПОЛЯ === каталог:', {f: len(v) for f, v in none.items()}, '; реестр none:', {f: len(v) for f, v in regn.items()}, '; совпадение позиций:', all(none[f] == regn[f] for f in regn))
assert all(none[f] == regn[f] for f in regn) and none['year'] == [] and none['annotation'] == regn['annotation'] and 4275 in none['annotation']
assert len(reg['entries']) == 110 and all(cat[e['cat']]['title'] == e['title'] for e in reg['entries']), 'реестр: title ↔ cat'
assert {e['cat'] for e in reg['closed_f6_p2']} == {6812, 6813, 3685, 5654, 5024}
assert all(cat[e['cat']]['title'] == e['title'] for k in ('genre', 'studio_empty', 'annotation') for e in q[k]), 'очередь: title ↔ cat'
# точные дубли title+year
dups = [(k, c) for k, c in Counter((r['title'], r['year']) for r in cat).items() if c > 1]
print('=== ТОЧНЫЕ ДУБЛИ title+year ===', len(dups))
for (t, y), c in sorted(dups, key=lambda x: (x[0][1] or 0)):
    pos = [i for i, r in enumerate(cat) if (r['title'], r['year']) == (t, y)]
    print(f'  {c}x {t!r} ({y}) cat{pos} студии {[cat[i]["studio"] for i in pos]}')
assert len(dups) == 3 and ('Пес и Кот', 1938) not in dict(dups)
# санкция: состав и значения
setpos = {(x['cat'], x['field']) for x in prot['set']}
for x in prot['set']:
    assert cat[x['cat']][x['field']] == x['after'] and cat0[x['cat']][x['field']] == x['before'], f'санкция cat{x["cat"]}/{x["field"]}'
cnt = 0
for i in range(N):
    for k in set(cat0[i]) | set(cat[i]):
        if (i, k) in setpos: continue
        assert cat0[i].get(k) == cat[i].get(k), f'вне санкции: cat{i}/{k}'
        cnt += 1
assert [(r['title'], r['source']) for i, r in enumerate(cat) if (i, 'title') not in setpos] == [(r['title'], r['source']) for i, r in enumerate(cat0) if (i, 'title') not in setpos], 'И5′'
print('=== САНКЦИЯ === set', len(prot['set']), dict(Counter(x['field'] for x in prot['set'])), '; прочих полей сверено байт-в-байт:', cnt, '; удалений 0')
# alignment/мастер вне санкции
tcats = {x['cat'] for x in prot['set'] if x['field'] == 'title'} | {mo['cat'] for mo in prot['master_only']} | {6812, 6813}
for i in range(N):
    if i not in tcats: assert al0[i] == al[i], f'alignment вне санкции cat{i}'
trows = {bycat[c]['xlsx_row'] for c in tcats}
r0 = {r['xlsx_row']: r for r in m0['rows']}
for r in m['rows']:
    if r['xlsx_row'] not in trows: assert r0[r['xlsx_row']] == r, f'мастер вне санкции row {r["xlsx_row"]}'
assert al[6812]['xlsx_row'] == 6648 and al[6813]['xlsx_row'] == 7200 and bycat[6812]['title_canon'] == cat[6812]['title'] == 'Фитиль № 281' and bycat[6813]['title_canon'] == cat[6813]['title'] == 'Фитиль № 282'
print('   alignment/мастер вне санкции: неизменны; перепривязка 6812↔6813: OK')
# маркеры титров в аннотациях (весь каталог)
MARK = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Фильм озвучен|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер|гл\. опер|Реж\.-пост|Опер\.-пост)')
mk = [(i, MARK.search(r['annotation']).group()) for i, r in enumerate(cat) if r['annotation'] and MARK.search(r['annotation'])]
print('=== МАРКЕРЫ ТИТРОВ (жёсткие) в аннотациях ===', len(mk), mk)
SOFT = re.compile(r'(дирижер|Дирижер|композ\.|монтаж\.|консульт\.)')
sk = [(i, SOFT.search(r['annotation']).group()) for i, r in enumerate(cat) if r['annotation'] and SOFT.search(r['annotation'])]
print('   мягкие слова (дирижер/композ./монтаж./консульт.) — в сюжете или концертных программах:', len(sk), [i for i, _ in sk])
# титул ↔ указатель (нормализованно, без альтернативных названий в скобках)
def nm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))
diff = [(i, cat[i]['title'], bycat[i]['title_canon']) for i in range(N) if nm(re.sub(r'\s*\(«.*$', '', cat[i]['title'])) != nm(bycat[i]['title_canon']) and nm(cat[i]['title']) != nm(bycat[i]['title_canon'])]
print('=== ТИТУЛ ↔ title_canon мастера (норм.) === расхождений:', len(diff), diff)
assert diff == [(2682, 'Загадка Н. Ф. И. и другие устные рассказы Ираклия Андроникова', 'Загадка Н. Ф. И.')]
bad_case = [i for i in range(N) if cat[i]['title'].isupper() and len(re.sub(r'[^А-ЯЁ]', '', cat[i]['title'])) > 3]
print('   титулы целиком в верхнем регистре (>3 букв):', bad_case)
# гистограмма
yc = Counter(r['year'] for r in cat if r['year'] is not None)
print('=== ГОДЫ === по десятилетиям:', {d: sum(c for y, c in yc.items() if y // 10 * 10 == d) for d in sorted({y // 10 * 10 for y in yc})}, '; вне 1915–1992:', sorted(y for y in yc if y < 1915 or y > 1992))
VOL = {'v1': (1918, 1935), 'v2': (1930, 1957), 'v3': (1958, 1963), 'v4': (1964, 1965), 'v5': (1966, 1967), 'v6': (1968, 1969), 'v7': (1970, 1971), 'v8': (1972, 1973), 'v9': (1974, 1975), 'v10': (1976, 1977), 'v11': (1978, 1979), 'v12': (1980, 1981), 'v13': (1982, 1983), 'v14': (1984, 1985), 'v15': (1986, 1987)}
out = [(i, r['title'][:30], r['year'], r['source']) for i, r in enumerate(cat) if r['year'] is not None and not (VOL[r['source'].split('_')[0]][0] - 1 <= r['year'] <= VOL[r['source'].split('_')[0]][1] + 1)]
print('   годы вне диапазона тома ±1:', len(out))
short = [i for i, r in enumerate(cat) if r['annotation'] is not None and len(r['annotation']) < 100]
print('=== АННОТАЦИИ < 100 зн. (не None) ===', len(short))
nofin = [i for i, r in enumerate(cat) if r['annotation'] and not re.search(r'[.!?…»)"\']$', r['annotation'])]
print('=== АННОТАЦИИ без конечной пунктуации ===', len(nofin), '(системный класс — П3)')
print('=== ИНВЕНТАРЬ === уникальных genre:', len({r['genre'] for r in cat if r['genre']}), '; studio:', len({r['studio'] for r in cat if r['studio']}))
print('=== cat2243 ===', {k: cat[2243][k] for k in ('title', 'genre', 'year', 'studio')}, cat[2243]['annotation'][:80])
print('OK: приёмка Ф6-П2 пройдена')
