# -*- coding: utf-8 -*-
"""Ф6-П3а корректирующий пакет — apply, режим Cowork. Запуск из КОРНЯ: python3 scripts/f6_apply_p3a.py [--dry]
Вход: state/catalog_final_v1.json (7173), state/alignment_final.json, state/index_master_final.json, state/Ф5_стабы_реестр.json,
      state/Ф5_очередь_docx.json, scripts/f6_p3a_resolution.json.
Действия: (1) правки annotation по резолюции (gap-pre/head/post/mid/tailrepl/almanac — утерянные печатные строки);
(2) титул cat708 (склейка двух строк xlsx) + title_canon мастера row 1088 + alignment.master_title;
(3) вставка записи «Старый наездник» 1940 (v2 @3136, литерный №1628а) перед «Суворов» → id сдвигаются на +1 с id 1629;
    alignment: новая строка (xlsx_row синтетический), мастер: новая card-строка; реестр/очередь: cat/id сдвинуты;
(4) выход: state/catalog_final_v2.json (7174); alignment/мастер обновлены на месте (_meta.f6_p3a); v1 → backups/.
Порядок: пред-ассерты → apply в памяти → И1′–И6 → бэкапы → запись → протокол scripts/_f6_p3a_sanction.json."""
import json, copy, os, re, shutil, sys, datetime, hashlib
from collections import Counter
DRY = '--dry' in sys.argv
SRC_CAT, SRC_AL, SRC_M = 'state/catalog_final_v1.json', 'state/alignment_final.json', 'state/index_master_final.json'
SRC_REG, SRC_Q = 'state/Ф5_стабы_реестр.json', 'state/Ф5_очередь_docx.json'
OUT_CAT = 'state/catalog_final_v2.json'
FIELDS = ('id', 'title', 'genre', 'year', 'studio', 'annotation', 'source')
MARK = re.compile(r'(Авт\. сцен|Авт\.сцен|Авт\. текста|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер|Реж\.-пост|Опер\.-пост|ЦСДФ)')
PUNCT_END = re.compile(r'[.!?…»)"\']$')
res = json.load(open('scripts/f6_p3a_resolution.json', encoding='utf-8'))
cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
al0 = json.load(open(SRC_AL, encoding='utf-8'))
m0 = json.load(open(SRC_M, encoding='utf-8'))
reg0 = json.load(open(SRC_REG, encoding='utf-8'))
q0 = json.load(open(SRC_Q, encoding='utf-8'))
sha0 = hashlib.sha256(open(SRC_CAT, 'rb').read()).hexdigest()
# ── Пред-ассерты §0 ──
N0 = 7173; N1 = N0 + 1
assert len(cat0) == N0 and res['_meta']['input_sha256'] == sha0 and res['_meta']['input_records'] == N0, 'вход ≠ вход резолюции'
assert all(list(r.keys()) == list(FIELDS) and r['id'] == i + 1 for i, r in enumerate(cat0))
assert len(al0) == N0 and all(a['cat_pos'] == i and a['id'] == i + 1 for i, a in enumerate(al0))
rows0 = m0['rows']; cards0 = [r for r in rows0 if r['kind'] == 'card']
assert len(rows0) == 7203 and Counter(r['kind'] for r in rows0) == {'card': N0, 'crossref': 22, 'unbound': 8} and m0['strays'] == []
assert sorted(r['cat_pos'] for r in cards0) == list(range(N0)) and len({r['xlsx_row'] for r in rows0}) == 7203
assert [r['xlsx_row'] for r in rows0] == sorted(r['xlsx_row'] for r in rows0), 'мастер: строки отсортированы по xlsx_row'
assert len(reg0['entries']) == 109 and reg0['catalog'] == SRC_CAT
SET = res['set']; INS = res['insert']; TIT = res['title']
seen = set()
for x in SET:
    c, cls, b, a = x['cat'], x['class'], x['before'], x['after']
    assert (c, 'annotation') not in seen; seen.add((c, 'annotation'))
    assert x['field'] == 'annotation' and cls in ('gap-pre', 'gap-head', 'gap-post', 'gap-mid', 'gap-tailrepl', 'gap-almanac'), f'cat{c}: {cls}'
    assert cat0[c]['annotation'] == b and cat0[c]['title'] == x['title'] and cat0[c]['source'] == x['source'] and cat0[c]['id'] == x['id'], f'cat{c}: before/title/source/id'
    assert isinstance(a, str) and a and a == a.strip() and '  ' not in a and '\t' not in a and '\n' not in a and a != b, f'cat{c}: after'
    assert x['lines'] and x['raw'] and x['note'] and x['ops']
    if cls in ('gap-pre', 'gap-head'): assert a.endswith(' ' + b) and not MARK.search(a[:len(a) - len(b)]), f'cat{c}: pre'
    elif cls == 'gap-post': assert a.startswith(b + ' ') and not MARK.search(a[len(b):]) and PUNCT_END.search(a), f'cat{c}: post'
    elif cls == 'gap-mid':
        cp = os.path.commonprefix([a, b]); assert 0 < len(cp) < len(b) and len(a) > len(b) and not MARK.search(a), f'cat{c}: mid'
    elif cls == 'gap-tailrepl': assert a.startswith(b[:-len('Фильм не сохранился.')].rstrip()) and a.endswith('Фильм не сохранился.') and b.endswith('Фильм не сохранился.')
    elif cls == 'gap-almanac': assert not MARK.search(a) and len(a) > len(b) and PUNCT_END.search(a), f'cat{c}: almanac'
