# -*- coding: utf-8 -*-
"""Ф6-П3б мини-пакет — apply, режим Cowork. Запуск из КОРНЯ: python3 scripts/f6_apply_p3b.py [--dry]
Вход: state/catalog_final_v2.json (7174, после П3а), state/Ф5_стабы_реестр.json, scripts/f6_p3b_resolution.json.
Действия: правки annotation (gap-pre ×2, cred-cut ×2) на месте; реестр: +cat4732 annotation/source-only.
Прочие файлы state/ не меняются (состав/титулы/alignment/мастер — без изменений). И1′–И6, бэкапы, протокол scripts/_f6_p3b_sanction.json."""
import json, copy, os, re, shutil, sys, datetime, hashlib
from collections import Counter
DRY = '--dry' in sys.argv
CAT, REG = 'state/catalog_final_v2.json', 'state/Ф5_стабы_реестр.json'
FIELDS = ('id', 'title', 'genre', 'year', 'studio', 'annotation', 'source')
res = json.load(open('scripts/f6_p3b_resolution.json', encoding='utf-8'))
cat0 = json.load(open(CAT, encoding='utf-8')); reg0 = json.load(open(REG, encoding='utf-8'))
sha0 = hashlib.sha256(open(CAT, 'rb').read()).hexdigest()
N = 7174
assert len(cat0) == N and res['_meta']['input_sha256'] == sha0 and res['_meta']['input_records'] == N
assert len(reg0['entries']) == 109 and reg0['catalog'] == CAT
SET = res['set']; assert len(SET) == 4 and Counter(x['class'] for x in SET) == {'gap-pre': 2, 'cred-cut': 2}
for x in SET:
    c, b, a = x['cat'], x['before'], x['after']
    assert cat0[c]['annotation'] == b and cat0[c]['id'] == x['id'] and cat0[c]['title'] == x['title'] and a != b and a == a.strip() and '  ' not in a
    if x['class'] == 'gap-pre': assert a.endswith(' ' + b)
    else: assert b.endswith(a) and len(a) >= 30
cat1 = copy.deepcopy(cat0)
for x in SET: cat1[x['cat']]['annotation'] = x['after']
changed = {(i, k) for i in range(N) for k in FIELDS if cat1[i][k] != cat0[i][k]}
assert changed == {(x['cat'], 'annotation') for x in SET}, 'И2'
assert [(r['title'], r['year'], r['studio'], r['genre'], r['source'], r['id']) for r in cat1] == [(r['title'], r['year'], r['studio'], r['genre'], r['source'], r['id']) for r in cat0], 'И3/И5′'
reg1 = copy.deepcopy(reg0)
assert cat1[4732]['annotation'] == 'По мотивам одноименного романа Майн Рида.' and not any(e['cat'] == 4732 for e in reg1['entries'])
reg1['entries'].append({'cat': 4732, 'title': cat1[4732]['title'], 'source': cat1[4732]['source'], 'field': 'annotation', 'state': 'source-only',
                        'reason': 'после среза титров, поглощённых аннотацией (Ф6-П3б), осталась только формула источника; печатной прозы в статье нет (v8 @1512–1515)', 'evidence': None, 'origin': 'Ф6-П3б', 'cat_f5': None, 'id': 4733})
reg1['entries'].sort(key=lambda e: (e['cat'], e['field']))
reg1['counts'] = dict(sorted(Counter(f"{e['field']}/{e['state']}" for e in reg1['entries']).items()))
reg1['package'] = reg0['package'] + ' → Ф6-П3б'
reg1['note'] = reg0['note'] + ' Ф6-П3б: +cat4732 annotation/source-only (титры сняты из аннотации).'
assert len(reg1['entries']) == 110 and reg1['counts']['annotation/source-only'] == 32
prot = {'_meta': {**res['_meta'], 'applied': datetime.datetime.now().isoformat(timespec='minutes'), 'output': CAT,
                  'result': {'catalog': N, 'set': 4, 'set_by_class': {'gap-pre': 2, 'cred-cut': 2}, 'register': reg1['counts'], 'register_added_source_only': [4732]}}, 'set': SET}
if DRY: print('DRY OK', prot['_meta']['result']); sys.exit(0)
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
shutil.copy2(CAT, f'backups/catalog_final_v2_до_П3б_{ts}.json'); shutil.copy2(REG, f'backups/Ф5_стабы_реестр_{ts}.json')
def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, indent=1)
dump(cat1, CAT); dump(reg1, REG); dump(prot, 'scripts/_f6_p3b_sanction.json')
print('OK Ф6-П3б: set 4 (gap-pre 2, cred-cut 2); реестр 110 (+cat4732 source-only); sha256', hashlib.sha256(open(CAT, 'rb').read()).hexdigest())
