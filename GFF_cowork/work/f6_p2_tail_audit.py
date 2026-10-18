# аудит хвостов резолюции: (A) хвост начинается с печатной строки-продолжения (строчная буква) — ложный срез прозы;
# (B) after обрывается на букве, а в печати за строкой-обрывом (через мусор) идёт продолжение прозы — кандидат RESTORE
import sys, json, re
sys.path.insert(0, 'work')
import f6_p2_lib as L
cat = json.load(open('state/catalog_f6_p1.json', encoding='utf-8'))
res = json.load(open('scripts/f6_p2_resolution.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p2_ann_scan.json', encoding='utf-8'))}
def nmap(s):
    out = []; idx = []
    for i, ch in enumerate(s.lower().replace('ё', 'е').translate(L._TR)):
        if ('а' <= ch <= 'я') or ('a' <= ch <= 'z') or ('0' <= ch <= '9'): out.append(ch); idx.append(i)
    return ''.join(out), idx
A = []; B = []
for e in res['set']:
    if e['field'] != 'annotation' or not e['after'] or 'tail' not in e['class']: continue
    b, a = e['before'], e['after']; nb, idx = nmap(b); na, _ = nmap(a)
    q = nb.find(na) if 'prefix' not in e['class'] else -1
    if q < 0: continue
    t0 = q + len(na)
    if t0 >= len(nb): continue
    tail_raw = b[idx[t0]:]; tn = nb[t0:]
    x = scan.get(e['cat']); Ls = L.lines(e['vol'])
    lo = x['h'] if x else 0; hi = (x['e'] + 6) if x else len(Ls) - 1
    hit = None
    for j in range(lo, min(hi, len(Ls) - 1) + 1):
        ln, _ = nmap(Ls[j][1])
        if len(tn) >= 12 and tn[:12] in ln: hit = j; break
    if hit is not None:
        t = Ls[hit][1].lstrip()
        if re.match(r'^[а-яё]', t) and L.kind(t) in ('prize', 'prose', 'cred') and len(tn) > 30:
            A.append((e['cat'], e['class'], hit, t[:80], tail_raw[:80]))
    # (B)
    if re.search(r'[а-яёА-ЯЁ]$', a) and x:
        lp = x.get('last_prose_line')
        if lp:
            for j in range(lp + 1, min(lp + 5, len(Ls))):
                t = Ls[j][1].lstrip()
                if L.kind(t) == 'junk': continue
                if re.match(r'^[а-яё]', t) and L.kind(t) == 'prose':
                    B.append((e['cat'], e['class'], lp, j, a[-40:], t[:80]))
                break
print('A (ложный срез прозы-продолжения):', len(A))
for r in A: print('  ', r)
print('B (обрыв + продолжение в печати):', len(B))
for r in B: print('  ', r)
json.dump({'A': A, 'B': B}, open('work/f6_p2_tail_audit.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
