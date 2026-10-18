# -*- coding: utf-8 -*-
"""Ф6-П3 сборка — apply, режим Cowork. Запуск из КОРНЯ: python3 scripts/f6_apply_p3.py [--dry]
Вход: state/catalog_f6_p2e.json (7173), state/alignment_f6_p2e.json, state/index_master_f6_p2e.json,
      state/Ф5_стабы_реестр.json, state/Ф5_очередь_docx.json, scripts/f6_p3_resolution.json.
Действия: (1) правки annotation по резолюции (restore/tail/punct); (2) сборка финальной схемы: id 1..N, поля
title, genre, year, studio, annotation, source; служебные ключи _merged/_f4_recovered сняты; (3) alignment/мастер
переименованы в final (+ поле id в строках), реестр/очередь обновлены (source-only +5, intro-only 7 закрыты как слитые П1).
Порядок: пред-ассерты → apply в памяти → И1′–И6 → бэкапы → запись → протокол scripts/_f6_p3_sanction.json."""
import json, copy, os, re, shutil, sys, datetime
from collections import Counter
DRY = '--dry' in sys.argv
SRC_CAT, SRC_AL, SRC_M = 'state/catalog_f6_p2e.json', 'state/alignment_f6_p2e.json', 'state/index_master_f6_p2e.json'
SRC_REG, SRC_Q = 'state/Ф5_стабы_реестр.json', 'state/Ф5_очередь_docx.json'
OUT_CAT, OUT_AL, OUT_M = 'state/catalog_final_v1.json', 'state/alignment_final.json', 'state/index_master_final.json'
FIELDS = ('id', 'title', 'genre', 'year', 'studio', 'annotation', 'source')
MARK = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер|Реж\.-пост|Опер\.-пост)')
PUNCT_END = re.compile(r'[.!?…»)"\']$')
res = json.load(open('scripts/f6_p3_resolution.json', encoding='utf-8'))
cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
al0 = json.load(open(SRC_AL, encoding='utf-8'))
m0 = json.load(open(SRC_M, encoding='utf-8'))
reg0 = json.load(open(SRC_REG, encoding='utf-8'))
q0 = json.load(open(SRC_Q, encoding='utf-8'))
# ── Пред-ассерты §0 ──
N = 7173
assert len(cat0) == N, f'И1(вход): {len(cat0)}'
assert Counter(k for r in cat0 for k in r) == {'title': N, 'genre': N, 'year': N, 'studio': N, 'annotation': N, 'source': N, '_merged': 6775, '_f4_recovered': 398}, 'ключи входа'
assert len(al0) == N and all(a['cat_pos'] == i for i, a in enumerate(al0)) and all(a['xlsx_row'] is not None for a in al0), 'alignment'
rows0 = m0['rows']; cards0 = [r for r in rows0 if r['kind'] == 'card']
assert len(rows0) == 7203 and Counter(r['kind'] for r in rows0) == {'card': N, 'crossref': 22, 'unbound': 8} and m0['strays'] == [], 'мастер'
assert sorted(r['cat_pos'] for r in cards0) == list(range(N)) and len({r['xlsx_row'] for r in rows0}) == 7203, 'мастер card/xlsx_row'
assert len(reg0['entries']) == 111 and reg0['catalog'] == SRC_CAT, 'реестр'
# ── Пред-ассерты резолюции ──
SET = res['set']
seen = set()
for x in SET:
    c, f, cls, b, a = x['cat'], x['field'], x['class'], x['before'], x['after']
    assert (c, f) not in seen, f'дубль (cat{c},{f})'; seen.add((c, f))
    assert f == 'annotation' and cls in ('restore', 'tail', 'punct'), f'cat{c}: {f}/{cls}'
    assert cat0[c]['annotation'] == b, f'cat{c}: before не совпал байт-в-байт'
    assert cat0[c]['title'] == x['title'] and cat0[c]['source'] == x['source'], f'cat{c}: title/source'
    assert isinstance(a, str) and a and a == a.strip() and '  ' not in a and '\t' not in a and ('\n' not in a or c in (3638, 4218, 4750, 4823)), f'cat{c}: after'
    assert a != b, f'cat{c}: after == before'
    assert x.get('vol') and x.get('note') is not None
    if cls == 'punct':
        old, new = x['ops'][0][1], x['ops'][0][2]
        cp = os.path.commonprefix([old, new])
        assert x['ops'][0][0] == 'PUNCT' and b.endswith(old) and a == b[:len(b) - len(old)] + new, f'cat{c}: punct'
        assert re.fullmatch(r'[.!?…»)"\']*', new[len(cp):]) and re.fullmatch(r'[\s\dа-яё.\-]{0,3}', old[len(cp):]), f'cat{c}: punct diff {old[len(cp):]!r}→{new[len(cp):]!r}'
        assert len(x['ops']) == 1 and x['lines']
    elif cls == 'tail':
        assert x['ops'][0][0] == 'TAIL' and len(a) < len(b) and len(a) >= 30, f'cat{c}: tail'
        core = a
        for o in x['ops'][1:]:
            assert o[0] in ('PUNCT', 'M'), f'cat{c}: tail ops {o}'
            if o[0] == 'PUNCT': assert core.endswith(o[2]); core = core[:len(core) - len(o[2])]
            if o[0] == 'M': assert core.endswith(o[2]); core = core[:len(core) - len(o[2])] + o[1]
        assert b.startswith(core), f'cat{c}: tail — остаток не является префиксом before'
        cut = b[len(core):].strip()
        assert re.search(r'(удостоен|присужден|премия|премии|приз|Приз|диплом|Диплом|медал|награда|награжден|лучшим|Ника|Гран|дипломов|Содержание I тома|В 19\d\d г\.|Зак|2294|Гэсударственн|кинофестивал)', cut), f'cat{c}: хвост не наградной/мусор: {cut[:60]}'
    elif cls == 'restore':
        assert x['lines'] or x['cat'] == 5112, f'cat{c}: нет @строк'
        add = a
        # добавленный/изменённый текст не содержит маркеров титров
        assert not MARK.search(a), f'cat{c}: маркер титров: {MARK.search(a).group()}'
        assert len(a) >= len(b) - 60, f'cat{c}: restore заметно короче before'
        assert PUNCT_END.search(a) or c in (2335,), f'cat{c}: restore без конечной пунктуации'
