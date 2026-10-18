# -*- coding: utf-8 -*-
"""Ф6-П3в: сборка резолюции среза титров из аннотаций по спецификациям work/f6_p3v_manual.py.
Вход: state/catalog_final_v2.json, work/vN_lines.json. Выход: scripts/f6_p3v_resolution.json, work/f6_p3v_review.txt.
Проверки: срезанный текст покрыт указанными печатными строками (пробы по 14 нормализованных знаков, ≥90%), остаток начинается с
прописной/«/цифры/многоточия и кончается знаком конца предложения, без двойных пробелов; остаток-формула источника → флаг source_only."""
import json, re, sys, hashlib, datetime
sys.path.insert(0, 'work')
import f6_p2_lib as L
import f6_p3v_manual as M
src = open('work/f6_p3a_tail_scan.py', encoding='utf-8').read()
ns = {'re': re, 'L': L}; exec(src[src.index('CONCERT ='):src.index('res = []')], ns); nmap = ns['nmap']
CAT = 'state/catalog_final_v2.json'
cat = json.load(open(CAT, encoding='utf-8')); sha = hashlib.sha256(open(CAT, 'rb').read()).hexdigest()
SRC = re.compile(r'^(По (мотивам|одноименн|роману|повести|пьесе|рассказ|сказк|трем|одноимённ)|Экранизац|В основу|В фильме использован[ыа]? (сюжет|мотив)|Вариация на тему)')
def probes(tn, n=14):
    if len(tn) <= n: return [tn] if len(tn) >= 5 else []
    return [tn[j:j + n] for j in range(0, len(tn) - n + 1, 5)] + [tn[-n:]]
def covered(cut_n, ref_n):
    pr = probes(cut_n)
    if not pr: return 1.0
    return sum(1 for p in pr if p in ref_n) / len(pr)
def find_span(a, A, amap, tn):
    """найти нормализованный текст tn в аннотации; вернуть (s, e) в исходных индексах"""
    pos = A.find(tn)
    if pos < 0 or A.find(tn, pos + 1) >= 0: return None
    s = amap[pos]; e = amap[pos + len(tn) - 1] + 1
    return s, e
def extend_end(a, e):
    while e < len(a) and a[e] in '.…!?»)': e += 1
    while e < len(a) and a[e] == ' ': e += 1
    return e
def extend_start(a, s):
    while s > 0 and a[s - 1] in '«(': s -= 1
    return s
out, review, problems = [], [], []
def emit(i, cls, before, after, lines, removed, note, ops):
    r = cat[i]
    after = re.sub(r'\s+', ' ', after).strip()
    ok = bool(after) and re.match(r'^(\.\.\.|…)?[А-ЯЁA-Z0-9«„(]', after) and (re.search(r'[.!?»)…]$', after) or not re.search(r'[.!?»)…]$', before)) and '  ' not in after
    so = bool(SRC.match(after)) and len(after) <= 140 and re.sub(r'\b[А-ЯЁ]\. ', '', after).count('. ') == 0
    if not ok: problems.append((i, 'RESIDUE', after[:80], after[-40:]))
    out.append({'cat': i, 'id': r['id'], 'title': r['title'], 'source': r['source'], 'field': 'annotation', 'class': cls, 'before': before, 'after': after,
                'vol': r['source'].split('_')[0], 'lines': lines, 'removed': removed, 'note': note, 'ops': ops, 'source_only': so})
    review.append(f"cat{i} id{r['id']} {r['source'].split('_')[0]} «{r['title']}» [{cls}]{' SOURCE-ONLY' if so else ''}\n   −− {removed[:300]}\n   →→ {after[:160]}{' … ' + after[-50:] if len(after) > 210 else ''}")
