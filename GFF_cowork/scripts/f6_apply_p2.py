# -*- coding: utf-8 -*-
"""Ф6-П2 точечные дефекты — apply, режим Cowork. Запуск из КОРНЯ: python3 scripts/f6_apply_p2.py [--dry]
Вход: state/catalog_f6_p1.json (7173), state/alignment_f6_p1.json, state/index_master_f6_p1.json,
      state/Ф5_стабы_реестр.json, state/Ф5_очередь_docx.json, scripts/f6_p2_resolution.json.
Действия: set по полям (annotation: lead/tail/prefix/restore/mid/none; year; studio; title) — без удалений;
титулы синхронно в alignment.master_title и мастер.title_canon (+ 80 master-only исправлений title_canon);
перепривязка cat6812 ↔ cat6813 (row 6648 ↔ row 7200); реестр: +cat4275 annotation/none, закрыты 4 title/defect и 1 suspect.
Порядок: пред-ассерты → apply в памяти → И1′–И6 → бэкапы → запись → протокол scripts/_f6_p2_sanction.json."""
import json, copy, os, re, shutil, sys, datetime
from collections import Counter

DRY = '--dry' in sys.argv
SRC_CAT, SRC_AL, SRC_M = 'state/catalog_f6_p1.json', 'state/alignment_f6_p1.json', 'state/index_master_f6_p1.json'
SRC_REG, SRC_Q = 'state/Ф5_стабы_реестр.json', 'state/Ф5_очередь_docx.json'
OUT_CAT, OUT_AL, OUT_M = 'state/catalog_f6_p2.json', 'state/alignment_f6_p2.json', 'state/index_master_f6_p2.json'
MARKERS = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиография|БИБЛИОГРАФИЯ|дир\. картины|худ\.-пост|Роли дублируют|Роли озвучива|Фильм дублирован)')
FIELDS = ('title', 'genre', 'year', 'studio', 'annotation', 'source')
N = 7173

res = json.load(open('scripts/f6_p2_resolution.json', encoding='utf-8'))
cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
al0 = json.load(open(SRC_AL, encoding='utf-8'))
m0 = json.load(open(SRC_M, encoding='utf-8'))
reg0 = json.load(open(SRC_REG, encoding='utf-8'))
q0 = json.load(open(SRC_Q, encoding='utf-8'))