exp_set = {(x['cat'], 'annotation') for x in SET}
assert Counter(x['class'] for x in SET) == res['_meta']['counts']
# ── Apply в памяти ──
snap = [dict(r) for r in cat0]
cat_set = copy.deepcopy(cat0)
for x in SET:
    cat_set[x['cat']]['annotation'] = x['after']
# сборка финальной схемы
cat1 = []
for i, r in enumerate(cat_set):
    cat1.append({'id': i + 1, 'title': r['title'], 'genre': r['genre'], 'year': r['year'], 'studio': r['studio'], 'annotation': r['annotation'], 'source': r['source']})
# ── Инварианты ──
assert len(cat1) == N, 'И1′'
changed = {(i, k) for i in range(N) for k in ('title', 'genre', 'year', 'studio', 'annotation', 'source') if cat1[i][k] != snap[i][k]}
assert changed == exp_set, f'И2: {changed ^ exp_set}'
for x in SET: assert cat1[x['cat']]['annotation'] == x['after']
for i in range(N):
    assert list(cat1[i].keys()) == list(FIELDS) and cat1[i]['id'] == i + 1, f'схема cat{i}'
    for k in ('title', 'genre', 'year', 'studio', 'source'):
        assert cat1[i][k] == snap[i][k], f'И3 cat{i}/{k}'
    if (i, 'annotation') not in changed: assert cat1[i]['annotation'] == snap[i]['annotation'], f'И3 cat{i}/annotation'
