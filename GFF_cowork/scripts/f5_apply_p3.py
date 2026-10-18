# -*- coding: utf-8 -*-
"""Ф5 П3 год-пакет — apply, режим Cowork. Запуск из КОРНЯ:
python3 scripts/f5_apply_p3.py <N=1|2|3> <vol1> [vol2 ...]
Читает scripts/y{N}_resolution.json:
  {"sanction": {cat: [год_до, год_после, строка, "а"/"а+б"/"б", "verbatim"]},
   "confirm":  {cat: {"note": ..., "line": ..., "verbatim": ...}},
   "notfound": {cat: {"note": ...}}}
Классы: санкция (правка year) / подтверждён-без-правки (закрыть позицию) /
недобор (note, остаётся). Стоп-ассерт: страи запрещены во всех классах.
Порядок: пред-ассерты -> И1-И5 -> бэкапы -> запись state/catalog_f5_y{N}.json +
очередь -> предыдущий каталог в backups/ -> протокол scripts/_y{N}_sanction.json."""
import json, copy, os, shutil, sys, datetime
from collections import Counter

N = int(sys.argv[1]); VOLS = set(sys.argv[2:]); assert VOLS, "укажи тома"
PREV = {1: 'g14', 2: 'y1', 3: 'y2'}[N]
SRC_CAT = f'state/catalog_f5_{PREV}.json'
SRC_Q, SRC_AL = 'state/Ф5_очередь_docx.json', 'state/alignment_v17.json'

WIN = {'v1': (1917, 1935), 'v2': (1929, 1957), 'v3': (1957, 1963), 'v4': (1963, 1965),
       'v5': (1965, 1967), 'v6': (1967, 1969), 'v7': (1969, 1971), 'v8': (1971, 1973),
       'v9': (1973, 1975), 'v10': (1975, 1977), 'v11': (1977, 1979), 'v12': (1979, 1981),
       'v13': (1981, 1983), 'v14': (1983, 1985), 'v15': (1985, 1987)}

res = json.load(open(f'scripts/y{N}_resolution.json', encoding='utf-8'))
SAN = {int(k): tuple(v) for k, v in res['sanction'].items()}
CONF = {int(k): v for k, v in res.get('confirm', {}).items()}
NF = {int(k): v for k, v in res.get('notfound', {}).items()}

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q = json.load(open(SRC_Q, encoding='utf-8'))
al = json.load(open(SRC_AL, encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}

exp = {}   # cat -> ожидаемое текущее значение year
for e in q['year_empty']:
    if e.get('stray'): continue
    if e['vol'].split('_')[0] in VOLS:
        exp[e['cat']] = 1905 if e['cat'] == 854 else None
for e in q['year_candidates']:
    if cat0[e['cat']]['source'].split('_')[0] in VOLS:
        exp[e['cat']] = e['year_record']
if N == 1:
    assert 'v2' in VOLS
    exp[1186] = 1929   # внеочередная санкция, вето-3 §4.1

touched = set(SAN) | set(CONF) | set(NF)

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, "alignment"
assert touched == set(exp), f"классы != цели пакета: {touched ^ set(exp)}"
assert not (set(SAN) & set(CONF)) and not (set(SAN) & set(NF)) and not (set(CONF) & set(NF)), "пересечение классов"
assert not (touched & strays), f"СТРАИ: {touched & strays}"
for c, v in exp.items():
    assert cat0[c]['year'] == v, f"cat{c}: year {cat0[c]['year']!r} != ожидаемого {v!r}"
    assert cat0[c]['source'].split('_')[0] in VOLS, f"cat{c}: source"
for c, (y0, y1, ln, src, verb) in SAN.items():
    assert y0 == exp[c], f"cat{c}: год_до {y0!r} != {exp[c]!r}"
    lo, hi = WIN[cat0[c]['source'].split('_')[0]]
    assert isinstance(y1, int) and lo <= y1 <= hi, f"cat{c}: год {y1} вне окна [{lo},{hi}]"
    assert src in ('а', 'а+б', 'б'), f"cat{c}: источник {src!r}"
    assert y1 != y0, f"cat{c}: год не меняется — это класс confirm"

snap_b = [{k: v for k, v in r.items() if k != 'year'} for r in cat0]
year_b = [r['year'] for r in cat0]

cat1 = copy.deepcopy(cat0)
for c, (y0, y1, *_ ) in SAN.items():
    cat1[c]['year'] = y1

# ── Инварианты ──
assert len(cat1) == 7232, "И1"
changed = [i for i in range(7232) if cat1[i]['year'] != year_b[i]]
assert set(changed) == set(SAN), f"И2: {set(changed) ^ set(SAN)}"
for c in changed:
    assert cat1[c]['year'] == SAN[c][1], f"И2: cat{c}"
snap_a = [{k: v for k, v in r.items() if k != 'year'} for r in cat1]
assert json.dumps(snap_b, ensure_ascii=False, sort_keys=True) == \
       json.dumps(snap_a, ensure_ascii=False, sort_keys=True), "И3"
assert Counter(r['source'] for r in cat0) == Counter(r['source'] for r in cat1), "И4"
assert [(r['title'], r['source']) for r in cat0] == \
       [(r['title'], r['source']) for r in cat1], "И5"

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
shutil.copy2(SRC_CAT, f'backups/catalog_f5_{PREV}_{ts}.json')
shutil.copy2(SRC_Q, f'backups/Ф5_очередь_docx_{PREV}_{ts}.json')

with open(f'state/catalog_f5_y{N}.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)

# ── Очередь: sanction/confirm удалить; notfound — note; страи и чужие тома нетронуты ──
closed = set(SAN) | set(CONF)
for sec in ('year_empty', 'year_candidates'):
    out = []
    for e in q[sec]:
        if e['cat'] in closed and e['cat'] != 1186:
            continue
        if e['cat'] in NF:
            e = dict(e); e.update(NF[e['cat']])
        out.append(e)
    q[sec] = out
with open(SRC_Q, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

os.replace(SRC_CAT, f'backups/catalog_f5_{PREV}.json')

json.dump({str(c): {'before': v[0], 'after': v[1], 'line': v[2], 'src': v[3], 'head': v[4]}
           for c, v in SAN.items()} |
          {str(c): {'confirmed': True, **v} for c, v in CONF.items()} |
          {str(c): {'notfound': True, **v} for c, v in NF.items()},
          open(f'scripts/_y{N}_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"OK y{N}: правок year {len(SAN)}; подтверждено без правки {len(CONF)}; "
      f"недоборов {len(NF)}; И1-И5 пройдены; страёв в классах нет.")
for sec in ('year_empty', 'year_candidates'):
    a = sum(1 for e in q[sec] if not e.get('stray'))
    s = sum(1 for e in q[sec] if e.get('stray'))
    print(f"очередь {sec}: {len(q[sec])} (активных {a}, страёв {s})")
