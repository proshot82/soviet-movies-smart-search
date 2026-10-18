# -*- coding: utf-8 -*-
"""Ф6-П1 страи — apply, режим Cowork. Запуск из КОРНЯ: python3 scripts/f6_apply_p1.py [--dry]
Вход: state/catalog_f5.json (7232), state/alignment_v17.json, state/index_master_v18r.json,
      state/Ф5_стабы_реестр.json, state/Ф5_очередь_docx.json, scripts/f6_p1_resolution.json,
      state/Ф6_страи_диспозиция.json.
Действия: set (restore/append/studio) у 14 целей + cat1197; delete 59 страёв; перенумерация cat;
alignment/мастер синхронно (cat1197 → строка мастера 2106 «1184а»); реестр/очередь перенумерованы.
Порядок: пред-ассерты → apply в памяти → И1′–И6 → бэкапы → запись → протокол scripts/_f6_p1_sanction.json."""
import json, copy, os, re, shutil, sys, datetime
from collections import Counter

DRY = '--dry' in sys.argv
SRC_CAT, SRC_AL, SRC_M = 'state/catalog_f5.json', 'state/alignment_v17.json', 'state/index_master_v18r.json'
SRC_REG, SRC_Q, SRC_D = 'state/Ф5_стабы_реестр.json', 'state/Ф5_очередь_docx.json', 'state/Ф6_страи_диспозиция.json'
OUT_CAT, OUT_AL, OUT_M = 'state/catalog_f6_p1.json', 'state/alignment_f6_p1.json', 'state/index_master_f6_p1.json'
MARKERS = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиография|БИБЛИОГРАФИЯ|дир\. картины|худ\.-пост)')
FIELDS = ('title', 'genre', 'year', 'studio', 'annotation', 'source')

res = json.load(open('scripts/f6_p1_resolution.json', encoding='utf-8'))
cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
al0 = json.load(open(SRC_AL, encoding='utf-8'))
m0 = json.load(open(SRC_M, encoding='utf-8'))
reg0 = json.load(open(SRC_REG, encoding='utf-8'))
q0 = json.load(open(SRC_Q, encoding='utf-8'))
disp = json.load(open(SRC_D, encoding='utf-8'))

# ── Пред-ассерты §0 ──
N0 = 7232
assert len(cat0) == N0, f'И1(вход): {len(cat0)}'
assert sum('_merged' in r for r in cat0) == 6834 and sum('_f4_recovered' in r for r in cat0) == 398, 'служебные ключи Ф4'
assert len(al0) == N0 and all(a['cat_pos'] == i for i, a in enumerate(al0)), 'alignment'
strays = {a['cat_pos'] for a in al0 if a['xlsx_row'] is None}
assert len(strays) == 60, 'страёв 60'
rows0 = m0['rows']
kinds0 = Counter(r['kind'] for r in rows0)
assert len(rows0) == 7203 and kinds0 == {'card': 7172, 'crossref': 22, 'unbound': 9}, f'мастер: {kinds0}'
assert len(m0['strays']) == 60 and {s['cat_pos'] for s in m0['strays']} == strays, 'мастер strays'
assert {r['cat_pos'] for r in rows0 if r['kind'] == 'card'} == set(range(N0)) - strays, 'мастер card ↔ не-страи'
assert len({r['xlsx_row'] for r in rows0}) == 7203, 'xlsx_row уникальны'
row2106 = [r for r in rows0 if r['xlsx_row'] == 2106]
assert len(row2106) == 1 and row2106[0]['kind'] == 'unbound' and row2106[0]['xlsx_num'] == '1184а', 'row 2106'
DELSET = set(disp['actions']['delete'])
assert len(DELSET) == 59 and DELSET == strays - {1197}, 'диспозиция delete'
assert {x['cat'] for x in res['delete']} == DELSET, 'резолюция delete == диспозиция'
assert len(reg0['entries']) == 114 and not ({e['cat'] for e in reg0['entries']} & strays), 'реестр'
assert len(q0['year_empty']) == 32 and {e['cat'] for e in q0['year_empty']} <= strays, 'очередь year_empty'
assert {e['cat'] for e in q0['annotation']} == {489, 1185, 3876, 3877}, 'очередь annotation'
assert [e['cat'] for e in q0['genre']] == [8, 213, 500, 1024, 2848, 3554, 3876, 3877, 3878, 3915, 4277, 6963]
assert [e['cat'] for e in q0['studio_empty']] == [3064]

