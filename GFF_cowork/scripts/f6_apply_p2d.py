# -*- coding: utf-8 -*-
"""Ф6-П2д механическая чистка OCR-мусора в аннотациях — apply, режим Cowork. Запуск из КОРНЯ: python3 scripts/f6_apply_p2d.py [--dry]
Вход: state/catalog_f6_p2.json (7173), state/alignment_f6_p2.json, state/index_master_f6_p2.json,
      state/Ф5_стабы_реестр.json, state/Ф5_очередь_docx.json, scripts/f6_p2d_resolution.json.
Действия: set ТОЛЬКО поля annotation (без удалений, без правок титулов/годов/студий); alignment и мастер — без содержательных изменений
(переименование состояния p2 → p2d, отметка в _meta мастера); реестр: +cat2958 annotation/source-only.
Порядок: пред-ассерты → apply в памяти → И1′–И6 → бэкапы → запись → протокол scripts/_f6_p2d_sanction.json."""
import json, copy, os, re, shutil, sys, datetime
from collections import Counter

DRY = '--dry' in sys.argv
SRC_CAT, SRC_AL, SRC_M = 'state/catalog_f6_p2.json', 'state/alignment_f6_p2.json', 'state/index_master_f6_p2.json'
SRC_REG, SRC_Q = 'state/Ф5_стабы_реестр.json', 'state/Ф5_очередь_docx.json'
OUT_CAT, OUT_AL, OUT_M = 'state/catalog_f6_p2d.json', 'state/alignment_f6_p2d.json', 'state/index_master_f6_p2d.json'
MARKERS = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиография|БИБЛИОГРАФИЯ|дир\. картины|худ\.-пост|Роли дублируют|Роли озвучива|Фильм дублирован)')
JUNK = re.compile(r'[\^■❖©®|\\@<>*•।_\[\]{}#$£™¡¿“”„"]')
N = 7173

res = json.load(open('scripts/f6_p2d_resolution.json', encoding='utf-8'))
cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
al0 = json.load(open(SRC_AL, encoding='utf-8'))
m0 = json.load(open(SRC_M, encoding='utf-8'))
reg0 = json.load(open(SRC_REG, encoding='utf-8'))
q0 = json.load(open(SRC_Q, encoding='utf-8'))