# ── Пред-ассерты §0 (состояние после П1) ──
assert len(cat0) == N, f'И1(вход): {len(cat0)}'
assert len(al0) == N and all(a['cat_pos'] == i for i, a in enumerate(al0)) and all(a['xlsx_row'] is not None for a in al0), 'alignment'
rows0 = m0['rows']; kinds0 = Counter(r['kind'] for r in rows0)
assert len(rows0) == 7203 and kinds0 == {'card': 7173, 'crossref': 22, 'unbound': 8} and m0['strays'] == [], f'мастер: {kinds0}'
assert sorted(r['cat_pos'] for r in rows0 if r['kind'] == 'card') == list(range(N)) and len({r['xlsx_row'] for r in rows0}) == 7203
assert len(reg0['entries']) == 114 and reg0['counts']['annotation/none'] == 7 and reg0['counts']['title/defect'] == 4 and reg0['counts']['annotation/suspect'] == 1
none0 = {f: sorted(i for i, r in enumerate(cat0) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
assert (len(none0['genre']), len(none0['studio']), len(none0['annotation']), len(none0['year'])) == (12, 1, 7, 0)
bycat0 = {r['cat_pos']: r for r in rows0 if r['kind'] == 'card'}

# ── Пред-ассерты резолюции ──
SET = res['set']; seen = set()
def norm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))
for x in SET:
    c, f, cls, b, a = x['cat'], x['field'], x['class'], x['before'], x['after']
    assert (c, f) not in seen, f'дубль (cat{c},{f})'; seen.add((c, f))
    assert 0 <= c < N and cat0[c]['title'] == x['title'] and cat0[c]['source'] == x['source'], f'cat{c}: title/source'
    assert cat0[c].get(f) == b, f'cat{c}/{f}: before не совпал байт-в-байт'
    assert a != b, f'cat{c}/{f}: after == before'
    assert x.get('vol') == x['source'].split('_')[0] and isinstance(x.get('lines'), list) and x['lines'] and x.get('note'), f'cat{c}/{f}: vol/lines/note'
    parts = set(cls.split('+'))
    if f == 'annotation':
        assert parts <= {'lead', 'tail', 'prefix', 'restore', 'mid', 'none'}, f'cat{c}: класс {cls}'
        if 'none' in parts:
            assert a is None and c == 4275
        else:
            assert isinstance(a, str) and a and a == a.strip() and '  ' not in a and '\n' not in a and '\t' not in a, f'cat{c}: after'
            assert not MARKERS.search(a), f'cat{c}: маркер титров в after: {MARKERS.search(a).group()}'
            if parts <= {'lead', 'tail'}: assert norm(a) in norm(b), f'cat{c}: lead/tail — after не подстрока before'
            if parts == {'lead'}: assert len(a) < len(b) and norm(b).endswith(norm(a)), f'cat{c}: lead'
            if parts == {'tail'}: assert len(a) < len(b) and norm(b).startswith(norm(a)), f'cat{c}: tail'
            if 'prefix' in parts: assert norm(a).endswith(norm(b) if 'tail' not in parts else norm(a)[-20:]) or norm(b)[:40] in norm(a), f'cat{c}: prefix'
            if 'restore' in parts: assert re.match(r'^[А-ЯЁ0-9«"(…A-Z\[XIV]', a), f'cat{c}: restore не с прописной'
    elif f == 'year':
        assert cls == 'year' and c == 2243 and (b, a) == (1938, 1955)
    elif f == 'studio':
        assert cls == 'studio' and c == 2243 and a == 'Союзмультфильм'
    elif f == 'title':
        assert cls == 'title' and isinstance(a, str) and a == a.strip() and '  ' not in a and a != b
        mm = x['master']; r = bycat0[c]
        assert mm['xlsx_row'] == r['xlsx_row'] and mm['title_canon_before'] == r['title_canon'] and mm['master_title_before'] == al0[c]['master_title'] and mm['title_canon_after'] == mm['master_title_after'] == a, f'cat{c}: master-блок титула'
    else:
        raise AssertionError(f'cat{c}: поле {f}')
TITLE_CATS = {x['cat'] for x in SET if x['field'] == 'title'}
assert len(TITLE_CATS) == 36
MO = res['master_only']; assert len(MO) == 80
for mo in MO:
    c = mo['cat']; r = bycat0[c]
    assert c not in TITLE_CATS and mo['xlsx_row'] == r['xlsx_row'] and mo['title_canon_before'] == r['title_canon'] and mo['title_canon_after'] == cat0[c]['title'] == mo['master_title_after'] and mo['master_title_before'] == al0[c]['master_title'], f'master-only cat{c}'
REB = res['rebind']
assert REB == {'6812': {'xlsx_row': 6648, 'idx_num': 3068}, '6813': {'xlsx_row': 7200, 'idx_num': 3069}}
assert al0[6812]['xlsx_row'] == 7200 and al0[6813]['xlsx_row'] == 6648 and bycat0[6812]['xlsx_row'] == 7200 and bycat0[6813]['xlsx_row'] == 6648
assert bycat0[6812]['num'] == 3069 and bycat0[6813]['num'] == 3068 and bycat0[6813]['xlsx_title'] == 'Фитиль № 281'
NEWT = {x['cat']: x['after'] for x in SET if x['field'] == 'title'}
assert NEWT[6812] == 'Фитиль № 281' and NEWT[6813] == 'Фитиль № 282'

# ── Apply в памяти: каталог ──
snap = [dict(r) for r in cat0]
cat1 = copy.deepcopy(cat0)
for x in SET:
    cat1[x['cat']][x['field']] = x['after']
exp_set = {(x['cat'], x['field']) for x in SET}

# ── Инварианты И1′–И5′ ──
assert len(cat1) == N, 'И1′'
changed = {(i, k) for i in range(N) for k in set(cat1[i]) | set(snap[i]) if cat1[i].get(k) != snap[i].get(k)}
assert changed == exp_set, f'И2: {changed ^ exp_set}'
for i in range(N):
    for k in set(snap[i]) | set(cat1[i]):
        assert (k in snap[i]) == (k in cat1[i]), f'И3 ключ cat{i}/{k}'
        if (i, k) not in changed: assert snap[i].get(k) == cat1[i].get(k), f'И3 cat{i}/{k}'