for i, (P, lines) in sorted(M.PREFIX.items()):
    r = cat[i]; a = r['annotation']; v = r['source'].split('_')[0]; Ls = L.lines(v); A, amap = nmap(a)
    if isinstance(P, str):
        k = a.find(P); assert k > 0 and a.find(P, k + 1) < 0, (i, 'start')
        oi = k
    else:
        pn = nmap(Ls[P][1])[0][:16]; assert len(pn) >= 8, (i, 'P short', pn)
        pos = A.find(pn); assert pos > 0 and A.find(pn, pos + 1) < 0, (i, 'P not unique/found', pn, pos)
        oi = amap[pos]
        if Ls[P][1].lstrip().startswith('...') and a[oi - 3:oi] == '...': oi -= 3
        elif a[oi - 1:oi] in '«„(': oi -= 1
    cut, after = a[:oi], a[oi:]
    ref = nmap(' '.join(Ls[k][1] for k in lines))[0]
    cov = covered(nmap(cut)[0], ref)
    if cov < 0.9: problems.append((i, 'COVER', round(cov, 2), cut[:100]))
    emit(i, 'cred-prefix' if i != 5354 else 'junk-prefix', a, after, lines, cut.strip(), M.NOTES.get(i), [{'op': 'cut_prefix', 'until': ('start:' + P) if isinstance(P, str) else f'@{P}', 'chars': len(cut)}])
for i, (P, k) in sorted(M.MID.items()):
    r = cat[i]; a = r['annotation']; v = r['source'].split('_')[0]; Ls = L.lines(v); A, amap = nmap(a)
    pn = nmap(Ls[P][1])[0][:16]; pos = A.find(pn); assert pos > 0 and A.find(pn, pos + 1) < 0, (i, 'MID P', pn)
    oi = amap[pos]
    if a[oi - 1:oi] in '«„(': oi -= 1
    cut, after = a[:oi], a[oi:]
    cov = covered(nmap(cut)[0], nmap(Ls[k][1])[0])
    if cov < 0.9: problems.append((i, 'COVER-MID', round(cov, 2), cut[:100]))
    emit(i, 'cred-prefix', a, after, [k], cut.strip(), M.NOTES.get(i), [{'op': 'cut_prefix', 'until': f'@{P}', 'chars': len(cut), 'midline': k}])
for i, specs in sorted(M.INNER.items()):
    r = cat[i]; a0 = r['annotation']; v = r['source'].split('_')[0]; Ls = L.lines(v)
    a = a0; removed = []; ops = []; lines = []
    for sp in specs:
        A, amap = nmap(a)
        if 'text' in sp:
            t = sp['text']; k = a.find(t); assert k >= 0 and a.find(t, k + 1) < 0, (i, 'INNER text', t)
            s, e = k, k + len(t)
            cov = covered(nmap(t)[0], nmap(Ls[sp['line']][1])[0])
        else:
            tn = nmap(Ls[sp['line']][1])[0]; sp_ = find_span(a, A, amap, tn)
            assert sp_, (i, 'INNER line not found', sp['line'], tn[:40])
            s, e = sp_; s = extend_start(a, s); e = extend_end(a, e); cov = 1.0
        if cov < 0.9: problems.append((i, 'COVER-INNER', round(cov, 2), a[s:e][:100]))
        removed.append(a[s:e].strip()); lines.append(sp['line'])
        assert s > 0, (i, 'inner at start')
        a = a[:s] + a[e:]
        ops.append({'op': 'remove', 'line': f"@{sp['line']}", 'chars': e - s, 'note': sp.get('note')})
    emit(i, 'cred-inner', a0, a, lines, ' | '.join(removed), M.NOTES.get(i), ops)
out.sort(key=lambda x: x['cat'])
assert len({x['cat'] for x in out}) == len(out)
from collections import Counter
meta = {'package': 'Ф6-П3в', 'date': datetime.date.today().isoformat(), 'input': CAT, 'input_sha256': sha, 'input_records': len(cat),
        'counts': dict(Counter(x['class'] for x in out)), 'records': len(out), 'source_only': [x['cat'] for x in out if x['source_only']],
        'basis': 'решение владельца 04.09.2026 («срезать») по §7 п.1 ВЕТО_Ф6_П3а; спецификации work/f6_p3v_manual.py (по печати); сканы work/f6_p3v_scan*.py'}
json.dump({'_meta': meta, 'set': out}, open('scripts/f6_p3v_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open('work/f6_p3v_review.txt', 'w', encoding='utf-8').write('\n'.join(review))
print(meta['counts'], 'records', len(out), 'source_only', meta['source_only'])
print('PROBLEMS', len(problems))
for p in problems: print('  ', p)
