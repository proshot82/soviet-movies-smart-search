# -*- coding: utf-8 -*-
"""Ф5 добор genre, сессия 4 (том v3_1958-1963). Санкция: 8 правок; 1 позиция
(cat2848 «Кёр-оглы») — терминально None (жанр в печатной голове отсутствует,
самоназвания в аннотации нет; прецедент v1). 8 + 1 = вся активная v3-очередь.
Источники: (а) печатная голова — 7 правок; (б) жанровое самоназвание
(cat3064 «Сборник комедийных фильмов» → «Киносборник», прецедент g3) — 1.
Строка = индекс в v3_lines.json. Инварианты И1-И5 до записи файла.
Страи alignment_v17 в санкции запрещены."""
import json, copy
from collections import Counter

SRC_CAT = '/mnt/user-data/uploads/catalog_f5_g3.json'
SRC_Q   = '/mnt/user-data/uploads/Ф5_очередь_docx.json'
SRC_AL  = '/mnt/user-data/uploads/alignment_v17.json'
VOL     = 'v3_1958-1963'

res = json.load(open('/home/claude/g4/g4_resolution.json', encoding='utf-8'))
SANCTION = {int(k): tuple(v) for k, v in res['sanction'].items()}   # cat -> (raw, canon, line, src)
TERMINAL = {int(k): v for k, v in res['terminal'].items()}          # cat -> {note, ...}

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q    = json.load(open(SRC_Q, encoding='utf-8'))
al   = json.load(open(SRC_AL, encoding='utf-8'))

qv_active = {e['cat'] for e in q['genre'] if e['vol'] == VOL and not e.get('note')}
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, f"alignment: {len(al)}/{len(strays)}"
assert set(SANCTION) | set(TERMINAL) == qv_active, \
    f"санкция+терминал != активное v3-подмножество очереди: {(set(SANCTION)|set(TERMINAL)) ^ qv_active}"
assert not (set(SANCTION) & set(TERMINAL)), "пересечение санкции и терминала"
assert not ((set(SANCTION) | set(TERMINAL)) & strays), \
    f"страи в санкции: {(set(SANCTION)|set(TERMINAL)) & strays}"
for c in list(SANCTION) + list(TERMINAL):
    r = cat0[c]
    assert r['genre'] is None, f"cat{c}: genre не None: {r['genre']!r}"
    assert r['source'] == VOL, f"cat{c}: source {r['source']!r}"

snap_before  = [{k: v for k, v in r.items() if k != 'genre'} for r in cat0]
genre_before = [r['genre'] for r in cat0]

# ── Применение (только санкция; терминал каталог не трогает) ──
cat1 = copy.deepcopy(cat0)
for c, (raw, canon, ln, src) in SANCTION.items():
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
with open('/mnt/user-data/outputs/catalog_f5_g4.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)

# ── Обновление очереди: закрытые удалить, терминалу — пометка ──
new_gq = []
for e in q['genre']:
    if e['cat'] in SANCTION:
        continue
    if e['cat'] in TERMINAL:
        e = dict(e)
        e['note'] = TERMINAL[e['cat']]['note']
        e['head_line_v3'] = TERMINAL[e['cat']]['head_line_v3']
    new_gq.append(e)
q['genre'] = new_gq
with open('/mnt/user-data/outputs/Ф5_очередь_docx.json', 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

# ── Протокол ──
json.dump({str(k): {'raw': v[0], 'canon': v[1], 'line': v[2], 'src': v[3]}
           for k, v in SANCTION.items()} |
          {str(k): {'terminal': True, **v} for k, v in TERMINAL.items()},
          open('/home/claude/g4/_g4_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"OK: применено {len(SANCTION)} правок genre; терминалов: {len(TERMINAL)}; "
      f"И1-И5 прошли; страёв в санкции нет.")
rest = Counter(e['vol'] for e in q['genre'] if not e.get('note'))
term = sum(1 for e in q['genre'] if e.get('note'))
print(f"очередь genre: {len(q['genre'])} (в т.ч. терминальных: {term})")
print("остаток по томам:", dict(sorted(rest.items())))
print("новые значения:", dict(Counter(v[1] for v in SANCTION.values()).most_common()))
print("источники:", dict(Counter(v[3] for v in SANCTION.values())))