assert Counter(r['source'] for r in cat1) == Counter(r['source'] for r in cat0), 'И4'
assert [(r['title'], r['source']) for r in cat1] == [(r['title'], r['source']) for r in cat0], 'И5′'
assert all(isinstance(r['id'], int) for r in cat1) and [r['id'] for r in cat1] == list(range(1, N + 1)), 'id 1..N'
assert all(r['year'] is not None and isinstance(r['year'], int) for r in cat1)
assert all(r['annotation'] is None or (r['annotation'] == r['annotation'].strip() and '  ' not in r['annotation']) for r in cat1)
# alignment/мастер: содержимое неизменно + поле id
al1 = []
for a in al0:
    b = dict(a); b['id'] = a['cat_pos'] + 1; al1.append(b)
m1 = copy.deepcopy(m0)
for r in m1['rows']:
    if r['kind'] == 'card': r['id'] = r['cat_pos'] + 1
m1['_meta'].update({'name': 'index_master_final', 'derived_from': 'index_master_f6_p2e.json',
                    'f6_p3': {'date': datetime.date.today().isoformat(), 'catalog': OUT_CAT, 'alignment': OUT_AL,
                              'change': 'строки без изменений (П3 правил только annotation каталога); в card-строки и alignment добавлено поле id (= cat_pos + 1 = id записи catalog_final_v1.json); файл переименован в final',
                              'resolution': 'scripts/f6_p3_resolution.json', 'sanction': 'scripts/_f6_p3_sanction.json'}})
cards1 = [r for r in m1['rows'] if r['kind'] == 'card']
assert len(al1) == N and all(a['cat_pos'] == i and a['id'] == i + 1 for i, a in enumerate(al1)), 'И6 alignment'
assert len({a['xlsx_row'] for a in al1}) == N and {r['cat_pos']: r['xlsx_row'] for r in cards1} == {a['cat_pos']: a['xlsx_row'] for a in al1}, 'И6 биекция'
assert all(r['vol'] == cat1[r['cat_pos']]['source'] for r in cards1) and all(r['id'] == cat1[r['cat_pos']]['id'] for r in cards1), 'И6 vol/id'
assert all({k: v for k, v in a.items() if k != 'id'} == al0[i] for i, a in enumerate(al1)), 'И3 alignment'
assert all({k: v for k, v in r.items() if k != 'id'} == r0 for r, r0 in zip(m1['rows'], rows0)), 'И3 мастер'
bycat = {r['cat_pos']: r for r in cards1}
assert all(al1[i]['master_title'] == bycat[i]['title_canon'] for i in range(N) if al1[i]['master_title'] is not None), 'master_title ≠ title_canon'
# ── Реестр ──
reg1 = copy.deepcopy(reg0)
SRC_ONLY = {2545: 'По одноименной повести А. С. Пушкина.', 3846: 'По одноименной сказке А. С. Пушкина.', 4664: 'По одноименной поэме А. С. Пушкина.',
            4250: 'По одноименному роману Ф. М. Достоевского.', 4814: 'По повести А. П. Чехова «Дуэль».'}
for c, txt in SRC_ONLY.items():
    assert cat1[c]['annotation'] == txt, f'cat{c}: source-only text'
    assert not any(e['cat'] == c for e in reg1['entries'])
    reg1['entries'].append({'cat': c, 'title': cat1[c]['title'], 'source': cat1[c]['source'], 'field': 'annotation', 'state': 'source-only',
                            'reason': 'после среза призового блока (Ф6-П3) осталась только формула источника; иной печатной прозы в статье нет', 'evidence': None, 'origin': 'Ф6-П3', 'cat_f5': al1[c]['cat_pos_f5']})