# ── Пред-ассерты §0 (состояние после П2) ──
assert len(cat0) == N, f'И1(вход): {len(cat0)}'
assert len(al0) == N and all(a['cat_pos'] == i for i, a in enumerate(al0)) and all(a['xlsx_row'] is not None for a in al0), 'alignment'
rows0 = m0['rows']; kinds0 = Counter(r['kind'] for r in rows0)
assert len(rows0) == 7203 and kinds0 == {'card': 7173, 'crossref': 22, 'unbound': 8} and m0['strays'] == [], f'мастер: {kinds0}'
assert sorted(r['cat_pos'] for r in rows0 if r['kind'] == 'card') == list(range(N)) and len({r['xlsx_row'] for r in rows0}) == 7203
assert len(reg0['entries']) == 110 and reg0['counts']['annotation/none'] == 8 and reg0['counts']['annotation/source-only'] == 25 and len(reg0['closed_f6_p2']) == 5
none0 = {f: sorted(i for i, r in enumerate(cat0) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
assert (len(none0['genre']), len(none0['studio']), len(none0['annotation']), len(none0['year'])) == (12, 1, 8, 0)
assert not [e for e in reg0['entries'] if e['cat'] == 2958]

# ── Пред-ассерты резолюции ──
SET = res['set']; seen = set()
def letters(s): return re.sub(r'[^А-ЯЁа-яё]', '', s)
CLS = set(res['_meta']['classes'])
SAFE = {'B', 'WS', 'C■', 'C•', 'C’', 'C*', 'C^', 'C|', 'C<', 'C>', 'C"', "C'", 'C„', 'C×', 'C.'}
for x in SET:
    c, f, cls, b, a = x['cat'], x['field'], x['class'], x['before'], x['after']
    assert (c, f) not in seen, f'дубль (cat{c},{f})'; seen.add((c, f))
    assert f == 'annotation', f'cat{c}: поле {f}'
    assert 0 <= c < N and cat0[c]['title'] == x['title'] and cat0[c]['source'] == x['source'], f'cat{c}: title/source'
    assert cat0[c]['annotation'] == b, f'cat{c}: before не совпал байт-в-байт'
    assert isinstance(a, str) and a and a != b and a == a.strip() and '  ' not in a and '\t' not in a and not re.search(r'\n\s|\s\n', a), f'cat{c}: after'
    assert cls.startswith('ocr:') and set(cls[4:].split('+')) <= CLS, f'cat{c}: класс {cls}'
    assert x.get('vol') == x['source'].split('_')[0] and isinstance(x.get('lines'), list) and x.get('note') and x.get('ops'), f'cat{c}: vol/lines/note/ops'
    assert not MARKERS.search(a), f'cat{c}: маркер титров в after: {MARKERS.search(a).group()}'
    assert not JUNK.search(a), f'cat{c}: мусорный символ в after: {JUNK.search(a).group()}'
    parts = set(cls[4:].split('+')); manualB = any(o[0] == 'B' and len(o) > 3 and o[3] == 'вручную' for o in x['ops'])
    if parts <= SAFE and not manualB: assert letters(a) == letters(b), f'cat{c}: буквы изменены безопасными классами'
    assert len(a) >= 40, f'cat{c}: after короче 40 зн.'
    if not parts & {'T', 'BIB', 'L'}: assert len(a) >= 0.5 * len(b), f'cat{c}: after < 50% before без T/BIB/L'
    assert ('\n' in a) == ('\n' in b or c == 4218), f'cat{c}: перевод строки'
REG_ADD = res['register']['add']; assert len(REG_ADD) == 1 and REG_ADD[0]['cat'] == 2958 and REG_ADD[0]['state'] == 'source-only'
x2958 = [x for x in SET if x['cat'] == 2958][0]; assert x2958['after'] == 'По мотивам повести Н. В. Гоголя «Ночь перед Рождеством».'

# ── Apply в памяти: каталог ──
snap = [dict(r) for r in cat0]
cat1 = copy.deepcopy(cat0)
for x in SET: cat1[x['cat']]['annotation'] = x['after']
exp_set = {(x['cat'], 'annotation') for x in SET}

# ── Инварианты И1′–И5′ ──
assert len(cat1) == N, 'И1′'
changed = {(i, k) for i in range(N) for k in set(cat1[i]) | set(snap[i]) if cat1[i].get(k) != snap[i].get(k)}
assert changed == exp_set, f'И2: {changed ^ exp_set}'
for i in range(N):
    for k in set(snap[i]) | set(cat1[i]):
        assert (k in snap[i]) == (k in cat1[i]), f'И3 ключ cat{i}/{k}'
        if (i, k) not in changed: assert snap[i].get(k) == cat1[i].get(k), f'И3 cat{i}/{k}'
assert Counter(r['source'] for r in cat1) == Counter(r['source'] for r in cat0), 'И4'
assert [(r['title'], r['year'], r['studio'], r['genre'], r['source']) for r in cat1] == [(r['title'], r['year'], r['studio'], r['genre'], r['source']) for r in cat0], 'И5′ (титулы/годы/студии/жанры неизменны)'
assert sorted(i for i, r in enumerate(cat1) if r['annotation'] is None) == none0['annotation'], 'annotation/none неизменны'

# ── Alignment / мастер: без содержательных изменений ──
al1 = copy.deepcopy(al0)
m1 = copy.deepcopy(m0)
m1['_meta'].update({'name': 'index_master_f6_p2d', 'derived_from': 'index_master_f6_p2.json',
                    'f6_p2d': {'date': datetime.date.today().isoformat(), 'catalog': OUT_CAT, 'alignment': OUT_AL,
                               'change': 'нет (П2д правил только annotation каталога); файл переименован для единственности состояния',
                               'resolution': 'scripts/f6_p2d_resolution.json', 'sanction': 'scripts/_f6_p2d_sanction.json'}})
# ── И6: биекция (неизменна) ──
assert al1 == al0 and m1['rows'] == m0['rows'] and m1['strays'] == []
rows1 = m1['rows']; cards = [r for r in rows1 if r['kind'] == 'card']
bycat1 = {r['cat_pos']: r for r in cards}
assert all(al1[i]['master_title'] == bycat1[i]['title_canon'] for i in range(N) if al1[i]['master_title'] is not None), 'master_title ≠ title_canon'
assert all(r['vol'] == cat1[r['cat_pos']]['source'] for r in cards) and all(al1[i]['source'] == cat1[i]['source'] for i in range(N))

# ── Реестр и очередь ──
reg1 = copy.deepcopy(reg0)
reg1['entries'].append({'cat': 2958, 'title': cat1[2958]['title'], 'source': cat1[2958]['source'], 'field': 'annotation', 'state': 'source-only',
                        'reason': REG_ADD[0]['reason'], 'evidence': {'lines_v3': [4052]}, 'origin': 'Ф6-П2д', 'cat_f5': al0[2958]['cat_pos_f5']})
reg1['entries'].sort(key=lambda e: (e['field'], e['cat']))
reg1['counts'] = dict(Counter(f"{e['field']}/{e['state']}" for e in reg1['entries']))
reg1['catalog'] = OUT_CAT; reg1['package'] = reg0['package'] + ' → Ф6-П2д'
reg1['note'] = reg0['note'] + ' Ф6-П2д: +cat2958 annotation/source-only (библиография снята, осталась формула источника).'
none1 = {f: sorted(i for i, r in enumerate(cat1) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
regn = {f: sorted(e['cat'] for e in reg1['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
assert regn == {f: none1[f] for f in regn} and none1['year'] == [], 'реестр none ≠ каталог'
assert (reg1['counts']['genre/none'], reg1['counts']['studio/none'], reg1['counts']['annotation/none'], reg1['counts']['annotation/source-only']) == (12, 1, 8, 26)
assert len(reg1['entries']) == 111 and all(cat1[e['cat']]['title'] == e['title'] for e in reg1['entries']), 'реестр'
q1 = copy.deepcopy(q0)
assert all(cat1[e['cat']]['title'] == e['title'] for k in ('genre', 'studio_empty', 'annotation') for e in q1[k]), 'очередь: title ↔ cat'

# ── Протокол ──
ops_cnt = dict(Counter(o[0] for x in SET for o in x['ops']))
prot = {'_meta': {**res['_meta'], 'applied': datetime.datetime.now().isoformat(timespec='minutes'),
                  'result': {'catalog': N, 'alignment': len(al1), 'master_rows': len(rows1), 'master_card': len(cards), 'strays': 0, 'deleted': 0,
                             'set': len(SET), 'set_field': 'annotation', 'ops_by_class': ops_cnt,
                             'register': {'added': [2958], 'closed': [], 'counts': reg1['counts']}}},
        'set': SET, 'register': res['register']}
if DRY:
    print('DRY OK: И1′–И6 пройдены;', json.dumps(prot['_meta']['result'], ensure_ascii=False)); sys.exit(0)

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
for src, tag in ((SRC_CAT, 'catalog_f6_p2'), (SRC_AL, 'alignment_f6_p2'), (SRC_M, 'index_master_f6_p2'), (SRC_REG, 'Ф5_стабы_реестр'), (SRC_Q, 'Ф5_очередь_docx')):
    shutil.copy2(src, f'backups/{tag}_{ts}.json')
def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
dump(cat1, OUT_CAT); dump(al1, OUT_AL); dump(m1, OUT_M); dump(reg1, SRC_REG); dump(q1, SRC_Q)
dump(prot, 'scripts/_f6_p2d_sanction.json')
for src, name in ((SRC_CAT, 'catalog_f6_p2.json'), (SRC_AL, 'alignment_f6_p2.json'), (SRC_M, 'index_master_f6_p2.json')):
    os.replace(src, f'backups/{name}')
print(f'OK Ф6-П2д: set {len(SET)} (annotation) ops {ops_cnt}; каталог {N}; alignment {len(al1)}; мастер rows {len(rows1)} (card {len(cards)}); '
      f'страёв 0; реестр {len(reg1["entries"])} ({reg1["counts"]}); И1′–И6 пройдены.')
