# -*- coding: utf-8 -*-
"""Приёмка финала Ф5: state/catalog_f5.json (или catalog_f5_k5.json) против alignment, реестра стабов и диспозиции страёв.
Запуск из корня папки: python3 scripts/f5_final_check.py [путь_к_каталогу]"""
import json, sys, os, collections, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
path = sys.argv[1] if len(sys.argv) > 1 else ('state/catalog_f5.json' if os.path.exists('state/catalog_f5.json') else 'state/catalog_f5_k5.json')
cat = json.load(open(path, encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
reg = json.load(open('state/Ф5_стабы_реестр.json', encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
ok = True
def chk(cond, msg):
    global ok
    print(('OK  ' if cond else 'FAIL'), msg)
    ok = ok and bool(cond)
print('каталог', path, 'sha256', hashlib.sha256(open(path,'rb').read()).hexdigest()[:16])
chk(len(cat) == 7232, f'И1 длина == 7232 ({len(cat)})')
strays = [i for i,a in enumerate(al) if a.get('xlsx_row') is None]
chk(len(strays) == 60, f'страёв 60 ({len(strays)})')
chk(all(al[i]['cat_pos'] == i and cat[i]['source'] == al[i]['source'] for i in range(7232)), 'alignment: cat_pos == позиция, source совпадает')
g5 = json.load(open('backups/catalog_f5_g5.json', encoding='utf-8')) if os.path.exists('backups/catalog_f5_g5.json') else None
if g5:
    chk(len(g5) == 7232 and all(g5[i]['title'] == cat[i]['title'] and g5[i]['source'] == cat[i]['source'] for i in range(7232)), 'И5 последовательность (title, source) == вход Ф5 (backups/catalog_f5_g5.json)')
else:
    print('INFO backups/catalog_f5_g5.json не найден — И5 против входа Ф5 не проверялся')
base = {'title','genre','year','studio','annotation','source'}
chk(all(set(r.keys()) - {'_merged', '_f4_recovered'} == base for r in cat), 'схема полей: title, genre, year, studio, annotation, source (+ служебные флаги Ф4 _merged / _f4_recovered — снять в Ф6)')
S = set(strays)
ns = [i for i in range(7232) if i not in S]
gN = [i for i in ns if cat[i]['genre'] is None]; sN = [i for i in ns if cat[i]['studio'] is None]; aN = [i for i in ns if not cat[i]['annotation']]
c = reg['counts']
chk(len(gN) == c['genre/none'], f'genre None у не-страёв {len(gN)} == реестр {c["genre/none"]}')
chk(len(sN) == c['studio/none'], f'studio None у не-страёв {len(sN)} == реестр {c["studio/none"]} ({sN})')
chk(len(aN) == c['annotation/none'], f'annotation None у не-страёв {len(aN)} == реестр {c["annotation/none"]} ({aN})')
yN = [i for i in ns if cat[i]['year'] is None]
chk(len(yN) == 0, f'year None у не-страёв == 0 ({yN})')
chk(sorted(gN) == sorted(x['cat'] for x in q['genre']), 'genre None == терминалы очереди genre')
chk([x['cat'] for x in q['year_empty']] and all(x['cat'] in S for x in q['year_empty']), f'year_empty очереди ({len(q["year_empty"])}) — все страи')
# точные дубли title+year (не-страи)
dup = collections.Counter((cat[i]['title'], cat[i]['year']) for i in ns)
dups = [(k,v) for k,v in dup.items() if v > 1]
print(f'INFO точных дублей title+year среди не-страёв: {len(dups)} → {dups[:12]}')
# годы по томам
bad = []
rng = {'v1':(1918,1935),'v2':(1929,1957),'v3':(1957,1963),'v4':(1963,1965),'v5':(1965,1967),'v6':(1967,1969),'v7':(1969,1971),'v8':(1971,1973),'v9':(1973,1975),'v10':(1975,1977),'v11':(1977,1979),'v12':(1979,1981),'v13':(1981,1983),'v14':(1983,1985),'v15':(1985,1987)}
for i in ns:
    v = cat[i]['source'].split('_')[0]; y = cat[i]['year']; lo,hi = rng[v]
    if y is not None and not (lo <= y <= hi): bad.append((i, cat[i]['title'][:30], y, v))
print(f'INFO годы не-страёв вне диапазона тома −1 (печатные годы дополнений/включений в альманахи, П3): {len(bad)} → {bad}')
hist = collections.Counter((cat[i]['year']//10)*10 for i in ns if cat[i]['year'])
print('INFO гистограмма по десятилетиям:', dict(sorted(hist.items())))
print('INFO по томам:', dict(sorted(collections.Counter(r['source'] for r in cat).items(), key=lambda x: int(x[0][1:].split('_')[0]))))
print('INFO служебные флаги Ф4: _merged', dict(collections.Counter(str(r['_merged']) for r in cat if '_merged' in r)), '; _f4_recovered (dict-провенанс Ф4):', sum(1 for r in cat if '_f4_recovered' in r), 'записей')
# маркеры титров/библиографии в аннотациях не-страёв
import re
mk = re.compile(r'(Библиография:|Авт\. сцен|В ролях:|Роли дублируют:|звукоопер\.)')
m = [i for i in ns if cat[i]['annotation'] and mk.search(cat[i]['annotation'])]
print(f'INFO аннотаций не-страёв с маркерами титров (остаточные лиды «Роли дублируют:»/«В ролях:», титры новелл старых волн) — бэклог Ф6: {len(m)} → {m}')
# диспозиция страёв
if os.path.exists('state/Ф6_страи_диспозиция.json'):
    d = json.load(open('state/Ф6_страи_диспозиция.json', encoding='utf-8'))
    chk(sorted(s['cat'] for s in d['strays']) == sorted(strays), 'диспозиция: все 60 страёв имеют вердикт')
    chk(all(s['target'] is None or s['target'] not in S for s in d['strays']), 'диспозиция: цели — не-страи')
    for t, a in list(d['actions']['restore'].items()) + list(d['actions']['append'].items()):
        chk(cat[int(t)]['annotation'] == a['before'], f'диспозиция: before cat{t} == каталог')
    k = d['actions']['keep']['1197']
    chk(cat[1197]['studio'] == k['fields']['studio']['before'] and cat[1197]['annotation'] == k['fields']['annotation']['before'], 'диспозиция: before cat1197 == каталог')
print('ИТОГ:', 'ПРИЁМКА ПРОЙДЕНА' if ok else 'ЕСТЬ РАСХОЖДЕНИЯ')
