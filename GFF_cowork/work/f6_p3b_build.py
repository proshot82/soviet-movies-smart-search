# -*- coding: utf-8 -*-
"""Ф6-П3б: мини-пакет по итогам финальной регрессии (после П3а) → scripts/f6_p3b_resolution.json.
 gap-pre  — утерянные формулы источника «В фильме использованы мотивы…» (по kind() П2 — проза; печать: строка перед прозой): cat2485, cat6700;
 cred-cut — титры, поглощённые аннотацией (список ролей / титровое примечание перед формулой источника): cat2076, cat4732.
Номера cat — индексы state/catalog_final_v2.json."""
import json, re, sys, hashlib, datetime
sys.path.insert(0, 'work')
import f6_p2_lib as L
from f6_p3_clean import clean, join_lines
src = open('work/f6_p3a_tail_scan.py', encoding='utf-8').read()
ns = {'re': re, 'L': L}; exec(src[src.index('JUNKLINE ='):src.index('res = []')], ns); nmap = ns['nmap']
CAT_PATH = 'state/catalog_final_v2.json'
cat = json.load(open(CAT_PATH, encoding='utf-8')); sha = hashlib.sha256(open(CAT_PATH, 'rb').read()).hexdigest()
gap = {x['cat']: x for x in json.load(open('work/f6_ref_gap_scan_v2.json', encoding='utf-8'))}
MARK = re.compile(r'(Авт\. сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Фильм дублирован|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер)')
PRE = {2485: [9322], 6700: [2096]}
CUT = {2076: {'drop_prefix_lines': [6358, 6359], 'note': 'подзаголовок и список ролей вставного сказа («В сказе о Гагарке. Г Юдин (Гурий Гагарка), …») — титры (В ролях), поглощённые аннотацией; аннотация начинается с логлайна @6360'},
       4732: {'drop_prefix_lines': [1512, 1514], 'note': 'титровое примечание «Лошади конных заводов…» @1512 и хвост списка ролей @1514 (продолжение «В ролях» @1513), поглощённые аннотацией; печатной прозы нет — остаётся формула источника @1515 (реестр: source-only)'}}
res = []
for i, lines in PRE.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']; g = gap[i]
    for k in lines: assert g['h2'] < k < g['k1'], f'cat{i}: @{k} не перед началом аннотации'
    raw = [L.lines(v)[k][1] for k in lines]; t, ops, manual = clean(v, join_lines(raw), i)
    assert not manual and not MARK.search(t) and L.kind(raw[0]) == 'prose' and nmap(t)[0][:20] not in nmap(b)[0]
    res.append({'cat': i, 'id': r['id'], 'title': r['title'], 'source': r['source'], 'field': 'annotation', 'class': 'gap-pre', 'before': b, 'after': t + ' ' + b, 'vol': v, 'lines': lines, 'raw': raw,
                'note': 'формула источника «В фильме использованы мотивы…» перед прозой утеряна (по kind() П2 — проза; в П3а отфильтрована как титроподобная); восстановлена по печати', 'ops': [('PREFIX', t[:70], '')] + ops})
for i, sp in CUT.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']; g = gap[i]; Ls = L.lines(v)
    raw = [Ls[k][1] for k in sp['drop_prefix_lines']]
    for k, t in zip(sp['drop_prefix_lines'], raw): assert g['h2'] < k < g['E'] and (L.kind(t) == 'cred' or k in (6358, 1512)), f'cat{i}: @{k} kind={L.kind(t)}'   # 6358 — подзаголовок списка ролей, 1512 — титровое примечание в блоке титров (перед «В ролях»)
    # аннотация = [титровые строки] + остаток; найти остаток по началу следующей печатной строки (проза)
    nxt = Ls[sp['drop_prefix_lines'][-1] + 1][1]; nn = nmap(nxt)[0][:16]; B, bidx = nmap(b)
    p = B.find(nn); assert p > 0 and B.count(nn) == 1, f'cat{i}: якорь остатка не найден'
    pos = bidx[p]; dropped = b[:pos].strip(); a = b[pos:].strip()
    # снятое должно покрываться титровыми строками печати (пробы)
    dn = nmap(dropped)[0]; ln = ''.join(nmap(t)[0] for t in raw)
    pr = [dn[k:k + 14] for k in range(0, max(1, len(dn) - 14), 20)]
    assert sum(1 for x in pr if x in ln) * 2 >= len(pr), f'cat{i}: снятое не покрыто титровыми строками'
    assert L.kind(nxt) == 'prose' and a and not MARK.search(a) and re.search(r'[.!?…»)]$', a)
    res.append({'cat': i, 'id': r['id'], 'title': r['title'], 'source': r['source'], 'field': 'annotation', 'class': 'cred-cut', 'before': b, 'after': a, 'vol': v, 'lines': sp['drop_prefix_lines'], 'raw': raw,
                'note': sp['note'], 'ops': [('DROP-PREFIX', dropped[:90] + ('…' if len(dropped) > 90 else ''), '')]})
from collections import Counter
meta = {'package': 'Ф6-П3б', 'date': datetime.date.today().isoformat(), 'input': CAT_PATH, 'input_sha256': sha, 'input_records': len(cat), 'counts': dict(Counter(x['class'] for x in res)),
        'basis': 'финальная регрессия аннотаций (work/f6_ref_lost3.py: in_article/prose) и скан титроподобных предложений (work/f6_p3b_cred_cands.json) после П3а; каждая позиция верифицирована по печати'}
json.dump({'_meta': meta, 'set': res}, open('scripts/f6_p3b_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for x in res: print(f"cat{x['cat']} [{x['class']}] {x['ops'][0]}\n   AFTER: {x['after'][:220]}")
print(meta['counts'])