# ── Пред-ассерты резолюции ──
SET = res['set']
seen = set()
for x in SET:
    c, f, cls, b, a = x['cat'], x['field'], x['class'], x['before'], x['after']
    assert (c, f) not in seen, f'дубль (cat{c},{f})'; seen.add((c, f))
    assert f in ('annotation', 'studio') and cls in ('restore', 'append', 'studio'), f'cat{c}: {f}/{cls}'
    assert c not in DELSET, f'cat{c}: правка удаляемого страя'
    assert c == 1197 or c not in strays, f'cat{c}: страй вне диспозиции keep'
    assert cat0[c].get(f) == b, f'cat{c}/{f}: before не совпал байт-в-байт'
    assert cat0[c]['title'] == x['title'] and cat0[c]['source'] == x['source'], f'cat{c}: title/source'
    assert isinstance(a, str) and a and a == a.strip() and '  ' not in a and '\n' not in a and '\t' not in a, f'cat{c}/{f}: after'
    assert a != b, f'cat{c}/{f}: after == before'
    assert x.get('vol') and x.get('lines'), f'cat{c}/{f}: нет vol/@строк'
    assert x.get('note') is not None
    if cls == 'restore':
        assert f == 'annotation' and not MARKERS.search(a), f'cat{c}: маркер титров: {MARKERS.search(a)}'
        assert len(a) > len(b) or c == 1197, f'cat{c}: restore короче before'  # cat1197: срез библиографии
        tgt = disp['actions']['restore'].get(str(c)) or (disp['actions']['keep']['1197']['fields']['annotation'] if c == 1197 else None)
        assert tgt and tgt['after'] == a, f'cat{c}: after != диспозиция'
    elif cls == 'append':
        assert f == 'annotation' and a.startswith(b) and not MARKERS.search(a[len(b):]), f'cat{c}: append'
        assert disp['actions']['append'][str(c)]['after'] == a, f'cat{c}: after != диспозиция'
    elif cls == 'studio':
        assert f == 'studio' and c == 1197 and b.startswith(a) and a == disp['actions']['keep']['1197']['fields']['studio']['after']
exp_set = {(int(c), 'annotation') for c in disp['actions']['restore']} | {(int(c), 'annotation') for c in disp['actions']['append']} | {(1197, 'annotation'), (1197, 'studio')}
assert {(x['cat'], x['field']) for x in SET} == exp_set, 'состав set != диспозиция'
assert len(SET) == 16

# ── Apply в памяти ──
snap = [dict(r) for r in cat0]
cat_set = copy.deepcopy(cat0)
for x in SET:
    cat_set[x['cat']][x['field']] = x['after']
keep_old = [i for i in range(N0) if i not in DELSET]
new_of = {old: new for new, old in enumerate(keep_old)}      # карта перенумерации
cat1 = [cat_set[i] for i in keep_old]
N1 = len(cat1)

# ── Инварианты И1′–И5′ ──
assert N1 == N0 - 59 == 7173, f'И1′: {N1}'
changed = {(old, k) for old in keep_old for k in set(cat_set[old]) | set(snap[old]) if cat_set[old].get(k) != snap[old].get(k)}
assert changed == exp_set, f'И2: {changed ^ exp_set}'
for x in SET:
    assert cat1[new_of[x['cat']]][x['field']] == x['after'], f'И2 значение cat{x["cat"]}'
for old in keep_old:
    for k in set(snap[old]) | set(cat1[new_of[old]]):
        if (old, k) not in changed:
            assert snap[old].get(k) == cat1[new_of[old]].get(k), f'И3 cat{old}/{k}'
            assert (k in snap[old]) == (k in cat1[new_of[old]]), f'И3 ключ cat{old}/{k}'
src0, src1 = Counter(r['source'] for r in cat0), Counter(r['source'] for r in cat1)
delsrc = Counter(cat0[c]['source'] for c in DELSET)
assert src1 == Counter({s: n - delsrc[s] for s, n in src0.items()}), 'И4'
assert [(r['title'], r['source']) for r in cat1] == [(cat0[i]['title'], cat0[i]['source']) for i in keep_old], 'И5′'