assert Counter(x['class'] for x in SET) == res['_meta']['counts'] and len(SET) == 56
assert len(TIT) == 1 and TIT[0]['cat'] == 708 and cat0[708]['title'] == TIT[0]['before'] and cat0[708]['id'] == 709
row1088 = [r for r in rows0 if r['xlsx_row'] == 1088]; assert len(row1088) == 1 and row1088[0]['cat_pos'] == 708 and row1088[0]['title_canon'] == TIT[0]['before']
assert al0[708]['master_title'] == TIT[0]['before'] and al0[708]['xlsx_row'] == 1088
rec = INS['record']; BC = INS['before_cat']
assert BC == 1628 and cat0[BC]['title'] == 'Суворов' and cat0[BC - 1]['title'] == 'Случай в вулкане'
assert rec['title'] == 'Старый наездник' and rec['year'] == 1940 and rec['genre'] == 'Комедия' and rec['studio'] == 'Мосфильм' and rec['source'] == 'v2_1936-1957'
assert rec['annotation'] and not MARK.search(rec['annotation']) and rec['annotation'] == rec['annotation'].strip() and '  ' not in rec['annotation']
assert not any(r['title'] == rec['title'] for r in cat0) and INS['num'] == '1628а'
# ── Apply в памяти: аннотации, титул ──
cat_set = copy.deepcopy(cat0)
for x in SET: cat_set[x['cat']]['annotation'] = x['after']
cat_set[708]['title'] = TIT[0]['after']
# ── вставка записи ──
new_rec = {'id': None, 'title': rec['title'], 'genre': rec['genre'], 'year': rec['year'], 'studio': rec['studio'], 'annotation': rec['annotation'], 'source': rec['source']}
cat1 = cat_set[:BC] + [new_rec] + cat_set[BC:]
for i, r in enumerate(cat1): r['id'] = i + 1
def shift(c): return c + 1 if c >= BC else c
NEWROW = max(r['xlsx_row'] for r in rows0) + 1
al1 = []
for a in al0:
    b = dict(a); b['cat_pos'] = shift(a['cat_pos']); b['id'] = b['cat_pos'] + 1
    if a['cat_pos'] == 708: b['master_title'] = TIT[0]['after']
    al1.append(b)
