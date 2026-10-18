# -*- coding: utf-8 -*-
"""Ф6 приёмка: регрессионная сверка финального каталога со старым каталогом движка
(reference/catalog_old_from_db.json = слой catalog_all_v4.json старой gosfilmofond.db, 6857 записей).
Сопоставление старый → новый: норм. титул (+без скобок) и год (±1), затем по началу аннотации, затем по схожести титула.
Классификация аннотаций у пар: equal / old_prefix (обрезка старого закрыта) / old_inside (снят лид) / new_shorter (проверить) / different.
Выход: work/f6_ref_compare_v2.json, печать сводки."""
import json, re, sys, difflib
sys.path.insert(0, 'work')
import f6_p2_lib as L
from collections import Counter, defaultdict
old = json.load(open('reference/catalog_old_from_db.json', encoding='utf-8'))
new = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
def nt(s): return L.norm_m(s or '')
def base(s): return re.sub(r'\s*\([^)]*\)', '', s or '').strip()
def na(s): return re.sub(r'[^а-яa-z0-9]', '', (s or '').lower().replace('ё', 'е'))
idx = defaultdict(list)
for j, r in enumerate(new):
    for k in {nt(r['title']), nt(base(r['title']))}:
        if k: idx[(k, r['year'])].append(j)
new_ann = [na(r['annotation']) for r in new]
match = {}   # i_old -> (j_new, method)
used = Counter()
def ann_pick(i, cands):
    """из нескольких кандидатов — по схожести аннотаций"""
    ao = na(old[i]['annotation'])
    best = None; bs = -1
    for j in cands:
        s = difflib.SequenceMatcher(None, ao[:300], new_ann[j][:300]).ratio() if ao and new_ann[j] else 0
        if s > bs: bs, best = s, j
    return best
for i, r in enumerate(old):
    keys = {nt(r['title']), nt(base(r['title']))}
    cands = []
    for k in keys:
        if k: cands += idx.get((k, r['year']), [])
    cands = sorted(set(cands))
    if cands:
        match[i] = (cands[0] if len(cands) == 1 else ann_pick(i, cands), 'title+year' if len(cands) == 1 else 'title+year+ann'); continue
    for dy in (-1, 1):
        for k in keys:
            if k: cands += idx.get((k, r['year'] + dy), [])
    cands = sorted(set(cands))
    if cands:
        match[i] = (cands[0] if len(cands) == 1 else ann_pick(i, cands), 'title+year±1'); continue
# второй проход: по началу аннотации (первые 60 норм. знаков) среди ещё не сопоставленных новых записей
taken = {j for j, m in match.values()}
pref = {}
for j, a in enumerate(new_ann):
    if j in taken or len(a) < 60: continue
    pref.setdefault(a[:60], []).append(j)
for i, r in enumerate(old):
    if i in match: continue
    ao = na(r['annotation'])
    if len(ao) >= 60 and ao[:60] in pref:
        cands = [j for j in pref[ao[:60]] if abs(new[j]['year'] - r['year']) <= 2]
        if cands:
            j = cands[0] if len(cands) == 1 else ann_pick(i, cands)
            match[i] = (j, 'annotation-prefix'); taken.add(j)
# третий проход: схожесть титула (≥0.85) при том же годе среди не сопоставленных новых
byyear = defaultdict(list)
for j, r in enumerate(new):
    if j not in taken: byyear[r['year']].append(j)
for i, r in enumerate(old):
    if i in match: continue
    k = nt(base(r['title'])); best = None; bs = 0
    for dy in (0, -1, 1):
        for j in byyear.get(r['year'] + dy, []):
            s = difflib.SequenceMatcher(None, k, nt(base(new[j]['title']))).ratio()
            if s > bs: bs, best = s, j
    if best is not None and bs >= 0.85:
        match[i] = (best, f'title-fuzzy({bs:.2f})'); taken.add(best)
# четвёртый проход: окно из середины/конца аннотации старого (40 норм. знаков) ищется как подстрока в непривязанных новых аннотациях
free = [j for j in range(len(new)) if j not in taken and new_ann[j]]
for i, r in enumerate(old):
    if i in match: continue
    ao = na(r['annotation'])
    probes = [ao[k:k + 40] for k in (0, 40, 80, 120, 200) if len(ao) >= k + 40] + ([ao[-40:]] if len(ao) >= 40 else [])
    hit = None
    for pr in probes:
        cands = [j for j in free if pr in new_ann[j]]
        if len(cands) == 1: hit = cands[0]; break
        if len(cands) > 1:
            cands = [j for j in cands if abs(new[j]['year'] - r['year']) <= 2]
            if len(cands) == 1: hit = cands[0]; break
    if hit is not None:
        match[i] = (hit, 'annotation-window'); taken.add(hit); free.remove(hit)
unmatched_old = [i for i in range(len(old)) if i not in match]
matched_new = Counter(j for j, m in match.values())
multi = {j: c for j, c in matched_new.items() if c > 1}
unmatched_new = [j for j in range(len(new)) if j not in matched_new]
print('old', len(old), 'matched', len(match), 'unmatched_old', len(unmatched_old), '; new', len(new), 'matched_new', len(matched_new), 'multi-hit new', len(multi), 'unmatched_new', len(unmatched_new))
print('methods', Counter(m for j, m in match.values()))
# классификация аннотаций
cls = {}
for i, (j, m) in match.items():
    ao, an = na(old[i]['annotation']), new_ann[j]
    if not ao and not an: c = 'both-none'
    elif not ao: c = 'old-none'
    elif not an: c = 'new-none'
    elif ao == an: c = 'equal'
    elif an.startswith(ao): c = 'old_prefix'
    elif ao in an: c = 'old_inside'
    elif ao.startswith(an): c = 'new_prefix_of_old'
    elif an in ao: c = 'new_inside_old'
    else:
        # общий префикс
        k = 0
        while k < min(len(ao), len(an)) and ao[k] == an[k]: k += 1
        c = 'common_prefix' if k >= 40 else 'different'
    cls[i] = c
print('annotation classes', Counter(cls.values()))
out = {'old_file': 'reference/catalog_old_from_db.json', 'old_n': len(old), 'new_n': len(new), 'matched': len(match), 'methods': dict(Counter(m for j, m in match.values())),
       'unmatched_old': [{'i': i, 'title': old[i]['title'], 'year': old[i]['year'], 'studio': old[i]['studio'], 'ann': (old[i]['annotation'] or '')[:160]} for i in unmatched_old],
       'unmatched_new': [{'id': new[j]['id'], 'title': new[j]['title'], 'year': new[j]['year'], 'source': new[j]['source']} for j in unmatched_new],
       'multi_hit_new': [{'id': new[j]['id'], 'title': new[j]['title'], 'year': new[j]['year'], 'old': [old[i]['title'] for i, (jj, m) in match.items() if jj == j]} for j in multi],
       'pairs': [{'i': i, 'id': new[j]['id'], 'method': m, 'ann_class': cls[i]} for i, (j, m) in sorted(match.items())],
       'ann_classes': dict(Counter(cls.values()))}
json.dump(out, open('work/f6_ref_compare_v2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
