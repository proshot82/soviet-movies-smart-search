# -*- coding: utf-8 -*-
"""Ф5 добор genre, сессия 2 (том v1_1918-1935). Санкция: 57 правок из 61 позиции
очереди v1; 4 позиции — жанр в печатной голове отсутствует (конвенция тома,
преамбула стр. 21) -> остаются None с пометкой в очереди.
Источник каждой правки — печатная голова статьи тома ((а)); строка = индекс в v1_lines.json.
Инварианты И1-И5 до записи файла. Страи alignment_v17 в санкции запрещены."""
import json, copy
from collections import Counter

SRC_CAT = '/mnt/user-data/uploads/catalog_f5_g1.json'
SRC_Q   = '/mnt/user-data/uploads/Ф5_очередь_docx.json'
SRC_AL  = '/mnt/user-data/uploads/alignment_v17.json'

res = json.load(open('/home/claude/work/g2_resolution.json', encoding='utf-8'))
SANCTION = {int(k): tuple(v) for k, v in res['sanction'].items()}   # cat -> (raw, canon, line)
ABSENT   = {int(k): v for k, v in res['absent'].items()}            # cat -> line головы
ABSENT_NOTE = ('жанр в печатной голове отсутствует (конвенция тома v1, преамбула); '
               'жанрового самоназвания в аннотации нет — терминально None')

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q    = json.load(open(SRC_Q, encoding='utf-8'))
al   = json.load(open(SRC_AL, encoding='utf-8'))

qg_v1 = {e['cat'] for e in q['genre'] if e['vol'] == 'v1_1918-1935'}
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, f"alignment: {len(al)}/{len(strays)}"
assert set(SANCTION) | set(ABSENT) == qg_v1, \
    f"санкция+отсутствия != v1-подмножество очереди: {(set(SANCTION)|set(ABSENT)) ^ qg_v1}"
assert not (set(SANCTION) & set(ABSENT)), "пересечение санкции и отсутствий"
assert not (set(SANCTION) & strays), f"страи в санкции: {set(SANCTION) & strays}"
for c in SANCTION:
    r = cat0[c]
    assert r['genre'] is None, f"cat{c}: genre не None: {r['genre']!r}"
    assert r['source'] == 'v1_1918-1935', f"cat{c}: source {r['source']!r}"
for c in ABSENT:
    r = cat0[c]
    assert r['genre'] is None and r['source'] == 'v1_1918-1935', f"cat{c} (absent)"

snap_before  = [{k: v for k, v in r.items() if k != 'genre'} for r in cat0]
genre_before = [r['genre'] for r in cat0]

# ── Применение ──
cat1 = copy.deepcopy(cat0)
for c, (raw, canon, ln) in SANCTION.items():
    cat1[c]['genre'] = canon

# ── Инварианты ──
assert len(cat1) == 7232, "И1"
changed = [i for i in range(7232) if cat1[i]['genre'] != genre_before[i]]
assert set(changed) == set(SANCTION), f"И2: {set(changed) ^ set(SANCTION)}"
for c in changed:
    assert cat1[c]['genre'] == SANCTION[c][1], f"И2: cat{c} значение"
snap_after = [{k: v for k, v in r.items() if k != 'genre'} for r in cat1]
assert json.dumps(snap_before, ensure_ascii=False, sort_keys=True) == \
       json.dumps(snap_after,  ensure_ascii=False, sort_keys=True), "И3"
assert Counter(r['source'] for r in cat0) == Counter(r['source'] for r in cat1), "И4"
assert [(r['title'], r['source']) for r in cat0] == \
       [(r['title'], r['source']) for r in cat1], "И5"

# ── Запись каталога ──
with open('/mnt/user-data/outputs/catalog_f5_g2.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)

# ── Обновление очереди: закрытые удалить, отсутствия пометить ──
new_gq = []
for e in q['genre']:
    if e['cat'] in SANCTION:
        continue
    if e['cat'] in ABSENT:
        e = dict(e)
        e['note'] = ABSENT_NOTE
        e['head_line_v1'] = ABSENT[e['cat']]
    new_gq.append(e)
q['genre'] = new_gq
with open('/mnt/user-data/outputs/Ф5_очередь_docx.json', 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

# ── Протокол ──
json.dump({str(k): {'raw': v[0], 'canon': v[1], 'line': v[2], 'src': 'а'}
           for k, v in SANCTION.items()},
          open('/home/claude/work/_g2_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"OK: применено {len(SANCTION)} правок genre; И1-И5 прошли; страёв в санкции нет.")
rest = Counter(e['vol'] for e in q['genre'])
print(f"очередь genre: {len(q['genre'])} (в т.ч. v1 терминальных: "
      f"{sum(1 for e in q['genre'] if e.get('note'))})")
print("остаток по томам:", dict(sorted(rest.items())))
print("новые значения:", dict(Counter(v[1] for v in SANCTION.values()).most_common()))