new_al = {'cat_pos': BC, 'source': rec['source'], 'cat_title': rec['title'], 'xlsx_row': NEWROW, 'idx_num': INS['num'], 'method': 'manual', 'confidence': 'high',
          'second_signal': f'печатная голова v2 @{INS["head_line"]} «{INS["raw_head"][:60]}…» — литерный № между №1628 «Случай в вулкане» и №1629 «Суворов»',
          'note': 'Ф6-П3а: запись отсутствовала в каталоге Ф5/Ф6 (найдена регрессионной сверкой со старым каталогом catalog_all_v4, где стояла с годом ВЭ 1959); '
                  'строки в xlsx-указателе нет — синтетическая card-строка мастера', 'master_title': rec['title'], 'cat_pos_f5': None, 'id': BC + 1}
al1 = al1[:BC] + [new_al] + al1[BC:]
m1 = copy.deepcopy(m0)
for r in m1['rows']:
    if r['kind'] == 'card':
        r['cat_pos'] = shift(r['cat_pos']); r['id'] = r['cat_pos'] + 1
    if r['xlsx_row'] == 1088:
        r['title_canon'] = TIT[0]['after']; r['title_source'] = f'печатная голова v1 @{TIT[0]["print_line"]} («ЧТО ДОЛЖЕН ЗНАТЬ РАБОЧИЙ И КРЕСТЬЯНИН О СССР…»)'
        r['note'] = ('Ф6-П3а: строка xlsx — склейка двух строк указателя: «Что говорит «МОС»—сей отгадайте вопрос» (№217, cat216 → синтетическая row 7196) + '
                     '«Что должен знать .рабочий и крестьянин о СССР» (№711, эта запись); title_canon = вторая часть по печатной голове')
        r['alt_titles'] = list(r.get('alt_titles') or [])
new_row = {'xlsx_row': NEWROW, 'num': INS['num'], 'title_canon': rec['title'], 'title_source': f'печатная голова v2 @{INS["head_line"]} («1628а. СТАРЫЙ НАЕЗДНИК…»)',
           'vol': rec['source'], 'kind': 'card', 'cat_pos': BC, 'xlsx_title': None, 'xlsx_num': None, 'xlsx_year': None, 'alt_titles': [],
           'note': 'Ф6-П3а: статья есть в печати тома (литерный №1628а), строки в xlsx-указателе нет; запись каталога восстановлена по печати',
           'provenance': 'synthetic: Ф6-П3а — регрессионная сверка со старым каталогом + печать v2 @3136–3141', 'cat_pos_f5': None, 'id': BC + 1}
m1['rows'].append(new_row)
st = m1['_meta']['stats']; st['карточных строк'] = N1; st['литерные номера'] = sorted(set(st['литерные номера']) | {INS['num']}); st['по томам'][rec['source']] += 1
m1['_meta']['derived_from'] = 'index_master_final.json (Ф6-П3)'
m1['_meta']['f6_p3a'] = {'date': datetime.date.today().isoformat(), 'catalog': OUT_CAT, 'alignment': SRC_AL,
                         'change': f'+1 card-строка (синтетическая xlsx_row {NEWROW}, №{INS["num"]} «{rec["title"]}» → cat_pos {BC}/id {BC + 1}); cat_pos/id card-строк ≥ {BC} сдвинуты на +1; '
                                   'row 1088: title_canon «Что должен знать рабочий и крестьянин о СССР» (склейка xlsx разобрана)',
                         'resolution': 'scripts/f6_p3a_resolution.json', 'sanction': 'scripts/_f6_p3a_sanction.json'}
cards1 = [r for r in m1['rows'] if r['kind'] == 'card']
# ── Инварианты ──
assert len(cat1) == N1, 'И1′'
def old_of(i): return None if i == BC else (i if i < BC else i - 1)
exp_changed = {(shift(x['cat']), 'annotation') for x in SET} | {(708, 'title')}
changed = set()
for i, r in enumerate(cat1):
    j = old_of(i)
    if j is None: continue
    for k in ('title', 'genre', 'year', 'studio', 'annotation', 'source'):
        if r[k] != cat0[j][k]: changed.add((i, k))
