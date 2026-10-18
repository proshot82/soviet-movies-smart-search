# -*- coding: utf-8 -*-
"""Ф6-П3: печатно-обоснованный срез призового хвоста. Для кандидатов (work/f6_p3_prize_scan.json, tail != None):
статья по локализации tail-scan (h/e); печатные строки после последней прозы, классифицированные как призовые (PRIZE2/AW);
хвост = суффикс аннотации от первого вхождения начала первой призовой строки; проверка: конец остатка == конец последней печатной прозы."""
import json, re, sys
sys.path.insert(0, 'work')
import f6_p2_lib as L
src = open('work/f6_p3_tail_scan.py', encoding='utf-8').read()
ns = {'re': re, 'L': L}; exec(src[src.index('JUNKLINE ='):src.index('res = []')], ns)
PRIZE2, is_junk, is_headlike, verified_head, nmap = ns['PRIZE2'], ns['is_junk'], ns['is_headlike'], ns['verified_head'], ns['nmap']
AW = re.compile(open('work/f6_p3_prize_scan.py', encoding='utf-8').read().split("AW = re.compile(r'")[1].split("', re.I)")[0].replace('(удостоен|', '(Гэсударственн(ая|ой) преми|«Ника-\\d\\d»|удостоен|'), re.I)
cat = json.load(open('state/catalog_f6_p2e.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p3_tail_scan.json', encoding='utf-8'))}
cands = [x for x in json.load(open('work/f6_p3_prize_scan.json', encoding='utf-8')) if x['tail']]
EXTRA = [4250, 4770, 6434, 6705, 6865, 6925, 6072, 1467, 1802, 2448]
have = {x['cat'] for x in cands}
cands += [{'cat': c, 'title': cat[c]['title'], 'tail': ''} for c in EXTRA if c not in have]
SKIP = {374, 1182, 3154, 4721, 6033, 6862}
out = []
for x in cands:
    i = x['cat']
    if i in SKIP: continue
    a = cat[i]['annotation']; A_n, A_idx = nmap(a)
    s = scan[i]; vol = s['vol']; Ls = L.lines(vol); hs = L.headset(vol)
    h, e = s.get('h'), s.get('e')
    rec = {'cat': i, 'vol': vol, 'title': x['title'], 'h': h, 'e': e}
    if h is None: rec['status'] = 'UNLOCATED'; out.append(rec); continue
    # классификация печатных строк статьи
    kinds = []
    for k in range(h + 1, min(e + 3, len(Ls))):
        t = Ls[k][1]
        if is_junk(t): continue
        if k >= e and (verified_head(vol, k, hs, Ls) or is_headlike(t)): break
        kd = L.kind(t)
        if kd == 'prose' and (PRIZE2.match(t) or AW.search(t[:160])): kd = 'prize'
        kinds.append((k, kd, t))
    prose_lines = [k for k, kd, t in kinds if kd == 'prose']
    prize_lines = [(k, t) for k, kd, t in kinds if kd == 'prize']
    rec['kinds'] = [(k, kd) for k, kd, t in kinds]
    if not prize_lines: rec['status'] = 'NO-PRINT-PRIZE'; out.append(rec); continue
    # первая призовая строка после последней прозы (или любая, если призы внутри)
    firstpz = prize_lines[0][0]
    before_pz = [k for k in prose_lines if k < firstpz]
    lastp = before_pz[-1] if before_pz else (prose_lines[-1] if prose_lines else h)
    after = [(k, t) for k, t in prize_lines if k > lastp]
    first = after[0] if after else prize_lines[0]
    fn = nmap(first[1])[0]
    key = fn[:20]
    p = A_n.find(key)
    if p < 0:
        # призовая строка может начинаться внутри печатной строки прозы (cat2593: «Довженко удостоен…» отдельной строкой) — пробуем по AW-предложению хвоста
        tn = nmap(x['tail'])[0][:20]; p = A_n.find(tn) if tn else -1; rec['note'] = 'по AW-хвосту'
    if p < 0: rec['status'] = 'TAIL-NOT-FOUND'; rec['first_prize_line'] = (first[0], first[1][:120]); out.append(rec); continue
    cut = A_idx[p]
    # откат к границе предложения: назад до пробела после знака конца предложения
    m = None
    for mm in re.finditer(r'(?<=[.!?…»)])\s+', a[:cut + 1]): m = mm
    cut2 = m.end() if m and cut - m.end() <= 2 else cut
    rest = a[:cut2].rstrip(); tail = a[cut2:]
    rn = nmap(rest)[0]
    # проверка: конец остатка совпадает с концом последней печатной прозы
    ok = None; lp = None
    if prose_lines:
        lp = lastp; ln = nmap(Ls[lp][1])[0]
        ok = len(rn) >= 20 and ln.endswith(rn[-20:])
        if not ok and len(rn) >= 20:
            # остаток может кончаться внутри печатной строки (проза + приз в одной строке) — тогда вхождение
            ok = rn[-20:] in ln and 'inline' or False
    rec.update({'status': 'OK' if ok else ('INLINE' if ok == 'inline' else 'REST-END-MISMATCH'), 'rest_end': rest[-90:], 'tail': tail, 'last_prose_line': lp,
                'prize_lines': [(k, t[:160]) for k, t in prize_lines], 'rest_nonempty': len(rest) >= 40})
    out.append(rec)
json.dump(out, open('work/f6_p3_prize_cut.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(r['status'] for r in out))
for r in out:
    print(f"\ncat{r['cat']} {r['vol']} «{r['title']}» [{r['status']}] lp={r.get('last_prose_line')} kinds={r.get('kinds')}")
    if 'tail' in r:
        print('   REST-END:', repr(r['rest_end']))
        print('   TAIL:', repr(r['tail'][:400]))
        for k, t in r['prize_lines']: print(f'   PRIZE @{k}: {t}')