# ── Alignment ──
al1 = []
for old in keep_old:
    a = dict(al0[old]); a['cat_pos'] = new_of[old]; a['cat_pos_f5'] = old
    if old == 1197:
        assert a['xlsx_row'] is None and a['cat_title'] == 'Рядом с нами'
        a.update({'xlsx_row': 2106, 'idx_num': '1184а', 'method': 'manual', 'confidence': 'high',
                  'second_signal': 'печатная голова v2 @124 «1184 а. РЯДОМ С НАМИ…» — литерный № между №1184 (Путевка в жизнь) и №1185 (Снайпер)',
                  'note': 'Ф6-П1 (E_legit_no_master): склейка xlsx row 2106 «Рядовой Александр Матросов 1888 Рядом с нами» разделена — №1888 → row 7182/cat1901 (Ф5-нумерация); хвост «Рядом с нами» №1184а → эта запись',
                  'master_title': 'Рядом с нами'})
    al1.append(a)

# ── Мастер ──
m1 = copy.deepcopy(m0)
for r in m1['rows']:
    if r['kind'] == 'card':
        r['cat_pos_f5'] = r['cat_pos']; r['cat_pos'] = new_of[r['cat_pos']]
    elif r['xlsx_row'] == 2106:
        mr = res['master']['1197']
        assert mr['xlsx_row'] == 2106
        r.update({'kind': 'card', 'num': mr['num'], 'title_canon': mr['title_canon'], 'title_source': mr['title_source'],
                  'cat_pos': new_of[1197], 'cat_pos_f5': 1197, 'note': mr['note'], 'provenance': mr['provenance']})
m1['strays'] = []
lit = m1['_meta']['stats'].get('литерные номера', [])
st = m1['_meta']['stats']
st.update({'карточных строк': 7173, 'некарточных строк xlsx': 30, 'страёв каталога': 0,
           'литерные номера': sorted(set(lit) | {'1184а'})})
st['по томам'] = dict(Counter(r['vol'] for r in m1['rows'] if r['kind'] == 'card'))
m1['_meta'].update({'name': 'index_master_f6_p1', 'derived_from': 'index_master_v18r.json',
                    'f6_p1': {'date': datetime.date.today().isoformat(), 'catalog': OUT_CAT, 'alignment': OUT_AL,
                              'change': '59 страёв удалены (их cat_pos выбыли, card-строки перенумерованы: cat_pos_f5 → cat_pos); '
                                        'row 2106 (unbound, склейка) → card «Рядом с нами» №1184а (cat1197 Ф5); страёв 0',
                              'resolution': 'scripts/f6_p1_resolution.json', 'sanction': 'scripts/_f6_p1_sanction.json'}})

# ── И6: биекция каталог ↔ alignment ↔ card-строки мастера ──
assert len(al1) == N1 and all(a['cat_pos'] == i for i, a in enumerate(al1)), 'И6 alignment cat_pos'
assert all(a['xlsx_row'] is not None for a in al1), 'И6 страи в alignment'
xr_al = [a['xlsx_row'] for a in al1]
assert len(set(xr_al)) == N1, 'И6 xlsx_row alignment уникальны'
assert all(al1[i]['source'] == cat1[i]['source'] for i in range(N1)), 'И6 alignment ↔ каталог (source)'  # cat_title в alignment — титул эпохи Ф3, не инвариант
rows1 = m1['rows']
cards = [r for r in rows1 if r['kind'] == 'card']
assert len(rows1) == 7203 and len(cards) == 7173 and Counter(r['kind'] for r in rows1) == {'card': 7173, 'crossref': 22, 'unbound': 8}, 'И6 мастер'
assert sorted(r['cat_pos'] for r in cards) == list(range(N1)), 'И6 card cat_pos биекция'
assert len({r['xlsx_row'] for r in rows1}) == 7203, 'И6 xlsx_row мастера уникальны'
mx = {r['cat_pos']: r['xlsx_row'] for r in cards}
assert all(mx[a['cat_pos']] == a['xlsx_row'] for a in al1), 'И6 alignment.xlsx_row == мастер'
assert not [k for k, v in Counter((r['vol'], str(r['num'])) for r in cards).items() if v > 1], 'И6 (vol,num) уникальны'
assert all(r['vol'] == cat1[r['cat_pos']]['source'] for r in cards), 'И6 vol == source'
assert m1['strays'] == []
# И3 для alignment/мастера: прочие поля неизменны
for a in al1:
    o = al0[a['cat_pos_f5']]
    if a['cat_pos_f5'] != 1197:
        assert {k: v for k, v in a.items() if k not in ('cat_pos', 'cat_pos_f5')} == {k: v for k, v in o.items() if k != 'cat_pos'}, f'И3 alignment {a["cat_pos_f5"]}'
