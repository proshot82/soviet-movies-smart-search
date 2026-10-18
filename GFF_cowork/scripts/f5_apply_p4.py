# -*- coding: utf-8 -*-
"""Ф5 П4 аннотации — apply, режим Cowork. Запуск из КОРНЯ:
python3 scripts/f5_apply_p4.py <N=1|2|3|4>
Читает scripts/a{N}_resolution.json:
  {"cut": {cat: {"lead": str|null, "tail": str|null, "class": str}},
   "restore": {cat: {"text", "vol", "lines", "note"}},
   "none": {cat: {"note"}}, "confirm": {cat: {"note"}}, "notfound": {cat: {"note"}}}
Операции только по полю annotation. Срез — точный префикс/суффикс (анти-фабрикация
механикой), restore — verbatim из тома, none — None. Стоп-ассерт: страи запрещены.
Порядок: пред-ассерты -> И1-И5 -> бэкапы -> state/catalog_f5_a{N}.json + очередь ->
предыдущий каталог в backups/ -> протокол scripts/_a{N}_sanction.json."""
import json, copy, os, shutil, sys, datetime
from collections import Counter

N = int(sys.argv[1])
PREV = {1: 'y3', 2: 'a1', 3: 'a2', 4: 'a3', 5: 'a4'}[N]
SRC_CAT = f'state/catalog_f5_{PREV}.json'
SRC_Q, SRC_AL = 'state/Ф5_очередь_docx.json', 'state/alignment_v17.json'

# Точечные цели a1 (фиксированы хендоффом П4 §2 + сдвиговые случаи)
A1_QUEUE = {388, 464, 470, 2024, 2525, 2739, 3318, 5244, 5890, 6966, 3554, 1186}
A1_CUTS = {1184, 4767, 5456, 5468, 5606, 5645, 5894, 6334, 6335, 6546, 7230, 7231}

