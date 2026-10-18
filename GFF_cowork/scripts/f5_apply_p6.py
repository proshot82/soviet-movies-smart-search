# -*- coding: utf-8 -*-
"""Ф5 П6 стабы и разнобой канонов — apply, режим Cowork. Запуск из КОРНЯ:
python3 scripts/f5_apply_p6.py <N=1|2|3|4>
Читает scripts/k{N}_resolution.json:
  {"set": {cat: {"field": "genre|studio|annotation|year", "before": ..., "after": ...,
                 "vol": str|null, "line": int|[int,...]|null, "class": str, "note": str}},
   "confirm": {cat: {"note"}}}
Пополевые правки; before сверяется байт-в-байт (анти-фабрикация механикой).
Стоп-ассерт: страи запрещены. Порядок: пред-ассерты -> И1-И5 -> бэкапы ->
state/catalog_f5_k{N}.json -> предыдущий каталог в backups/ -> протокол
scripts/_k{N}_sanction.json. Очередь не меняется (копируется в бэкап)."""
import json, copy, os, re, shutil, sys, datetime
from collections import Counter

N = int(sys.argv[1])
PREV = {1: 's6', 2: 'k1', 3: 'k2', 4: 'k3', 5: 'k4'}[N]
SRC_CAT = f'state/catalog_f5_{PREV}.json'
SRC_Q, SRC_AL = 'state/Ф5_очередь_docx.json', 'state/alignment_v17.json'
FIELDS = {'genre', 'studio', 'annotation', 'year'}
CLASSES = {'canon', 'quotes', 'lex', 'punct', 'restore', 'lead', 'prefix', 'year'}
MARKERS = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиография|БИБЛИОГРАФИЯ|дир\. картины|худ\.-пост)')
VOL_RANGE = {'v1': (1918, 1935), 'v2': (1930, 1957), 'v3': (1958, 1963), 'v4': (1964, 1965),
             'v5': (1966, 1967), 'v6': (1968, 1969), 'v7': (1970, 1971), 'v8': (1972, 1973),
             'v9': (1974, 1975), 'v10': (1976, 1977), 'v11': (1978, 1979), 'v12': (1980, 1981),
             'v13': (1982, 1983), 'v14': (1984, 1985), 'v15': (1986, 1987)}

res = json.load(open(f'scripts/k{N}_resolution.json', encoding='utf-8'))
SET = {int(k): v for k, v in res.get('set', {}).items()}
CONF = {int(k): v for k, v in res.get('confirm', {}).items()}
DICT = res.get('dict', {})  # необязательный словарь допустимых after для canon/lex/punct

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q = json.load(open(SRC_Q, encoding='utf-8'))
al = json.load(open(SRC_AL, encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, "alignment"
assert not (set(SET) & set(CONF)), "пересечение set/confirm"
touched = set(SET) | set(CONF)
assert not (touched & strays), f"СТРАИ: {sorted(touched & strays)}"
for c, v in SET.items():
    f = v['field']; cls = v['class']
    assert f in FIELDS, f"cat{c}: поле {f!r}"
    assert cls in CLASSES, f"cat{c}: класс {cls!r}"
    cur = cat0[c].get(f)
    assert cur == v.get('before'), f"cat{c}/{f}: before не совпал: {cur!r} != {v.get('before')!r}"
    a = v.get('after')
    assert a != v.get('before'), f"cat{c}/{f}: after==before"
    if f == 'year':
        assert isinstance(a, int), f"cat{c}: год не int"
        vol = cat0[c]['source'].split('_')[0]
        lo, hi = VOL_RANGE[vol]
        assert lo - 1 <= a <= hi + 1, f"cat{c}: год {a} вне диапазона тома {vol}"
        assert cls == 'year'
    else:
        assert isinstance(a, str) and a.strip() and a == a.strip(), f"cat{c}/{f}: пустой/с пробелами after"
        assert '  ' not in a, f"cat{c}/{f}: двойной пробел в after"
    b = v.get('before')
    if cls == 'quotes':
        assert f == 'studio' and re.sub(r'[«»]', '', b) == a and '«' in b, f"cat{c}: quotes не механично"
    elif cls == 'lead':
        assert f == 'annotation' and b.endswith(a) and len(a) >= 40, f"cat{c}: lead не суффикс"
    elif cls == 'prefix':
        assert f == 'annotation' and a.endswith(b) and len(a) > len(b), f"cat{c}: prefix не расширение"
    elif cls == 'restore':
        assert f == 'annotation' and not MARKERS.search(a), f"cat{c}: маркер титров в restore: {MARKERS.search(a)}"
        assert v.get('vol') and v.get('line') is not None, f"cat{c}: restore без vol/line"
    elif cls in ('canon', 'lex', 'punct'):
        if DICT.get(cls):
            assert a in DICT[cls], f"cat{c}: after {a!r} вне словаря класса {cls}"
    assert v.get('note') is not None, f"cat{c}: нет note"

snap_b = [dict(r) for r in cat0]
cat1 = copy.deepcopy(cat0)
for c, v in SET.items():
    cat1[c][v['field']] = v['after']

# ── Инварианты ──
assert len(cat1) == 7232, "И1"
changed = {(i, k) for i in range(7232) for k in cat1[i] if cat1[i][k] != snap_b[i].get(k)}
expected = {(c, v['field']) for c, v in SET.items()}
assert changed == expected, f"И2: {changed ^ expected}"
for c, v in SET.items():
    assert cat1[c][v['field']] == v['after'], f"И2 значение cat{c}"
for i in range(7232):
    keys = set(snap_b[i]) | set(cat1[i])
    for k in keys:
        if (i, k) in changed:
            continue
        assert snap_b[i].get(k) == cat1[i].get(k), f"И3 cat{i}/{k}"
assert Counter(r['source'] for r in cat0) == Counter(r['source'] for r in cat1), "И4"
assert [(r['title'], r['source']) for r in cat0] == \
       [(r['title'], r['source']) for r in cat1], "И5"

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
shutil.copy2(SRC_CAT, f'backups/catalog_f5_{PREV}_{ts}.json')
shutil.copy2(SRC_Q, f'backups/Ф5_очередь_docx_{PREV}_{ts}.json')

with open(f'state/catalog_f5_k{N}.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)
os.replace(SRC_CAT, f'backups/catalog_f5_{PREV}.json')

prot = {}
for c, v in SET.items():
    prot[str(c)] = {'op': 'set', **v}
for c, v in CONF.items():
    prot[str(c)] = {'op': 'confirm', **v}
json.dump(prot, open(f'scripts/_k{N}_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

by_cls = Counter((v['field'], v['class']) for v in SET.values())
print(f"OK k{N}: set {len(SET)} {dict(by_cls)}, confirm {len(CONF)}; И1-И5 пройдены; страёв в классах нет.")