r0 = {r['xlsx_row']: r for r in rows0}
for r in rows1:
    o = r0[r['xlsx_row']]
    if r['xlsx_row'] == 2106: continue
    assert {k: v for k, v in r.items() if k not in ('cat_pos', 'cat_pos_f5')} == {k: v for k, v in o.items() if k != 'cat_pos'}, f'И3 мастер row {r["xlsx_row"]}'

# ── Реестр и очередь: перенумерация ──
reg1 = copy.deepcopy(reg0)
for e in reg1['entries']:
    e['cat_f5'] = e['cat']; e['cat'] = new_of[e['cat']]
reg1['catalog'] = OUT_CAT
reg1['renumbered'] = 'Ф6-П1: cat — по каталогу Ф6 (после удаления 59 страёв); cat_f5 — прежний индекс Ф5; номера cat в свободном тексте reason/note — нумерация Ф5'
q1 = copy.deepcopy(q0)
q1['year_empty'] = []
q1['annotation'] = [e for e in q0['annotation'] if not e.get('stray')]
assert [e['cat'] for e in q1['annotation']] == [3876, 3877]
for k in ('genre', 'studio_empty', 'annotation'):
    for e in q1[k]:
        e['cat_f5'] = e['cat']; e['cat'] = new_of[e['cat']]
q1 = {'_meta': {'renumbered': 'Ф6-П1: cat — по каталогу Ф6 (state/catalog_f6_p1.json); cat_f5 — индекс Ф5. year_empty (32 страя) и annotation 489/1185 (страи) закрыты удалением страёв; остались терминалы',
                'terminals': {'genre': len(q1['genre']), 'studio_empty': len(q1['studio_empty']), 'annotation': len(q1['annotation'])}}, **q1}
# реестр: счётчики пустых полей каталога должны совпасть с реестром
none_cnt = {f: [i for i, r in enumerate(cat1) if r[f] is None] for f in ('genre', 'studio', 'annotation', 'year')}
assert len(none_cnt['genre']) == reg1['counts']['genre/none'] == 12
assert len(none_cnt['studio']) == reg1['counts']['studio/none'] == 1
assert len(none_cnt['annotation']) == reg1['counts']['annotation/none'] == 7
assert none_cnt['year'] == []
reg_none = {f: sorted(e['cat'] for e in reg1['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
assert reg_none == {f: none_cnt[f] for f in reg_none}, f'реестр none ≠ каталог: {reg_none} vs {none_cnt}'

# ── Протокол ──
prot = {'_meta': {**res['_meta'], 'applied': datetime.datetime.now().isoformat(timespec='minutes'),
                  'result': {'catalog': N1, 'alignment': len(al1), 'master_rows': len(rows1), 'master_card': len(cards),
                             'master_noncard': len(rows1) - len(cards), 'strays': 0, 'deleted': len(DELSET), 'set': len(SET)}},
        'set': [{**x, 'cat_new': new_of[x['cat']]} for x in SET],
        'delete': [{**x, 'record': {f: cat0[x['cat']].get(f) for f in FIELDS},
                    'target_new': (new_of[x['target']] if x['target'] is not None else None)} for x in res['delete']],
        'master': {'row_2106': [r for r in rows1 if r['xlsx_row'] == 2106][0], 'alignment_1197': al1[new_of[1197]]},
        'renumbering': {str(old): new for old, new in new_of.items() if old != new}}

if DRY:
    print('DRY OK: И1′–И6 пройдены;', prot['_meta']['result']); sys.exit(0)

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
for src, tag in ((SRC_CAT, 'catalog_f5'), (SRC_AL, 'alignment_v17'), (SRC_M, 'index_master_v18r'),
                 (SRC_REG, 'Ф5_стабы_реестр'), (SRC_Q, 'Ф5_очередь_docx')):
    shutil.copy2(src, f'backups/{tag}_{ts}.json')

def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
dump(cat1, OUT_CAT); dump(al1, OUT_AL); dump(m1, OUT_M); dump(reg1, SRC_REG); dump(q1, SRC_Q)
dump(prot, 'scripts/_f6_p1_sanction.json')
for src, name in ((SRC_CAT, 'catalog_f5.json'), (SRC_AL, 'alignment_v17.json'), (SRC_M, 'index_master_v18r.json')):
    os.replace(src, f'backups/{name}')
print(f'OK Ф6-П1: set {len(SET)} {dict(Counter((x["field"], x["class"]) for x in SET))}; delete {len(DELSET)}; '
      f'каталог {N1}; alignment {len(al1)}; мастер rows {len(rows1)} (card {len(cards)}, noncard {len(rows1)-len(cards)}); страёв 0; И1′–И6 пройдены.')
