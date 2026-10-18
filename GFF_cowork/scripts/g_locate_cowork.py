# -*- coding: utf-8 -*-
"""Ф5 добор genre — локализация записей в томе, режим Cowork (относительные пути).
Запуск из КОРНЯ папки: python3 scripts/g_locate_cowork.py work/v6_lines.json work/g6_targets.json [cat] [ctx]
targets-JSON: [[cat, "метка", "ИГЛА"], ...] — игла прогоняется той же norm, что и стог.
Нормализация: лат->кир, Ё->Е, Й->И, 0->О, °->О, 4->Ч, схлопывание Н->П (гомоглиф П↔Н),
снятие пунктуации/пробелов (ловит внутрисловные разрывы). norm_base — без 4/Н-схлопывания."""
import json, re, sys

LAT2CYR = str.maketrans({
    'A':'А','B':'В','C':'С','E':'Е','H':'Н','K':'К','M':'М','O':'О','P':'Р',
    'T':'Т','X':'Х','Y':'У','I':'1','L':'Л','D':'Д','N':'П','U':'И','R':'Г',
    'a':'а','b':'ь','c':'с','e':'е','h':'н','k':'к','m':'м','o':'о','p':'р',
    'x':'х','y':'у','u':'и','n':'п','r':'г','t':'т','i':'і','d':'д','l':'л',
    'Ё':'Е','ё':'е','Й':'И','й':'и',
})

def norm_base(s):
    s = s.upper().translate(LAT2CYR)
    s = s.replace('Ё','Е').replace('Й','И')
    s = s.replace('0','О').replace('°','О')
    s = re.sub(r'[^А-ЯІ0-9]', '', s)
    return s

def norm(s):
    s = norm_base(s)
    s = s.replace('4','Ч').replace('Н','П')   # гомоглифы 4↔Ч, П↔Н (схлопывание классов)
    return s

def locate(nl, needle_norm):
    hits = []
    for i, s in enumerate(nl):
        if needle_norm and needle_norm in s:
            hits.append(('line', i))
    for i in range(len(nl) - 1):
        j2 = nl[i] + nl[i+1]
        if needle_norm in j2 and not (needle_norm in nl[i] or needle_norm in nl[i+1]):
            hits.append(('join2', i))
    return hits

if __name__ == '__main__':
    lines = json.load(open(sys.argv[1], encoding='utf-8'))
    targets = json.load(open(sys.argv[2], encoding='utf-8'))
    only = int(sys.argv[3]) if len(sys.argv) > 3 else None
    ctx = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    nl = [norm(t) for _, t, _ in lines]
    for cat, label, needle in targets:
        if only and cat != only:
            continue
        hits = locate(nl, norm(needle))
        print(f"\n===== cat{cat} «{label}» игла={needle!r} → {len(hits)} совпад.")
        for kind, i in hits[:20]:
            print(f"  --- {kind} @{i} [{lines[i][2]}]")
            for j in range(max(0, i-1), min(len(lines), i+ctx)):
                t = lines[j][1]
                if t:
                    print(f"    {j}: {t[:220]}")