assert Counter(r['source'] for r in cat1) == Counter(r['source'] for r in cat0), 'И4'
assert [(r['title'], r['source']) for r in cat1] == [((NEWT.get(i, cat0[i]['title'])), cat0[i]['source']) for i in range(N)], 'И5′'
assert all(isinstance(r['year'], int) for r in cat1) and all(isinstance(r['title'], str) and r['title'] for r in cat1)

# ── Alignment ──
al1 = copy.deepcopy(al0)
for c, t in NEWT.items():
    al1[c]['master_title'] = t
for mo in MO:
    al1[mo['cat']]['master_title'] = mo['master_title_after']
# перепривязка 6812 ↔ 6813
for c, rb in REB.items():
    a = al1[int(c)]; a['xlsx_row'] = rb['xlsx_row']; a['idx_num'] = rb['idx_num']; a['method'] = 'manual'; a['confidence'] = 'high'
    a['note'] = (a.get('note') or '') + (' | ' if a.get('note') else '') + 'Ф6-П2: перепривязка — тела статей «Фитиль № 281» (v14 @3159, cat6812) и «Фитиль № 282» (v14 @3173, cat6813) были перекрещены с привязкой мастера; исправлено'
    a['second_signal'] = 'печатная голова v14 @3159 / @3173'

# ── Мастер ──
m1 = copy.deepcopy(m0)
r2 = {r['xlsx_row']: r for r in m1['rows']}
src_of = {x['cat']: x for x in SET if x['field'] == 'title'}
for c, t in NEWT.items():
    r = r2[bycat0[c]['xlsx_row']]; r['title_canon'] = t; r['title_source'] = 'Ф6-П2: ' + src_of[c]['note']
for mo in MO:
    r = r2[mo['xlsx_row']]; r['title_canon'] = mo['title_canon_after']; r['title_source'] = 'Ф6-П2: титул каталога (= ' + mo['evidence'] + '); xlsx_title — сырьё'
    r['note'] = ((r.get('note') or '') + (' | ' if r.get('note') else '') + 'Ф6-П2: ' + mo['note'])
r6648, r7200 = r2[6648], r2[7200]
r6648['cat_pos'], r7200['cat_pos'] = 6812, 6813
r6648['cat_pos_f5'], r7200['cat_pos_f5'] = al0[6812]['cat_pos_f5'], al0[6813]['cat_pos_f5']
r6648['title_canon'] = 'Фитиль № 281'; r6648['title_source'] = 'Ф6-П2: xlsx row 6648 «Фитиль № 281» №3068 = печатная голова v14 @3159'
r7200['title_canon'] = 'Фитиль № 282'; r7200['title_source'] = 'Ф6-П2: печатная голова v14 @3173 «ФИТИЛЬ № 282.» (синтетическая строка, №3069)'
for r in (r6648, r7200):
    r['note'] = ((r.get('note') or '') + (' | ' if r.get('note') else '') + 'Ф6-П2: перепривязка cat6812 ↔ cat6813 (тела статей были перекрещены)')
m1['_meta'].update({'name': 'index_master_f6_p2', 'derived_from': 'index_master_f6_p1.json',
                    'f6_p2': {'date': datetime.date.today().isoformat(), 'catalog': OUT_CAT, 'alignment': OUT_AL,
                              'change': f'{len(NEWT)} титулов каталога синхронно в title_canon; {len(MO)} title_canon исправлены по титулу каталога (xlsx OCR/сдвиг f4_rebind); перепривязка row 6648 ↔ row 7200 (cat6812 ↔ cat6813)',
                              'resolution': 'scripts/f6_p2_resolution.json', 'sanction': 'scripts/_f6_p2_sanction.json'}})

