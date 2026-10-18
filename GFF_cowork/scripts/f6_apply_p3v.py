# -*- coding: utf-8 -*-
"""Ф6-П3в (срез титров, поглощённых аннотациями) — apply, режим Cowork. Запуск из КОРНЯ: python3 scripts/f6_apply_p3v.py [--dry]
Вход: state/catalog_final_v2.json (7174, после П3а+П3б), state/Ф5_стабы_реестр.json (110), scripts/f6_p3v_resolution.json.
Действия: правки annotation на месте (cred-prefix / cred-inner / junk-prefix); реестр: +cat5740 annotation/source-only.
Прочие файлы state/ не меняются (состав/титулы/alignment/мастер — без изменений). И2/И3/И5′, бэкапы, протокол scripts/_f6_p3v_sanction.json."""
import json, copy, re, shutil, sys, datetime, hashlib
from collections import Counter
DRY = '--dry' in sys.argv
CAT, REG = 'state/catalog_final_v2.json', 'state/Ф5_стабы_реестр.json'
FIELDS = ('id', 'title', 'genre', 'year', 'studio', 'annotation', 'source')
CONCERT = re.compile(r'(концерт|Концерт|опера|Опера|балет|Балет|ревю|Ревю|Музыкальн|музыкальн|Фильм-спектакль|спектакль|Оперетта|оперетта|Эстрадн|эстрадн|цирк|Цирк)')
res = json.load(open('scripts/f6_p3v_resolution.json', encoding='utf-8'))
cat0 = json.load(open(CAT, encoding='utf-8')); reg0 = json.load(open(REG, encoding='utf-8'))
sha0 = hashlib.sha256(open(CAT, 'rb').read()).hexdigest()
N = 7174
assert len(cat0) == N and res['_meta']['input_sha256'] == sha0 and res['_meta']['input_records'] == N
assert len(reg0['entries']) == 110 and reg0['catalog'] == CAT
SET = res['set']; CLS = Counter(x['class'] for x in SET)
assert len(SET) == 123 and CLS == {'cred-prefix': 110, 'cred-inner': 12, 'junk-prefix': 1} and len({x['cat'] for x in SET}) == 123
def nm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))
for x in SET:
    c, b, a = x['cat'], x['before'], x['after']
    r = cat0[c]
    assert r['annotation'] == b and r['id'] == x['id'] and r['title'] == x['title'] and r['source'] == x['source'] and x['field'] == 'annotation'
    assert a != b and a == a.strip() and '  ' not in a and len(a) >= 30 and re.match(r'^(\.\.\.|…)?[А-ЯЁA-Z0-9«„(]', a)
    assert not CONCERT.search(r['genre'] or ''), f'cat{c}: концертный жанр (конвенция П2)'
    if x['class'] in ('cred-prefix', 'junk-prefix'):
        assert b.endswith(a) and x['removed'] and nm(b) == nm(x['removed']) + nm(a), f'cat{c}: prefix'
    else:
        A = nm(b)
        for piece in x['removed'].split(' | '):
            p = nm(piece); k = A.find(p); assert k > 0 and A.find(p, k + 1) < 0, f'cat{c}: inner piece'
            A = A[:k] + A[k + len(p):]
        assert A == nm(a), f'cat{c}: inner'
    assert x['lines'] and all(isinstance(k, int) for k in x['lines'])
cat1 = copy.deepcopy(cat0)
for x in SET: cat1[x['cat']]['annotation'] = x['after']
changed = {(i, k) for i in range(N) for k in FIELDS if cat1[i][k] != cat0[i][k]}
assert changed == {(x['cat'], 'annotation') for x in SET}, 'И2'
assert [(r['title'], r['year'], r['studio'], r['genre'], r['source'], r['id']) for r in cat1] == [(r['title'], r['year'], r['studio'], r['genre'], r['source'], r['id']) for r in cat0], 'И3/И5′'
assert all(r['annotation'] is None or r['annotation'] == r['annotation'].strip() for r in cat1)
so = res['_meta']['source_only']; assert so == [5740]
reg1 = copy.deepcopy(reg0)
assert cat1[5740]['annotation'] == 'По мотивам романа И. Гончарова «Обломов».' and not any(e['cat'] == 5740 for e in reg1['entries'])
reg1['entries'].append({'cat': 5740, 'title': cat1[5740]['title'], 'source': cat1[5740]['source'], 'field': 'annotation', 'state': 'source-only',
                        'reason': 'после среза титров, поглощённых аннотацией (Ф6-П3в: «Текст от автора читает…», «В фильме использована музыка…» v11 @2327–2328), осталась только формула источника; печатной прозы в статье нет (v11 @2329, далее призы)', 'evidence': None, 'origin': 'Ф6-П3в', 'cat_f5': None, 'id': 5741})
reg1['entries'].sort(key=lambda e: (e['cat'], e['field']))
reg1['counts'] = dict(sorted(Counter(f"{e['field']}/{e['state']}" for e in reg1['entries']).items()))
reg1['package'] = reg0['package'] + ' → Ф6-П3в'
reg1['note'] = reg0['note'] + ' Ф6-П3в: +cat5740 annotation/source-only (титры сняты из аннотации).'
assert len(reg1['entries']) == 111 and reg1['counts']['annotation/source-only'] == 33
prot = {'_meta': {**res['_meta'], 'applied': datetime.datetime.now().isoformat(timespec='minutes'), 'output': CAT,
                  'result': {'catalog': N, 'set': len(SET), 'set_by_class': dict(CLS), 'register': reg1['counts'], 'register_added_source_only': so}}, 'set': SET}
if DRY: print('DRY OK', prot['_meta']['result']); sys.exit(0)
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
shutil.copy2(CAT, f'backups/catalog_final_v2_до_П3в_{ts}.json'); shutil.copy2(REG, f'backups/Ф5_стабы_реестр_{ts}.json')
def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, indent=1)
dump(cat1, CAT); dump(reg1, REG); dump(prot, 'scripts/_f6_p3v_sanction.json')
print('OK Ф6-П3в: set', len(SET), dict(CLS), '; реестр 111 (+cat5740 source-only); sha256', hashlib.sha256(open(CAT, 'rb').read()).hexdigest())
