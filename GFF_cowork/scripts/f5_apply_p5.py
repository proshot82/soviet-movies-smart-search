# -*- coding: utf-8 -*-
"""Ф5 П5 студии — apply, режим Cowork. Запуск из КОРНЯ:
python3 scripts/f5_apply_p5.py <N=1|2|3|4>
Читает scripts/s{N}_resolution.json:
  {"set": {cat: {"before": str|null, "after": str|null, "vol": str|null,
                 "line": int|[int,...]|null, "class": str, "note": str}},
   "confirm": {cat: {"note"}}, "notfound": {cat: {"note"}}}
Операции только по полю studio. before сверяется байт-в-байт (анти-фабрикация
механикой). Стоп-ассерт: страи запрещены. Порядок: пред-ассерты -> И1-И5 ->
бэкапы -> state/catalog_f5_s{N}.json + очередь -> предыдущий каталог в backups/
-> протокол scripts/_s{N}_sanction.json."""
import json, copy, os, shutil, sys, datetime
from collections import Counter

N = int(sys.argv[1])
PREV = {1: 'a5', 2: 's1', 3: 's2', 4: 's3', 5: 's4', 6: 's5'}[N]
SRC_CAT = f'state/catalog_f5_{PREV}.json'
SRC_Q, SRC_AL = 'state/Ф5_очередь_docx.json', 'state/alignment_v17.json'
VALID_CLASSES = {'shift', 'fill', 'copro', 'ocr', 'junk', 'tail', 'none'}

res = json.load(open(f'scripts/s{N}_resolution.json', encoding='utf-8'))
SET = {int(k): v for k, v in res.get('set', {}).items()}
CONF = {int(k): v for k, v in res.get('confirm', {}).items()}
NF = {int(k): v for k, v in res.get('notfound', {}).items()}

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q = json.load(open(SRC_Q, encoding='utf-8'))
al = json.load(open(SRC_AL, encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}

touched = set(SET) | set(CONF) | set(NF)
sets = [set(SET), set(CONF), set(NF)]

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, "alignment"
for i, s1 in enumerate(sets):
    for s2 in sets[i+1:]:
        assert not (s1 & s2), f"пересечение классов: {s1 & s2}"
assert not (touched & strays), f"СТРАИ: {touched & strays}"
for c, v in SET.items():
    cur = cat0[c].get('studio')
    assert v['class'] in VALID_CLASSES, f"cat{c}: класс {v['class']!r}"
    assert cur == v.get('before'), f"cat{c}: before не совпал: {cur!r} != {v.get('before')!r}"
    assert v.get('after') != v.get('before'), f"cat{c}: after==before"
    if v.get('after') is None:
        assert v['class'] == 'none' and v.get('note'), f"cat{c}: after=null без class=none/note"
    else:
        assert isinstance(v['after'], str) and v['after'].strip(), f"cat{c}: пустой after"
        assert v['after'] == v['after'].strip(), f"cat{c}: after с крайними пробелами"
    if v['class'] == 'fill':
        assert v.get('before') is None, f"cat{c}: fill при непустом before"

studio_b = [r.get('studio') for r in cat0]
snap_b = [{k: w for k, w in r.items() if k != 'studio'} for r in cat0]

cat1 = copy.deepcopy(cat0)
for c, v in SET.items():
    cat1[c]['studio'] = v.get('after')

# ── Инварианты ──
assert len(cat1) == 7232, "И1"
changed = [i for i in range(7232) if cat1[i].get('studio') != studio_b[i]]
assert set(changed) == set(SET), f"И2: {set(changed) ^ set(SET)}"
snap_a = [{k: w for k, w in r.items() if k != 'studio'} for r in cat1]
assert json.dumps(snap_b, ensure_ascii=False, sort_keys=True) == \
       json.dumps(snap_a, ensure_ascii=False, sort_keys=True), "И3"
assert Counter(r['source'] for r in cat0) == Counter(r['source'] for r in cat1), "И4"
assert [(r['title'], r['source']) for r in cat0] == \
       [(r['title'], r['source']) for r in cat1], "И5"

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
shutil.copy2(SRC_CAT, f'backups/catalog_f5_{PREV}_{ts}.json')
shutil.copy2(SRC_Q, f'backups/Ф5_очередь_docx_{PREV}_{ts}.json')

with open(f'state/catalog_f5_s{N}.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)

closed = set(SET) | set(CONF)
for sec in ('studio_empty', 'studio_flags'):
    out = []
    for e in q.get(sec, []):
        if e['cat'] in closed:
            continue
        if e['cat'] in NF:
            e = dict(e); e.update(NF[e['cat']])
        out.append(e)
    q[sec] = out
with open(SRC_Q, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

os.replace(SRC_CAT, f'backups/catalog_f5_{PREV}.json')

prot = {}
for c, v in SET.items():
    prot[str(c)] = {'op': 'set', **v}
for c, v in CONF.items():
    prot[str(c)] = {'op': 'confirm', **v}
for c, v in NF.items():
    prot[str(c)] = {'op': 'notfound', **v}
json.dump(prot, open(f'scripts/_s{N}_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

by_cls = Counter(v['class'] for v in SET.values())
print(f"OK s{N}: set {len(SET)} {dict(by_cls)}, confirm {len(CONF)}, notfound {len(NF)};"
      f" И1-И5 пройдены; страёв в классах нет.")
print(f"очередь: studio_empty {len(q.get('studio_empty', []))}, studio_flags {len(q.get('studio_flags', []))}")
