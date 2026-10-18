# -*- coding: utf-8 -*-
"""Ф6 финал — независимая приёмка финального каталога v2 (после корректирующих пакетов П3а, П3б и П3в) (читает файлы с диска, apply не использует).
Запуск из корня: python3 scripts/f6_final_check.py
Логика db_check (счётчики, точные дубли title+year, гистограмма лет) + схема финала (id 1..N, 7 полей, без служебных ключей),
состав правок == санкция (только annotation; прочее байт-в-байт с backups/catalog_f6_p2e.json), И4/И5′, биекция каталог ↔ alignment ↔
мастер (+id), реестр (пустые поля == реестр), маркеры титров/библиографии, призовые хвосты, OCR-мусор, титул ↔ указатель."""
import json, hashlib, re, os
from collections import Counter
cat = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
al = json.load(open('state/alignment_final.json', encoding='utf-8'))
m = json.load(open('state/index_master_final.json', encoding='utf-8'))
reg = json.load(open('state/Ф5_стабы_реестр.json', encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
cat0 = json.load(open('backups/catalog_final_v1.json', encoding='utf-8'))
al0 = json.load(open('backups/alignment_final_p3_20260904-0747.json', encoding='utf-8'))
m0 = json.load(open('backups/index_master_final_p3_20260904-0747.json', encoding='utf-8'))
prot = json.load(open('scripts/_f6_p3a_sanction.json', encoding='utf-8'))
prot_b = json.load(open('scripts/_f6_p3b_sanction.json', encoding='utf-8'))
prot_v = json.load(open('scripts/_f6_p3v_sanction.json', encoding='utf-8'))
BC = prot['insert']['cat']; TIT = prot['title'][0]
def shift(c): return c + 1 if c >= BC else c
def old_of(i): return None if i == BC else (i if i < BC else i - 1)
N = len(cat)
sha = hashlib.sha256(open('state/catalog_final_v2.json', 'rb').read()).hexdigest()
print(f'=== РАЗМЕР === записей {N}; sha256 {sha[:16]}…; ключи {dict(Counter(k for r in cat for k in r))}')
assert N == 7174 == len(cat0) + 1 and BC == 1628
assert sorted(os.listdir('state')) == ['alignment_final.json', 'catalog_final_v2.json', 'index_master_final.json', 'index_master_v18r_реконструкция.md', 'Ф5_очередь_docx.json', 'Ф5_стабы_реестр.json', 'Ф6_страи_диспозиция.json'], 'в state/ ровно один каталог/alignment/мастер'
FIELDS = ['id', 'title', 'genre', 'year', 'studio', 'annotation', 'source']
assert all(list(r.keys()) == FIELDS for r in cat), 'схема'
assert [r['id'] for r in cat] == list(range(1, N + 1)), 'id 1..N'
assert all(isinstance(r['title'], str) and r['title'] and isinstance(r['year'], int) and isinstance(r['source'], str) for r in cat)
assert all(r['genre'] is None or (isinstance(r['genre'], str) and r['genre']) for r in cat) and all(r['studio'] is None or (isinstance(r['studio'], str) and r['studio']) for r in cat)
assert all(r['annotation'] is None or (isinstance(r['annotation'], str) and r['annotation'] == r['annotation'].strip() and r['annotation']) for r in cat)
print('=== СХЕМА === id 1..N сквозной, 7 полей, служебных ключей нет: OK')
print('=== ПО ТОМАМ ===', dict(Counter(r['source'] for r in cat)))
assert Counter(r['source'] for r in cat) == Counter(r['source'] for r in cat0) + Counter({'v2_1936-1957': 1})
assert set(r['source'] for r in cat) == {f'v{i}_' + s for i, s in zip(range(1, 16), ['1918-1935', '1936-1957', '1958-1963', '1964-1965', '1966-1967', '1968-1969', '1970-1971', '1972-1973', '1974-1975', '1976-1977', '1978-1979', '1980-1981', '1982-1983', '1984-1985', '1986-1987'])}
# alignment / мастер
cards = [r for r in m['rows'] if r['kind'] == 'card']
print(f"=== МАСТЕР === rows {len(m['rows'])}: {dict(Counter(r['kind'] for r in m['rows']))}; card cat_pos биекция: {sorted(r['cat_pos'] for r in cards) == list(range(N))}")
assert len(al) == N and all(a['cat_pos'] == i and a['id'] == i + 1 for i, a in enumerate(al)) and m['strays'] == []
for i, a in enumerate(al0):
    b = al[shift(i)]; ka = {k: v for k, v in a.items() if k not in ('cat_pos', 'id', 'master_title')}; kb = {k: v for k, v in b.items() if k not in ('cat_pos', 'id', 'master_title')}
    assert ka == kb and (a['master_title'] == b['master_title'] or i == 708), f'alignment {i} ≠ П3 (кроме сдвига/титула 708)'
assert al[BC]['xlsx_row'] == prot['insert']['xlsx_row'] and al[BC]['idx_num'] == '1628а' and al[BC]['master_title'] == 'Старый наездник' and al[708]['master_title'] == TIT['after']
rows_by = {r['xlsx_row']: r for r in m['rows']}
for r0 in m0['rows']:
    r = rows_by[r0['xlsx_row']]; drop = ('cat_pos', 'id') + (('title_canon', 'title_source', 'note', 'alt_titles') if r0['xlsx_row'] == 1088 else ())
    assert {k: v for k, v in r.items() if k not in drop} == {k: v for k, v in r0.items() if k not in drop}, f'мастер row {r0["xlsx_row"]} ≠ П3'
    if r0['kind'] == 'card': assert r['cat_pos'] == shift(r0['cat_pos'])
assert rows_by[1088]['title_canon'] == TIT['after'] and rows_by[prot['insert']['xlsx_row']]['title_canon'] == 'Старый наездник' and rows_by[prot['insert']['xlsx_row']]['num'] == '1628а'
assert len({a['xlsx_row'] for a in al}) == N and len({r['xlsx_row'] for r in m['rows']}) == len(m['rows']) == 7204
assert {r['cat_pos']: r['xlsx_row'] for r in cards} == {a['cat_pos']: a['xlsx_row'] for a in al}
assert all(r['vol'] == cat[r['cat_pos']]['source'] and r['id'] == cat[r['cat_pos']]['id'] for r in cards)
bycat = {r['cat_pos']: r for r in cards}
assert all(al[i]['master_title'] == bycat[i]['title_canon'] for i in range(N) if al[i]['master_title'] is not None), 'master_title ≠ title_canon'
assert m['_meta']['name'] == 'index_master_final' and m['_meta']['f6_p3a']['catalog'] == 'state/catalog_final_v2.json' and m['_meta']['stats']['карточных строк'] == N and '1628а' in m['_meta']['stats']['литерные номера']
print('=== СТРАИ === 0; alignment и строки мастера == П3 + сдвиг cat_pos/id ≥ 1628, новая строка «Старый наездник», row 1088 титул; alignment.master_title == title_canon: OK')
# пустые поля == реестр
none = {f: sorted(i for i, r in enumerate(cat) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
regn = {f: sorted(e['cat'] for e in reg['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
print('=== ПУСТЫЕ ПОЛЯ === каталог:', {f: len(v) for f, v in none.items()}, '; реестр none:', {f: len(v) for f, v in regn.items()}, '; совпадение позиций:', all(none[f] == regn[f] for f in regn))
assert all(none[f] == regn[f] for f in regn) and none['year'] == [] and len(none['annotation']) == 8
assert len(reg['entries']) == 111 and all(cat[e['cat']]['title'] == e['title'] and e['id'] == e['cat'] + 1 for e in reg['entries']), 'реестр: title/id ↔ cat'
assert reg['counts'] == dict(Counter(f"{e['field']}/{e['state']}" for e in reg['entries'])) and reg['catalog'] == 'state/catalog_final_v2.json'
assert reg['counts']['annotation/source-only'] == 33 and len(reg['closed_f6_p3']) == 7 and 'annotation/intro-only' not in reg['counts']
assert all(cat[e['cat']]['title'] == e['title'] for k in ('genre', 'studio_empty', 'annotation') for e in q[k]), 'очередь: title ↔ cat'
print('=== РЕЕСТР ===', reg['counts'], '; closed_f6_p3:', [e['cat'] for e in reg['closed_f6_p3']])
dups = [(k, c) for k, c in Counter((r['title'], r['year']) for r in cat).items() if c > 1]
print('=== ТОЧНЫЕ ДУБЛИ title+year ===', len(dups), [(t, y, [r['id'] for r in cat if (r['title'], r['year']) == (t, y)]) for (t, y), c in dups])
assert len(dups) == 3
dups3 = [(k, c) for k, c in Counter((r['title'], r['year'], r['studio']) for r in cat).items() if c > 1]
print('=== ДУБЛИ title+year+studio (ключ импорта П4) ===', len(dups3)); assert not dups3
# санкция
setpos = {(x['cat'], 'annotation') for x in prot['set']} | {(708, 'title')} | {(x['cat'], 'annotation') for x in prot_b['set']} | {(x['cat'], 'annotation') for x in prot_v['set']}
pb = {x['cat']: x for x in prot_b['set']}; pv = {x['cat']: x for x in prot_v['set']}
for x in prot['set']:
    assert (cat[x['cat']]['annotation'] == x['after'] or x['cat'] in pb or x['cat'] in pv) and cat0[x['cat_v1']]['annotation'] == x['before'] and shift(x['cat_v1']) == x['cat'] and x['id'] == x['cat'] + 1, f'санкция cat{x["cat"]}'
for x in prot_b['set']:
    assert (cat[x['cat']]['annotation'] == x['after'] or x['cat'] in pv) and (cat0[old_of(x['cat'])]['annotation'] == x['before'] or any(y['cat'] == x['cat'] and y['after'] == x['before'] for y in prot['set'])), f'санкция П3б cat{x["cat"]}'
for x in prot_v['set']:
    prev = pb[x['cat']]['after'] if x['cat'] in pb else next((y['after'] for y in prot['set'] if y['cat'] == x['cat']), None)
    if prev is None: prev = cat0[old_of(x['cat'])]['annotation']
    assert cat[x['cat']]['annotation'] == x['after'] and prev == x['before'] and x['before'].endswith(x['after']) if x['class'] != 'cred-inner' else (cat[x['cat']]['annotation'] == x['after'] and prev == x['before'] and len(x['after']) < len(x['before'])), f'санкция П3в cat{x["cat"]}'
assert len(prot_v['set']) == 123 and Counter(x['class'] for x in prot_v['set']) == {'cred-prefix': 110, 'cred-inner': 12, 'junk-prefix': 1} and prot_v['_meta']['result']['register_added_source_only'] == [5740]
assert len(prot_b['set']) == 4 and Counter(x['class'] for x in prot_b['set']) == {'gap-pre': 2, 'cred-cut': 2}
for x in prot['set']:
    assert x['class'] in ('gap-pre', 'gap-head', 'gap-post', 'gap-mid', 'gap-tailrepl', 'gap-almanac') and x['lines'] and x['raw']
assert cat[708]['title'] == TIT['after'] and cat0[708]['title'] == TIT['before']
ins = cat[BC]; assert ins['title'] == 'Старый наездник' and ins['year'] == 1940 and ins['studio'] == 'Мосфильм' and ins['genre'] == 'Комедия' and ins['source'] == 'v2_1936-1957' and ins['annotation'] == prot['insert']['record']['annotation']
assert cat[BC - 1]['title'] == 'Случай в вулкане' and cat[BC + 1]['title'] == 'Суворов'
cnt = 0
for i in range(N):
    j = old_of(i)
    if j is None: continue
    for k in ('title', 'genre', 'year', 'studio', 'annotation', 'source'):
        if (i, k) in setpos: continue
        assert cat0[j][k] == cat[i][k], f'вне санкции: cat{i}/{k}'; cnt += 1
seq0 = [(r['title'], r['year'], r['studio'], r['genre'], r['source']) for r in cat0]; seq0[708] = (TIT['after'],) + seq0[708][1:]; seq0.insert(BC, ('Старый наездник', 1940, 'Мосфильм', 'Комедия', 'v2_1936-1957'))
assert [(r['title'], r['year'], r['studio'], r['genre'], r['source']) for r in cat] == seq0, 'И5′'
print('=== САНКЦИЯ === П3а set', len(prot['set']), dict(Counter(x['class'] for x in prot['set'])), '; титул 1 (cat708); вставка 1 (cat1628 «Старый наездник»); П3б set 4 {gap-pre 2, cred-cut 2}; П3в set', len(prot_v['set']), dict(Counter(x['class'] for x in prot_v['set'])), '; прочих полей сверено байт-в-байт:', cnt, '; удалений 0')
# воспроизводимость классов
for x in prot['set']:
    b, a = x['before'], x['after']
    if x['class'] in ('gap-pre', 'gap-head'): assert a.endswith(' ' + b)
    elif x['class'] == 'gap-post': assert a.startswith(b + ' ')
    elif x['class'] == 'gap-mid': assert len(os.path.commonprefix([a, b])) > 0 and len(a) > len(b)
    elif x['class'] == 'gap-tailrepl': assert a.endswith('Фильм не сохранился.') and a.startswith(b[:-20].rstrip())
    else: assert len(a) > len(b)
print('=== ВОСПРОИЗВОДИМОСТЬ === pre/head: after = текст + before; post: before + текст; mid: вставка; tailrepl/almanac: расширение; П3в prefix: before = срез + after, inner: удаление внутри: OK')
# маркеры титров / библиографии
MARK = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Фильм озвучен|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер|гл\. опер|Реж\.-пост|Опер\.-пост)')
mk = [(i, MARK.search(r['annotation']).group()) for i, r in enumerate(cat) if r['annotation'] and MARK.search(r['annotation'])]
print('=== МАРКЕРЫ ТИТРОВ (жёсткие) в аннотациях ===', len(mk), mk); assert not mk
# призовые предложения в конце аннотации (наградная форма)
AW = re.compile(r'(удостоен|присужден|награжден[аы]? (медал|приз|диплом|преми)|Гран-при|Гпавн(ый|ая) (приз|преми)|Главн(ый|ая) (приз|преми)|Специальн(ый|ая) (приз|преми|диплом)|Почетн(ый|ая) (диплом|приз)|Сталинской премии|Ленинской премии|Государственн(ая|ой|ые) преми|Гэсударственн|звания лауреата|признан лучшим|назван лучшим|Назван лучшим|приз жюри|премия жюри|дипломов|«Ника-|премированн|назван одним из лучших)', re.I)
def last_sent(a):
    parts = re.split(r'(?<=[.!?…»)])\s+(?=[А-ЯЁ«(\d])', a); return parts[-1]
aw = [(i, last_sent(r['annotation'])[:80]) for i, r in enumerate(cat) if r['annotation'] and AW.search(last_sent(r['annotation'])) and re.search(r'(фестивал|конкурс|преми|приз|диплом|медал|Ника)', last_sent(r['annotation']), re.I)]
print('=== НАГРАДНЫЕ ПРЕДЛОЖЕНИЯ в конце аннотаций ===', len(aw), aw)
assert {i for i, _ in aw} <= {1182, 2392, 2400, 2423, 4722, 6034}, 'оставлены сознательно: cat1182 — историко-критическая справка (реестр note); cat2391/2399/2422 — примечание о премированном сценарии (проза-примечание, печать); cat4721/6033 — сюжет («главный приз» в фабуле)'
# остаточный OCR-мусор (как в П2е)
JUNK = re.compile(r'[\^■❖©®|\\@<>*•।_\[\]{}#$£™¡¿“”„"’‘`]')
jk = [(i, ''.join(sorted(set(JUNK.findall(r['annotation'])))) ) for i, r in enumerate(cat) if r['annotation'] and JUNK.search(r['annotation'])]
print('=== МУСОРНЫЕ СИМВОЛЫ в аннотациях ===', len(jk), jk[:20]); assert all(s == '’' for i, s in jk), jk
LAT = re.compile(r'(?<![A-Za-z])[A-Za-z]+(?![A-Za-z])'); ROMAN = re.compile(r'^[IVXLCM]+$')
lat = [(i, mm.group(0)) for i, r in enumerate(cat) if r['annotation'] for mm in LAT.finditer(r['annotation']) if not ROMAN.match(mm.group(0)) and mm.group(0) not in ('SOS', 'F', 'Jude')]
print('=== ЛАТИНИЦА в аннотациях (кроме римских цифр/SOS/Jude/F-9) ===', len(lat), lat); assert lat == [(2713, 'cho'), (3306, 'w')]
sig = [(i, r['annotation'][max(0, mm.start() - 20):mm.end() + 20]) for i, r in enumerate(cat) if r['annotation'] for mm in re.finditer(r'Зак[,.]\s?№|Сов\. худ\. фильмы|[А-ЯЁа-яё]+- \d{1,4}\*? [а-яё]|^.{0,60}(?<!\()ВЭ \d|^\S{0,4}\d{1,3}\.[IVX]+\.\s?\d{4}|Содержание I тома|Аннотированный каталог', r['annotation'])]
print('=== СИГНАТУРЫ/КОЛОНТИТУЛЫ/ВЭ/оглавление в аннотациях ===', len(sig), sig); assert not sig
hy = [(i, r['annotation'][max(0, mm.start() - 15):mm.end() + 15]) for i, r in enumerate(cat) if r['annotation'] for mm in re.finditer(r'[А-ЯЁа-яё]- [а-яё]', r['annotation'])]
print('=== ОСТАТОЧНЫЕ ПЕРЕНОСЫ «w1- w2» ===', len(hy), hy); assert [i for i, _ in hy] == [6482]   # cat6437 «кино- и телефильмы» ушёл со срезом призового блока
ws = [i for i, r in enumerate(cat) if r['annotation'] and ('  ' in r['annotation'] or '\t' in r['annotation'])]
print('=== ДВОЙНЫЕ ПРОБЕЛЫ/ТАБЫ ===', len(ws)); assert not ws
nl = [i for i, r in enumerate(cat) if r['annotation'] and '\n' in r['annotation']]
print('=== ПЕРЕВОДЫ СТРОК (многоновелльные) === cat', nl, '= id', [i + 1 for i in nl]); assert nl == [3639, 4219, 4751, 4824]
pg = [(i, r['annotation'][-30:]) for i, r in enumerate(cat) if r['annotation'] and re.search(r'\s\d{1,4}$', r['annotation'])]
print('=== ЦИФРЫ В КОНЦЕ АННОТАЦИИ (номера страниц/сигнатуры) ===', len(pg), pg)
assert [i for i, a in pg] == [249], pg   # cat249 «См. № 168» — печатная отсылка (реестр formula)
def nm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))
diff = [(i, cat[i]['title'], bycat[i]['title_canon']) for i in range(N) if nm(re.sub(r'\s*\(«.*$', '', cat[i]['title'])) != nm(bycat[i]['title_canon']) and nm(cat[i]['title']) != nm(bycat[i]['title_canon'])]
print('=== ТИТУЛ ↔ title_canon мастера (норм.) === расхождений:', len(diff), diff)
assert diff == [(2683, 'Загадка Н. Ф. И. и другие устные рассказы Ираклия Андроникова', 'Загадка Н. Ф. И.')]
yc = Counter(r['year'] for r in cat)
print('=== ГОДЫ === по десятилетиям:', {d: sum(c for y, c in yc.items() if y // 10 * 10 == d) for d in sorted({y // 10 * 10 for y in yc})}, '; min/max:', min(yc), max(yc))
short = [i for i, r in enumerate(cat) if r['annotation'] is not None and len(r['annotation']) < 100]
print('=== АННОТАЦИИ < 100 зн. (не None) ===', len(short))
nofin = [i for i, r in enumerate(cat) if r['annotation'] and not re.search(r'[.!?…»)"\']$', r['annotation'])]
print('=== АННОТАЦИИ без конечной пунктуации ===', len(nofin), '(печать тоже без знака — оставлены)')
assert len(nofin) <= 131
print('=== УНИКАЛЬНЫХ === genre:', len({r['genre'] for r in cat if r['genre']}), '; studio:', len({r['studio'] for r in cat if r['studio']}))
print('OK: финальная приёмка Ф6 (каталог v2 после П3а+П3б+П3в) пройдена')