intro = [e for e in reg1['entries'] if e['state'] == 'intro-only']
assert len(intro) == 7 and all(len(cat1[e['cat']]['annotation']) > 300 for e in intro), 'intro-only: аннотации уже слиты П1'
reg1['entries'] = [e for e in reg1['entries'] if e['state'] != 'intro-only']
reg1['closed_f6_p3'] = [{**e, 'closed': 'Ф6-П3: новеллы слиты в запись Ф6-П1 по правилу k4 (диспозиция страёв RESTORE) — аннотация полная, слот не пустой'} for e in intro]
reg1['entries'].sort(key=lambda e: (e['cat'], e['field']))
for e in reg1['entries']: e['id'] = e['cat'] + 1
reg1['counts'] = dict(sorted(Counter(f"{e['field']}/{e['state']}" for e in reg1['entries']).items()))
reg1['catalog'] = OUT_CAT
reg1['package'] = reg0['package'] + ' → Ф6-П3'
reg1['note'] = reg0['note'] + ' Ф6-П3: +5 annotation/source-only (cat2545, 3846, 4664, 4250, 4814 — после среза призовых блоков); 7 intro-only закрыты (слиты П1) → closed_f6_p3; поле id = cat + 1.'
none_cnt = {f: [i for i, r in enumerate(cat1) if r[f] is None] for f in ('genre', 'studio', 'annotation', 'year')}
reg_none = {f: sorted(e['cat'] for e in reg1['entries'] if e['field'] == f and e['state'] == 'none') for f in ('genre', 'studio', 'annotation')}
assert reg_none == {f: none_cnt[f] for f in reg_none} and none_cnt['year'] == [], f'реестр none ≠ каталог'
assert len(reg1['entries']) == 111 - 7 + 5 == 109
q1 = copy.deepcopy(q0)
q1['_meta']['catalog'] = OUT_CAT
q1['_meta']['f6_p3'] = 'терминалы без изменений: genre 12, studio_empty 1, annotation 2'
for k in ('genre', 'studio_empty', 'annotation'):
    for e in q1[k]: e['id'] = e['cat'] + 1; assert cat1[e['cat']]['title'] == e['title']
# ── Протокол ──
prot = {'_meta': {**res['_meta'], 'applied': datetime.datetime.now().isoformat(timespec='minutes'),
                  'result': {'catalog': N, 'alignment': len(al1), 'master_rows': len(m1['rows']), 'master_card': len(cards1), 'strays': 0, 'deleted': 0,
                             'set': len(SET), 'set_by_class': dict(Counter(x['class'] for x in SET)), 'schema': list(FIELDS), 'service_keys_removed': ['_merged', '_f4_recovered'],
                             'register': {'added_source_only': sorted(SRC_ONLY), 'closed_intro_only': [e['cat'] for e in intro], 'counts': reg1['counts']}}},
        'set': SET}
if DRY:
    print('DRY OK: И1′–И6 пройдены;', json.dumps(prot['_meta']['result'], ensure_ascii=False)); sys.exit(0)
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
for src, tag in ((SRC_CAT, 'catalog_f6_p2e'), (SRC_AL, 'alignment_f6_p2e'), (SRC_M, 'index_master_f6_p2e'), (SRC_REG, 'Ф5_стабы_реестр'), (SRC_Q, 'Ф5_очередь_docx')):
    shutil.copy2(src, f'backups/{tag}_{ts}.json')
def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
dump(cat1, OUT_CAT); dump(al1, OUT_AL); dump(m1, OUT_M); dump(reg1, SRC_REG); dump(q1, SRC_Q)
dump(prot, 'scripts/_f6_p3_sanction.json')
for src, name in ((SRC_CAT, 'catalog_f6_p2e.json'), (SRC_AL, 'alignment_f6_p2e.json'), (SRC_M, 'index_master_f6_p2e.json')):
    os.replace(src, f'backups/{name}')
print(f'OK Ф6-П3: set {len(SET)} {dict(Counter(x["class"] for x in SET))}; каталог {N} (схема {FIELDS}); alignment {len(al1)}; мастер rows {len(m1["rows"])} (card {len(cards1)}); реестр {len(reg1["entries"])}; И1′–И6 пройдены.')
