# -*- coding: utf-8 -*-
"""Ф5 добор genre, сессия 5 (тома v4_1964-1965 + v5_1966-1967). Санкция: 22 правки;
2 терминальных None (cat3554 v4 — конвенция старого блока; cat3915 v5 — первый
прецедент печатного отсутствия жанра в новом томе); 3 позиции заблокированы
физическим разрывом docx v5 (cat3876, cat3877, cat3878 — печатные стр. ~113–116
отсутствуют). 22 + 2 + 3 = 27 = вся активная очередь v4+v5.
Источники: (а) печатная голова — 22 (в т.ч. cat4031 «Фитиль № 63» — FITIL-восстановление
по классу: первая строка головы утрачена, хвост @2433 + позиция в номерной
последовательности №62↔№64 + дословное совпадение трёх сюжетов с каталогом).
Строка = индекс в v4_lines.json / v5_lines.json. Инварианты И1–И5 до записи файла.
Страи alignment_v17 в санкции запрещены."""
import json, copy
from collections import Counter

SRC_CAT = '/mnt/user-data/uploads/catalog_f5_g4.json'
SRC_Q   = '/mnt/user-data/uploads/Ф5_очередь_docx.json'
SRC_AL  = '/mnt/user-data/uploads/alignment_v17.json'
VOLS    = {'v4_1964-1965', 'v5_1966-1967'}

res = json.load(open('/home/claude/g5/g5_resolution.json', encoding='utf-8'))
SANCTION = {int(k): tuple(v) for k, v in res['sanction'].items()}   # cat -> (raw, canon, line, src)
TERMINAL = {int(k): v for k, v in res['terminal'].items()}          # cat -> {note, head_line_*}
NOTFOUND = {int(k): v for k, v in res['notfound'].items()}          # cat -> {note, *_lines_v5}

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q    = json.load(open(SRC_Q, encoding='utf-8'))
al   = json.load(open(SRC_AL, encoding='utf-8'))

qv_active = {e['cat'] for e in q['genre'] if e['vol'] in VOLS and not e.get('note')}
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
touched = set(SANCTION) | set(TERMINAL) | set(NOTFOUND)

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, f"alignment: {len(al)}/{len(strays)}"
assert touched == qv_active, \
    f"санкция+терминал+недобор != активное v4/v5-подмножество очереди: {touched ^ qv_active}"
assert not (set(SANCTION) & set(TERMINAL)) and not (set(SANCTION) & set(NOTFOUND)) \
    and not (set(TERMINAL) & set(NOTFOUND)), "пересечение классов"
assert not (touched & strays), f"страи в санкции: {touched & strays}"
for c in touched:
    r = cat0[c]
    assert r['genre'] is None, f"cat{c}: genre не None: {r['genre']!r}"
    assert r['source'] in VOLS, f"cat{c}: source {r['source']!r}"

snap_before  = [{k: v for k, v in r.items() if k != 'genre'} for r in cat0]
genre_before = [r['genre'] for r in cat0]

# ── Применение (только санкция; терминал и недобор каталог не трогают) ──
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
with open('/mnt/user-data/outputs/catalog_f5_g5.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)

# ── Обновление очереди: закрытые удалить; терминалам и недоборам — пометка ──
new_gq = []
for e in q['genre']:
    if e['cat'] in SANCTION:
        continue
    if e['cat'] in TERMINAL or e['cat'] in NOTFOUND:
        e = dict(e)
        e.update(TERMINAL.get(e['cat']) or NOTFOUND[e['cat']])
    new_gq.append(e)
q['genre'] = new_gq
with open('/mnt/user-data/outputs/Ф5_очередь_docx.json', 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

# ── Протокол ──
json.dump({str(k): {'raw': v[0], 'canon': v[1], 'line': v[2], 'src': v[3]}
           for k, v in SANCTION.items()} |
          {str(k): {'terminal': True, **v} for k, v in TERMINAL.items()} |
          {str(k): {'notfound': True, **v} for k, v in NOTFOUND.items()},
          open('/home/claude/g5/_g5_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"OK: применено {len(SANCTION)} правок genre; терминалов: {len(TERMINAL)}; "
      f"недоборов (разрыв docx): {len(NOTFOUND)}; И1-И5 прошли; страёв в санкции нет.")
rest = Counter(e['vol'] for e in q['genre'] if not e.get('note'))
mark = sum(1 for e in q['genre'] if e.get('note'))
print(f"очередь genre: {len(q['genre'])} (активных: {len(q['genre'])-mark}, с пометкой: {mark})")
print("остаток активной очереди по томам:", dict(sorted(rest.items())))
print("новые значения:", dict(Counter(v[1] for v in SANCTION.values()).most_common()))
print("источники:", dict(Counter(v[3] for v in SANCTION.values())))