# ── И6: биекция ──
assert len(al1) == N and all(a['cat_pos'] == i for i, a in enumerate(al1)) and all(a['xlsx_row'] is not None for a in al1)
assert len({a['xlsx_row'] for a in al1}) == N, 'И6 xlsx_row alignment'
rows1 = m1['rows']; cards = [r for r in rows1 if r['kind'] == 'card']
assert len(rows1) == 7203 and Counter(r['kind'] for r in rows1) == {'card': 7173, 'crossref': 22, 'unbound': 8}
assert sorted(r['cat_pos'] for r in cards) == list(range(N)) and len({r['xlsx_row'] for r in rows1}) == 7203
mx = {r['cat_pos']: r['xlsx_row'] for r in cards}
assert all(mx[a['cat_pos']] == a['xlsx_row'] for a in al1), 'И6 alignment.xlsx_row == мастер'
assert not [k for k, v in Counter((r['vol'], str(r['num'])) for r in cards).items() if v > 1], 'И6 (vol,num)'
assert all(r['vol'] == cat1[r['cat_pos']]['source'] for r in cards) and all(al1[i]['source'] == cat1[i]['source'] for i in range(N))
assert m1['strays'] == []
# синхронность титулов (§1.3): master_title == title_canon для всех карточных строк
bycat1 = {r['cat_pos']: r for r in cards}
assert all(al1[i]['master_title'] == bycat1[i]['title_canon'] for i in range(N) if al1[i]['master_title'] is not None), 'master_title ≠ title_canon'
# титул каталога == title_canon для правленых и master-only
assert all(cat1[c]['title'] == bycat1[c]['title_canon'] == al1[c]['master_title'] for c in set(NEWT) | {mo['cat'] for mo in MO})
# И3 alignment/мастер: прочие записи неизменны
touched_al = set(NEWT) | {mo['cat'] for mo in MO} | {6812, 6813}
for i in range(N):
    if i in touched_al:
        ch = {k for k in set(al0[i]) | set(al1[i]) if al0[i].get(k) != al1[i].get(k)}
        assert ch <= ({'master_title'} | ({'xlsx_row', 'idx_num', 'method', 'confidence', 'note', 'second_signal'} if i in (6812, 6813) else set())), f'И3 alignment cat{i}: {ch}'
    else:
        assert al0[i] == al1[i], f'И3 alignment cat{i}'
touched_rows = {bycat0[c]['xlsx_row'] for c in NEWT} | {mo['xlsx_row'] for mo in MO} | {6648, 7200}
r0 = {r['xlsx_row']: r for r in rows0}
for r in rows1:
    o = r0[r['xlsx_row']]
    if r['xlsx_row'] in touched_rows:
        ch = {k for k in set(o) | set(r) if o.get(k) != r.get(k)}
        assert ch <= ({'title_canon', 'title_source', 'note'} | ({'cat_pos', 'cat_pos_f5'} if r['xlsx_row'] in (6648, 7200) else set())), f'И3 мастер row {r["xlsx_row"]}: {ch}'
    else:
        assert o == r, f'И3 мастер row {r["xlsx_row"]}'

# ── Реестр и очередь ──
reg1 = copy.deepcopy(reg0)
closed = [e for e in reg1['entries'] if (e['field'] == 'title' and e['state'] == 'defect') or (e['cat'] == 5024 and e['state'] == 'suspect')]
assert {e['cat'] for e in closed} == {6812, 6813, 3685, 5654, 5024}
reg1['entries'] = [e for e in reg1['entries'] if e not in closed]
for e in closed: e['closed'] = 'Ф6-П2: ' + ('титул исправлен по печатной голове/указателю' if e['field'] == 'title' else 'начало абзаца восстановлено по печати v9 @1471 (prefix)')
reg1['closed_f6_p2'] = closed
e4275 = [x for x in SET if x['cat'] == 4275][0]
reg1['entries'].append({'cat': 4275, 'title': cat1[4275]['title'], 'source': cat1[4275]['source'], 'field': 'annotation', 'state': 'none',
                        'reason': e4275['note'], 'evidence': {'lines_v6': [2176, 2181]}, 'origin': 'Ф6-П2 (в)', 'cat_f5': al0[4275]['cat_pos_f5']})
reg1['entries'].sort(key=lambda e: (e['field'], e['cat']))
for e in reg1['entries']:
    if e['cat'] in NEWT: e['title'] = NEWT[e['cat']]