res = json.load(open(f'scripts/a{N}_resolution.json', encoding='utf-8'))
CUT = {int(k): v for k, v in res.get('cut', {}).items()}
RST = {int(k): v for k, v in res.get('restore', {}).items()}
NONE_ = {int(k): v for k, v in res.get('none', {}).items()}
CONF = {int(k): v for k, v in res.get('confirm', {}).items()}
NF = {int(k): v for k, v in res.get('notfound', {}).items()}

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q = json.load(open(SRC_Q, encoding='utf-8'))
al = json.load(open(SRC_AL, encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}

touched = set(CUT) | set(RST) | set(NONE_) | set(CONF) | set(NF)
sets = [set(CUT), set(RST), set(NONE_), set(CONF), set(NF)]

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, "alignment"
for i, s1 in enumerate(sets):
    for s2 in sets[i+1:]:
        assert not (s1 & s2), f"пересечение классов: {s1 & s2}"
assert not (touched & strays), f"СТРАИ: {touched & strays}"
if N == 1:
    assert set(RST) | set(NONE_) | set(CONF) | set(NF) == A1_QUEUE | (set(RST) - A1_QUEUE), "очередь a1 закрыта не вся"
    assert A1_QUEUE <= touched, f"недостача очереди: {A1_QUEUE - touched}"
    assert set(CUT) == A1_CUTS, f"cut-набор a1: {set(CUT) ^ A1_CUTS}"

new_ann = {}
lower_starts = []
for c, v in CUT.items():
    a = cat0[c]['annotation']
    assert isinstance(a, str) and a, f"cat{c}: пустая аннотация под срез"
    lead, tail, mids = v.get('lead'), v.get('tail'), v.get('mid') or []
    assert lead or tail or mids, f"cat{c}: пустой срез"
    if lead:
        assert a.startswith(lead), f"cat{c}: lead не префикс"
        a = a[len(lead):]
    if tail:
        assert a.endswith(tail), f"cat{c}: tail не суффикс"
        a = a[:len(a)-len(tail)]
    for sub in mids:
        assert a.count(sub) == 1, f"cat{c}: mid-вставка неоднозначна"
        j = a.find(sub)
        left, right = a[:j].rstrip(), a[j+len(sub):].lstrip()
        if left.endswith('-') and right[:1].islower():
            a = left[:-1] + right           # склейка дефисного переноса
        else:
            a = left + ' ' + right
    a = a.strip()
    STUB_OK = __import__('re').search(r'(Фильм не сохранился|Содержание не установлено|Авторы и содержание не установлены)', a) or __import__('re').match(r'(По\s|Экранизация|Триптих|О\s|Об\s)', a)
    assert len(a) >= 40 or (len(a) >= 15 and STUB_OK), f"cat{c}: остаток короток: {a[:50]!r}"
    if lead:
        if not (a[0].isupper() or a[0].isdigit() or a[0] in '«…('):
            assert N >= 3, f"cat{c}: остаток начинается странно: {a[:30]!r}"
            lower_starts.append(c)
    new_ann[c] = a
for c, v in RST.items():
    t = v['text'].strip()
    assert t and len(t) >= 30, f"cat{c}: restore пуст"
    assert 'Библиография' not in t and 'БИБЛИОГРАФИЯ' not in t, f"cat{c}: библиография в restore"
    new_ann[c] = t
for c in NONE_:
    new_ann[c] = None

snap_b = [{k: v for k, v in r.items() if k != 'annotation'} for r in cat0]
ann_b = [r['annotation'] for r in cat0]

cat1 = copy.deepcopy(cat0)
for c, a in new_ann.items():
    cat1[c]['annotation'] = a

# ── Инварианты ──
assert len(cat1) == 7232, "И1"
changed = [i for i in range(7232) if cat1[i]['annotation'] != ann_b[i]]
assert set(changed) == set(new_ann), f"И2: {set(changed) ^ set(new_ann)}"
snap_a = [{k: v for k, v in r.items() if k != 'annotation'} for r in cat1]
assert json.dumps(snap_b, ensure_ascii=False, sort_keys=True) == \
       json.dumps(snap_a, ensure_ascii=False, sort_keys=True), "И3"
assert Counter(r['source'] for r in cat0) == Counter(r['source'] for r in cat1), "И4"
assert [(r['title'], r['source']) for r in cat0] == \
       [(r['title'], r['source']) for r in cat1], "И5"

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
shutil.copy2(SRC_CAT, f'backups/catalog_f5_{PREV}_{ts}.json')
shutil.copy2(SRC_Q, f'backups/Ф5_очередь_docx_{PREV}_{ts}.json')

with open(f'state/catalog_f5_a{N}.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)

closed = set(RST) | set(NONE_) | set(CONF)
out = []
for e in q['annotation']:
    if e['cat'] in closed:
        continue
    if e['cat'] in NF:
        e = dict(e); e.update(NF[e['cat']])
    out.append(e)
q['annotation'] = out
with open(SRC_Q, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

os.replace(SRC_CAT, f'backups/catalog_f5_{PREV}.json')

prot = {}
for c, v in CUT.items():
    prot[str(c)] = {'op': 'cut', 'class': v['class'],
                    'lead_cut': v.get('lead'), 'tail_cut': v.get('tail'),
                    'mid_cut': v.get('mid'),
                    'len_before': len(ann_b[c] or ''), 'len_after': len(new_ann[c])}
for c, v in RST.items():
    prot[str(c)] = {'op': 'restore', 'vol': v['vol'], 'lines': v['lines'],
                    'note': v['note'], 'before': ann_b[c], 'text': v['text']}
for c, v in NONE_.items():
    prot[str(c)] = {'op': 'none', 'note': v['note'], 'before': ann_b[c]}
for c, v in CONF.items():
    prot[str(c)] = {'op': 'confirm', **v}
for c, v in NF.items():
    prot[str(c)] = {'op': 'notfound', **v}
json.dump(prot, open(f'scripts/_a{N}_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"строчных остатков (наследие a4): {len(lower_starts)}")
print(f"OK a{N}: cut {len(CUT)}, restore {len(RST)}, none {len(NONE_)}, "
      f"confirm {len(CONF)}, notfound {len(NF)}; И1-И5 пройдены; страёв в классах нет.")
a = sum(1 for e in q['annotation'] if not e.get('stray'))
s = sum(1 for e in q['annotation'] if e.get('stray'))
print(f"очередь annotation: {len(q['annotation'])} (активных {a}, страёв {s})")