assert changed == exp_changed, f'И2: {changed ^ exp_changed}'
for x in SET: assert cat1[shift(x['cat'])]['annotation'] == x['after']
assert cat1[708]['title'] == TIT[0]['after'] and cat1[BC] == {**new_rec, 'id': BC + 1}
for i, r in enumerate(cat1):
    assert list(r.keys()) == list(FIELDS) and r['id'] == i + 1, f'схема cat{i}'
src_cnt = Counter(r['source'] for r in cat0); src_cnt[rec['source']] += 1
assert Counter(r['source'] for r in cat1) == src_cnt, 'И4'
exp_seq = [(r['title'], r['source']) for r in cat0]; exp_seq[708] = (TIT[0]['after'], cat0[708]['source']); exp_seq.insert(BC, (rec['title'], rec['source']))
assert [(r['title'], r['source']) for r in cat1] == exp_seq, 'И5′'
assert [r['id'] for r in cat1] == list(range(1, N1 + 1))
assert all(r['year'] is not None and isinstance(r['year'], int) for r in cat1)
assert all(r['annotation'] is None or (r['annotation'] == r['annotation'].strip() and '  ' not in r['annotation']) for r in cat1)
assert len(al1) == N1 and all(a['cat_pos'] == i and a['id'] == i + 1 for i, a in enumerate(al1)), 'И6 alignment'
assert len({a['xlsx_row'] for a in al1}) == N1 and {r['cat_pos']: r['xlsx_row'] for r in cards1} == {a['cat_pos']: a['xlsx_row'] for a in al1}, 'И6 биекция'
assert len(cards1) == N1 and sorted(r['cat_pos'] for r in cards1) == list(range(N1)) and len({r['xlsx_row'] for r in m1['rows']}) == len(m1['rows']) == 7204
assert all(r['vol'] == cat1[r['cat_pos']]['source'] and r['id'] == cat1[r['cat_pos']]['id'] for r in cards1), 'И6 vol/id'
bycat = {r['cat_pos']: r for r in cards1}
assert all(al1[i]['master_title'] == bycat[i]['title_canon'] for i in range(N1) if al1[i]['master_title'] is not None), 'master_title ≠ title_canon'
# И3 alignment/мастер: кроме cat_pos/id/master_title(708)/новой строки — байт-в-байт
for i, a in enumerate(al0):
    b = al1[shift(i)]; ka = {k: v for k, v in a.items() if k not in ('cat_pos', 'id', 'master_title')}; kb = {k: v for k, v in b.items() if k not in ('cat_pos', 'id', 'master_title')}
    assert ka == kb and (a['master_title'] == b['master_title'] or i == 708), f'И3 alignment {i}'
for r0 in rows0:
    r = [x for x in m1['rows'] if x['xlsx_row'] == r0['xlsx_row']][0]
    drop = ('cat_pos', 'id') + (('title_canon', 'title_source', 'note', 'alt_titles') if r0['xlsx_row'] == 1088 else ())
    assert {k: v for k, v in r.items() if k not in drop} == {k: v for k, v in r0.items() if k not in drop}, f'И3 мастер row {r0["xlsx_row"]}'
# ── Реестр / очередь: сдвиг cat/id ──
reg1 = copy.deepcopy(reg0)
for key in ('entries', 'closed_f6_p2', 'closed_f6_p3'):
    for e in reg1[key]:
        if e['cat'] == 708 and e.get('title') == TIT[0]['before']: e['title'] = TIT[0]['after']; e['note_f6_p3a'] = 'титул исправлен Ф6-П3а (склейка двух строк xlsx)'
        e['cat'] = shift(e['cat']); e['id'] = e['cat'] + 1