reg1['counts'] = dict(Counter(f"{e['field']}/{e['state']}" for e in reg1['entries']))
reg1['catalog'] = OUT_CAT; reg1['package'] = reg0['package'] + ' → Ф6-П2'
reg1['note'] = reg0['note'] + ' Ф6-П2: +cat4275 annotation/none (печать нечитаема); закрыты 4 title/defect (титулы исправлены) и annotation/suspect cat5024 (prefix); см. closed_f6_p2.'
none1 = {f: sorted(i for i, r in enumerate(cat1) if r[f] is None) for f in ('genre', 'studio', 'annotation', 'year')}
regn = {f: sorted(e['cat'] for e in reg1['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
assert regn == {f: none1[f] for f in regn} and none1['year'] == [], f'реестр none ≠ каталог'
assert (reg1['counts']['genre/none'], reg1['counts']['studio/none'], reg1['counts']['annotation/none']) == (12, 1, 8) and 'title/defect' not in reg1['counts'] and 'annotation/suspect' not in reg1['counts']
assert len(reg1['entries']) == 114 - 5 + 1
assert all(cat1[e['cat']]['title'] == e['title'] for e in reg1['entries']), 'реестр: title ↔ cat'
q1 = copy.deepcopy(q0)
for k in ('genre', 'studio_empty', 'annotation'):
    for e in q1[k]:
        if e['cat'] in NEWT: e['title'] = NEWT[e['cat']]
assert all(cat1[e['cat']]['title'] == e['title'] for k in ('genre', 'studio_empty', 'annotation') for e in q1[k]), 'очередь: title ↔ cat'

# ── Протокол ──
cls_cnt = dict(Counter((x['field'], x['class']) for x in SET))
prot = {'_meta': {**res['_meta'], 'applied': datetime.datetime.now().isoformat(timespec='minutes'),
                  'result': {'catalog': N, 'alignment': len(al1), 'master_rows': len(rows1), 'master_card': len(cards), 'strays': 0, 'deleted': 0,
                             'set': len(SET), 'set_by_class': {f'{f}/{c}': n for (f, c), n in cls_cnt.items()}, 'master_only': len(MO), 'rebind': 2,
                             'register': {'added': [4275], 'closed': sorted(e['cat'] for e in closed), 'counts': reg1['counts']}}},
        'set': SET, 'master_only': MO, 'rebind': {'alignment': {c: {k: al1[int(c)][k] for k in ('xlsx_row', 'idx_num', 'master_title', 'method')} for c in REB},
                                                  'master': {'6648': {k: r6648[k] for k in ('num', 'title_canon', 'cat_pos', 'xlsx_title')}, '7200': {k: r7200[k] for k in ('num', 'title_canon', 'cat_pos', 'xlsx_title')}}},
        'title_keep': res['title_keep'], 'renumbering': {}}
if DRY:
    print('DRY OK: И1′–И6 пройдены;', json.dumps(prot['_meta']['result'], ensure_ascii=False)); sys.exit(0)

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
for src, tag in ((SRC_CAT, 'catalog_f6_p1'), (SRC_AL, 'alignment_f6_p1'), (SRC_M, 'index_master_f6_p1'), (SRC_REG, 'Ф5_стабы_реестр'), (SRC_Q, 'Ф5_очередь_docx')):
    shutil.copy2(src, f'backups/{tag}_{ts}.json')
def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
dump(cat1, OUT_CAT); dump(al1, OUT_AL); dump(m1, OUT_M); dump(reg1, SRC_REG); dump(q1, SRC_Q)
dump(prot, 'scripts/_f6_p2_sanction.json')
for src, name in ((SRC_CAT, 'catalog_f6_p1.json'), (SRC_AL, 'alignment_f6_p1.json'), (SRC_M, 'index_master_f6_p1.json')):
    os.replace(src, f'backups/{name}')
print(f'OK Ф6-П2: set {len(SET)} {cls_cnt}; master-only {len(MO)}; rebind 2; каталог {N}; alignment {len(al1)}; '
      f'мастер rows {len(rows1)} (card {len(cards)}); страёв 0; реестр {len(reg1["entries"])} ({reg1["counts"]}); И1′–И6 пройдены.')
