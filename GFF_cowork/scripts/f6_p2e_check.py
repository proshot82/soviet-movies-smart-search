# -*- coding: utf-8 -*-
"""Ф6-П2е — независимая приёмка результата (читает файлы с диска, apply не использует).
Запуск из корня: python3 scripts/f6_p2e_check.py
Логика db_check: счётчики, точные дубли title+year, гистограмма лет; плюс: пустые поля == реестр, страёв 0,
биекция каталог ↔ alignment ↔ мастер, синхронность титулов, состав правок == санкция, прочее байт-в-байт,
маркеры титров, остаточный OCR-мусор (символы, латиница внутри кириллицы, «Зак. №», «Сов. худ. фильмы», номера страниц),
целостность букв для «безопасных» классов, титул ↔ указатель."""
import json, hashlib, re
from collections import Counter
cat = json.load(open('state/catalog_f6_p2e.json', encoding='utf-8'))
al = json.load(open('state/alignment_f6_p2e.json', encoding='utf-8'))
m = json.load(open('state/index_master_f6_p2e.json', encoding='utf-8'))
reg = json.load(open('state/Ф5_стабы_реестр.json', encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
cat0 = json.load(open('backups/catalog_f6_p2d.json', encoding='utf-8'))
al0 = json.load(open('backups/alignment_f6_p2d.json', encoding='utf-8'))
m0 = json.load(open('backups/index_master_f6_p2d.json', encoding='utf-8'))
prot = json.load(open('scripts/_f6_p2e_sanction.json', encoding='utf-8'))
N = len(cat)
sha = hashlib.sha256(open('state/catalog_f6_p2e.json', 'rb').read()).hexdigest()
print(f'=== РАЗМЕР === записей {N}; sha256 {sha[:16]}…; ключи {dict(Counter(k for r in cat for k in r))}')
assert N == 7173 == len(cat0)
print('=== ПО ТОМАМ ===', dict(Counter(r['source'] for r in cat)))
assert Counter(r['source'] for r in cat) == Counter(r['source'] for r in cat0)
assert [a['cat_pos'] for a in al if a['xlsx_row'] is None] == [] and m['strays'] == []
cards = [r for r in m['rows'] if r['kind'] == 'card']
print(f"=== МАСТЕР === rows {len(m['rows'])}: {dict(Counter(r['kind'] for r in m['rows']))}; card cat_pos биекция: {sorted(r['cat_pos'] for r in cards) == list(range(N))}")
assert len(al) == N and all(a['cat_pos'] == i for i, a in enumerate(al)) and al == al0 and m['rows'] == m0['rows']
assert len({a['xlsx_row'] for a in al}) == N and len({r['xlsx_row'] for r in m['rows']}) == len(m['rows']) == 7203
assert {r['cat_pos']: r['xlsx_row'] for r in cards} == {a['cat_pos']: a['xlsx_row'] for a in al}
assert all(r['vol'] == cat[r['cat_pos']]['source'] for r in cards)
bycat = {r['cat_pos']: r for r in cards}
assert all(al[i]['master_title'] == bycat[i]['title_canon'] for i in range(N) if al[i]['master_title'] is not None), 'master_title ≠ title_canon'
assert m['_meta']['name'] == 'index_master_f6_p2e' and m['_meta']['f6_p2e']['catalog'] == 'state/catalog_f6_p2e.json'
print('=== СТРАИ === 0; alignment и строки мастера == П2д (байт-в-байт); alignment.master_title == title_canon: OK')
none = {f: sorted(i for i, r in enumerate(cat) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
regn = {f: sorted(e['cat'] for e in reg['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
print('=== ПУСТЫЕ ПОЛЯ === каталог:', {f: len(v) for f, v in none.items()}, '; реестр none:', {f: len(v) for f, v in regn.items()}, '; совпадение позиций:', all(none[f] == regn[f] for f in regn))
assert all(none[f] == regn[f] for f in regn) and none['year'] == [] and len(none['annotation']) == 8
assert len(reg['entries']) == 111 and all(cat[e['cat']]['title'] == e['title'] for e in reg['entries']), 'реестр: title ↔ cat'
assert [e for e in reg['entries'] if e['cat'] == 2958][0]['state'] == 'source-only' and reg['catalog'] == 'state/catalog_f6_p2e.json'
assert all(cat[e['cat']]['title'] == e['title'] for k in ('genre', 'studio_empty', 'annotation') for e in q[k]), 'очередь: title ↔ cat'
dups = [(k, c) for k, c in Counter((r['title'], r['year']) for r in cat).items() if c > 1]
print('=== ТОЧНЫЕ ДУБЛИ title+year ===', len(dups), [(t, y, [i for i, r in enumerate(cat) if (r['title'], r['year']) == (t, y)]) for (t, y), c in dups])
assert len(dups) == 3
# санкция
setpos = {(x['cat'], x['field']) for x in prot['set']}
assert all(f == 'annotation' for _, f in setpos)
for x in prot['set']:
    assert cat[x['cat']]['annotation'] == x['after'] and cat0[x['cat']]['annotation'] == x['before'], f'санкция cat{x["cat"]}'
cnt = 0
for i in range(N):
    for k in set(cat0[i]) | set(cat[i]):
        if (i, k) in setpos: continue
        assert cat0[i].get(k) == cat[i].get(k), f'вне санкции: cat{i}/{k}'; cnt += 1
assert [(r['title'], r['year'], r['studio'], r['genre'], r['source']) for r in cat] == [(r['title'], r['year'], r['studio'], r['genre'], r['source']) for r in cat0], 'И5′'
print('=== САНКЦИЯ === set', len(prot['set']), '(annotation); прочих полей сверено байт-в-байт:', cnt, '; удалений 0; титулы/годы/студии/жанры неизменны')
# воспроизводимость: ops резолюции применяются к before и дают after; каждая операция — одно слово
def letters(s): return re.sub(r'[^А-ЯЁа-яё]', '', s)
bad = []
for x in prot['set']:
    t = x['before']
    for o in x['ops']:
        if o[0] == 'O':
            pat = re.compile((r'(?<![А-ЯЁа-яё-])' if ' ' in o[1] else r'(?<![А-ЯЁа-яё])') + re.escape(o[1]) + (r'(?![А-ЯЁа-яё-])' if ' ' in o[1] else r'(?![А-ЯЁа-яё])'))
            if len(pat.findall(t)) != 1: bad.append((x['cat'], o[1])); continue
            t = pat.sub(o[2], t)
        else:
            if t.count(o[1]) != 1: bad.append((x['cat'], o[1])); continue
            t = t.replace(o[1], o[2])
    if t != x['after'] or abs(len(letters(x['after'])) - len(letters(x['before']))) > 2 * len(x['ops']): bad.append((x['cat'], 'after'))
print('=== ВОСПРОИЗВОДИМОСТЬ ОПЕРАЦИЙ === нарушений:', len(bad), bad); assert not bad
# маркеры титров
MARK = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Фильм озвучен|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер|гл\. опер|Реж\.-пост|Опер\.-пост)')
mk = [(i, MARK.search(r['annotation']).group()) for i, r in enumerate(cat) if r['annotation'] and MARK.search(r['annotation'])]
print('=== МАРКЕРЫ ТИТРОВ (жёсткие) в аннотациях ===', len(mk), mk); assert not mk
# остаточный OCR-мусор
JUNK = re.compile(r'[\^■❖©®|\\@<>*•।_\[\]{}#$£™¡¿“”„"’‘`]')
jk = [(i, ''.join(sorted(set(JUNK.findall(r['annotation']))))) for i, r in enumerate(cat) if r['annotation'] and JUNK.search(r['annotation'])]
print('=== МУСОРНЫЕ СИМВОЛЫ в аннотациях ===', len(jk), jk[:20])
assert all(s == '’' for i, s in jk), jk   # ’ только в иноязычных именах (О’Сюлливен, О’Бриен, д’Артаньян…)
assert all(re.fullmatch(r"[ОДд]’[А-ЯЁ]", x) for i, s in jk for x in re.findall(r'.’.', cat[i]['annotation'])), 'апостроф вне имени'
LAT = re.compile(r'(?<![A-Za-z])[A-Za-z]+(?![A-Za-z])')
ROMAN = re.compile(r'^[IVXLCM]+$')
lat = []
for i, r in enumerate(cat):
    if not r['annotation']: continue
    for mm in LAT.finditer(r['annotation']):
        w = mm.group(0)
        if ROMAN.match(w) or w in ('SOS', 'F', 'Jude'): continue
        lat.append((i, w, r['annotation'][max(0, mm.start() - 15):mm.end() + 15]))
print('=== ЛАТИНИЦА в аннотациях (кроме римских цифр/SOS/Jude/F-9) ===', len(lat), lat)
assert [(i, w) for i, w, _ in lat] == [(2712, 'cho'), (3305, 'w')], 'оставлены сознательно (чтение неоднозначно) — список кандидатов'
sig = [(i, r['annotation'][max(0, mm.start() - 20):mm.end() + 20]) for i, r in enumerate(cat) if r['annotation'] for mm in re.finditer(r'Зак[,.]\s?№|Сов\. худ\. фильмы|[А-ЯЁа-яё]+- \d{1,4}\*? [а-яё]|^.{0,60}(?<!\()ВЭ \d|^\S{0,4}\d{1,3}\.[IVX]+\.\s?\d{4}', r['annotation'])]
print('=== СИГНАТУРЫ/КОЛОНТИТУЛЫ/ВЭ в аннотациях ===', len(sig), sig); assert not sig
hy = [(i, r['annotation'][max(0, mm.start() - 15):mm.end() + 15]) for i, r in enumerate(cat) if r['annotation'] for mm in re.finditer(r'[А-ЯЁа-яё]- [а-яё]', r['annotation'])]
print('=== ОСТАТОЧНЫЕ ПЕРЕНОСЫ «w1- w2» ===', len(hy), hy); assert [i for i, _ in hy] == [6437, 6481]
ws = [i for i, r in enumerate(cat) if r['annotation'] and ('  ' in r['annotation'] or r['annotation'] != r['annotation'].strip() or '\t' in r['annotation'])]
print('=== ДВОЙНЫЕ ПРОБЕЛЫ/КРАЕВЫЕ ПРОБЕЛЫ ===', len(ws), ws[:10]); assert not ws
nl = [i for i, r in enumerate(cat) if r['annotation'] and '\n' in r['annotation']]
print('=== ПЕРЕВОДЫ СТРОК (многоновелльные) ===', nl); assert nl == [3638, 4218, 4750, 4823]
def nm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))
diff = [(i, cat[i]['title'], bycat[i]['title_canon']) for i in range(N) if nm(re.sub(r'\s*\(«.*$', '', cat[i]['title'])) != nm(bycat[i]['title_canon']) and nm(cat[i]['title']) != nm(bycat[i]['title_canon'])]
print('=== ТИТУЛ ↔ title_canon мастера (норм.) === расхождений:', len(diff), diff)
assert diff == [(2682, 'Загадка Н. Ф. И. и другие устные рассказы Ираклия Андроникова', 'Загадка Н. Ф. И.')]
yc = Counter(r['year'] for r in cat if r['year'] is not None)
print('=== ГОДЫ === по десятилетиям:', {d: sum(c for y, c in yc.items() if y // 10 * 10 == d) for d in sorted({y // 10 * 10 for y in yc})})
short = [i for i, r in enumerate(cat) if r['annotation'] is not None and len(r['annotation']) < 100]
print('=== АННОТАЦИИ < 100 зн. (не None) ===', len(short))
nofin = [i for i, r in enumerate(cat) if r['annotation'] and not re.search(r'[.!?…»)"\']$', r['annotation'])]
print('=== АННОТАЦИИ без конечной пунктуации ===', len(nofin), '(системный класс — П3)')
print('OK: приёмка Ф6-П2е пройдена')
