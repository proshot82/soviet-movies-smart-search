# -*- coding: utf-8 -*-
"""П4 a3 — финальная резолюция: авто-лиды + концертные (ручная санкция) + restore лид-всё."""
import json, re, importlib.util, sys
spec = importlib.util.spec_from_file_location('a3s', 'work/a3_scan2.py')
# грамматику переиспользуем импортом функций через exec среза файла нельзя — скопируем минимум:
sys.path.insert(0, 'scripts')

cat = json.load(open('state/catalog_f5_a2.json', encoding='utf-8'))
auto = json.load(open('work/a3_res_auto2.json', encoding='utf-8'))['cut']
draft = json.load(open('work/a3_restores_draft.json', encoding='utf-8'))

# --- концертные: пересчитать грамматикой из scan2 (локальный реимпорт функций) ---
src = open('work/a3_scan2.py', encoding='utf-8').read()
head = src.split("res, points, doubts, log, manual_conc")[0]
ns = {}
exec(head, ns)
sentences, is_credit = ns['sentences'], ns['is_credit']
CONC = ns['CONC']
conc_cuts, conc_report = {}, []
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
A1 = ns['A1']
for i, r in enumerate(cat):
    if i in strays or i in A1: continue
    t = r.get('annotation')
    if not t: continue
    g = r.get('genre') or ''
    if not CONC.search(g): continue
    sents = sentences(t)
    classes, cut_end = [], 0
    for (s0, s1) in sents:
        k = is_credit(t[s0:s1])
        if k: classes.append(k); cut_end = s1
        else: break
    if not classes: continue
    lead = t[:cut_end]; rem = t[cut_end:].strip()
    if len(rem) < 15: conc_report.append((i, g, 'ЛИД-ВСЁ?', lead[:80], rem)); continue
    if i == 4396: continue
    flag = '' if (rem[0].isupper() or rem[0].isdigit() or rem[0] in '«…(') else 'a4-след'
    conc_cuts[str(i)] = {'lead': lead, 'tail': None,
                         'class': 'лид(концертный жанр, ручная санкция):' + '+'.join(classes)}
    conc_report.append((i, g, flag, lead[-60:], rem[:60]))

# --- restores ---
def full(vname, idxs):
    L = json.load(open(f'work/{vname}_lines.json', encoding='utf-8'))
    parts = [L[j][1].strip() for j in idxs]
    out = parts[0]
    for p in parts[1:]:
        out = (out[:-1] + p) if out.endswith('-') else (out + ' ' + p)
    return re.sub(r'\s+', ' ', out).strip()

restores = {}
for k, v in draft.items():
    if k in ('2878', '3304', '3306', '3324', '3343', '3464', '5438', '3478', '3716'):
        continue
    restores[k] = v
TRIM = {'3306': 'О воспитании подрастающего поколения.',
        '3324': 'По рассказу «Озеро Палиастоми»',
        '3343': 'По мотивам одноименной оперетты',
        '3464': 'По повести А. Казбеги',
        '5438': 'По одноименному рассказу Давида'}
for k, marker in TRIM.items():
    v = dict(draft[k])
    j = v['text'].find(marker)
    assert j > 0, k
    v['text'] = v['text'][j:]
    v['note'] += '; список ролей перед прозой не включён'
    restores[k] = v
restores['2878'] = {'text': full('v3', [3346, 3347, 3348]), 'vol': 'v3', 'lines': [3346, 3347, 3348],
    'note': 'проза статьи (лид-всё)'}
restores['3304'] = {'text': full('v3', [6769, 6770, 6771]), 'vol': 'v3', 'lines': [6769, 6770, 6771],
    'note': 'проза статьи (лид-всё)'}
restores['2794'] = {'text': full('v3', [2699, 2700, 2701]), 'vol': 'v3', 'lines': [2699, 2700, 2701],
    'note': 'проза статьи (лид-всё)'}
restores['3276'] = {'text': full('v3', [6513, 6514]), 'vol': 'v3', 'lines': [6513, 6514],
    'note': 'проза статьи (лид-всё)'}
L4 = json.load(open('work/v4_lines.json', encoding='utf-8'))
def nn(j, upto='Авт.'):
    t = L4[j][1].strip()
    return t.split(upto)[0].strip().rstrip('.').strip() + '.'
t3478 = ' '.join([
 L4[1343][1].strip(),
 nn(1344), L4[1346][1].strip(), L4[1347][1].strip(),
 nn(1348), L4[1350][1].strip(), (L4[1351][1].strip()[:-1] + L4[1352][1].strip()) if L4[1351][1].strip().endswith('-') else (L4[1351][1].strip() + ' ' + L4[1352][1].strip()),
 nn(1353), L4[1355][1].strip(), L4[1356][1].strip()])
restores['3478'] = {'text': re.sub(r'\s+', ' ', t3478), 'vol': 'v4',
 'lines': [1343, 1344, 1346, 1347, 1348, 1350, 1351, 1352, 1353, 1355, 1356],
 'note': 'киноальманах: состав + по-новелльные формулы и проза; титры новелл и призовая справка @1357 не включены; названия новелл взяты из голов новелл (@1344/1348/1353)'}
n1 = '«Служебный лифт».'   # @6548: «Служебный лиф т»Д — склейка внутрисловного OCR-разрыва, мусорная литера снята
t3716 = ' '.join([n1, L4[6552][1].strip(), L4[6553][1].strip(), L4[6554][1].strip(),
                  '«Чернушка».', L4[6559][1].strip(), L4[6560][1].strip(), L4[6561][1].strip()])
restores['3716'] = {'text': re.sub(r'\s+', ' ', t3716), 'vol': 'v4',
 'lines': [6548, 6552, 6553, 6554, 6555, 6559, 6560, 6561],
 'note': 'киноальманах: по-новелльные формулы и проза; названия новелл из голов (@6548 «Служебный лиф т»Д — внутрисловный OCR-разрыв склеен, мусорная литера снята; @6555); титры не включены'}

res = {'cut': dict(auto), 'restore': restores,
       'none': {'5266': {'note': 'статья тома (v10 @669-675): голова+титры+«В фильме использована музыка А. Вивальди» — аннотационной прозы печатно нет; прежнее значение — та же муз. справка'}},
       'confirm': {}, 'notfound': {}}
for k, v in conc_cuts.items():
    assert k not in res['cut']
    res['cut'][k] = v
overlap = set(res['cut']) & (set(res['restore']) | set(res['none']))
assert not overlap, overlap
json.dump(res, open('scripts/a3_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('=== КОНЦЕРТНЫЕ ===')
for i, g, flag, le, rem in conc_report:
    print(f'cat{i} [{g}]{flag}: …{le} ||| {rem}')
print()
for k in ('2878', '3304', '2794', '3276', '3478', '3716'):
    print(f'--- cat{k}: {restores[k]["text"][:150]} … {restores[k]["text"][-80:]}')
print(f'\ncut {len(res["cut"])} (авто {len(auto)} + концертных {len(conc_cuts)}), restore {len(restores)}, none 1')