for e in reg1['entries']: assert cat1[e['cat']]['title'] == e['title'], f'реестр cat{e["cat"]}'
reg1['catalog'] = OUT_CAT
reg1['package'] = reg0['package'] + ' → Ф6-П3а'
reg1['note'] = reg0['note'] + f' Ф6-П3а: вставлена запись «{rec["title"]}» ({rec["year"]}) перед «Суворов» — cat/id ≥ {BC} сдвинуты на +1 (состав реестра без изменений); каталог {OUT_CAT}.'
reg1['renumbered'] = reg0['renumbered'] + f'; Ф6-П3а: cat/id ≥ {BC} сдвинуты на +1 (вставка cat{BC} «{rec["title"]}»)'
none_cnt = {f: [i for i, r in enumerate(cat1) if r[f] is None] for f in ('genre', 'studio', 'annotation', 'year')}
reg_none = {f: sorted(e['cat'] for e in reg1['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
assert reg_none == {f: none_cnt[f] for f in reg_none} and none_cnt['year'] == [], 'реестр none ≠ каталог'
assert len(reg1['entries']) == 109 and reg1['counts'] == dict(sorted(Counter(f"{e['field']}/{e['state']}" for e in reg1['entries']).items()))
q1 = copy.deepcopy(q0)
q1['_meta']['catalog'] = OUT_CAT
q1['_meta']['f6_p3a'] = f'терминалы без изменений; cat/id ≥ {BC} сдвинуты на +1 (вставка «{rec["title"]}»)'
for k in ('genre', 'studio_empty', 'annotation'):
    for e in q1[k]:
        if e['cat'] == 708 and e.get('title') == TIT[0]['before']: e['title'] = TIT[0]['after']
        e['cat'] = shift(e['cat']); e['id'] = e['cat'] + 1; assert cat1[e['cat']]['title'] == e['title']
# ── Протокол ──
prot = {'_meta': {**res['_meta'], 'applied': datetime.datetime.now().isoformat(timespec='minutes'), 'output': OUT_CAT,
                  'result': {'catalog': N1, 'alignment': len(al1), 'master_rows': len(m1['rows']), 'master_card': len(cards1), 'strays': 0, 'deleted': 0, 'inserted': 1,
                             'set': len(SET), 'set_by_class': dict(Counter(x['class'] for x in SET)), 'title': 1, 'id_shift': f'cat ≥ {BC}: +1 (id 1629 → 1630 …)',
                             'new_master_row': NEWROW, 'register': reg1['counts']}},
        'set': [{**x, 'cat_v1': x['cat'], 'cat': shift(x['cat']), 'id_v1': x['id'], 'id': shift(x['cat']) + 1} for x in SET],
        'insert': {**INS, 'cat': BC, 'id': BC + 1, 'xlsx_row': NEWROW}, 'title': [{**t, 'cat_v1': t['cat']} for t in TIT]}
if DRY:
    print('DRY OK: И1′–И6 пройдены;', json.dumps(prot['_meta']['result'], ensure_ascii=False)); sys.exit(0)
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
for src, tag in ((SRC_CAT, 'catalog_final_v1'), (SRC_AL, 'alignment_final_p3'), (SRC_M, 'index_master_final_p3'), (SRC_REG, 'Ф5_стабы_реестр'), (SRC_Q, 'Ф5_очередь_docx')):
    shutil.copy2(src, f'backups/{tag}_{ts}.json')
def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
dump(cat1, OUT_CAT); dump(al1, SRC_AL); dump(m1, SRC_M); dump(reg1, SRC_REG); dump(q1, SRC_Q)
dump(prot, 'scripts/_f6_p3a_sanction.json')
os.replace(SRC_CAT, 'backups/catalog_final_v1.json')
sha1 = hashlib.sha256(open(OUT_CAT, 'rb').read()).hexdigest()
print(f'OK Ф6-П3а: set {len(SET)} {dict(Counter(x["class"] for x in SET))}; титул 1; вставка 1 (cat{BC}/id{BC + 1}); каталог {N1} → {OUT_CAT} sha256 {sha1}; '
      f'alignment {len(al1)}; мастер rows {len(m1["rows"])} (card {len(cards1)}); реестр {len(reg1["entries"])}; И1′–И6 пройдены; v1 → backups/.')
