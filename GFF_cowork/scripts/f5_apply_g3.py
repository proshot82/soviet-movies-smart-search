# -*- coding: utf-8 -*-
"""Ф5 добор genre, сессия 3 (том v2_1936-1957). Санкция: 26 правок = вся
активная v2-очередь; ненайденных нет. Источники: (а) печатная голова статьи —
23 правки; (б) жанровое самоназвание в аннотации при печатном отсутствии
жанра в голове (конвенция старых томов) — 3 правки (cat1181/1184/1186,
«Звуковые сборные программы», самоназвание «сборник» → канон «Киносборник»).
Строка = индекс в v2_lines.txt. Инварианты И1-И5 до записи файла.
Страи alignment_v17 в санкции запрещены."""
import json, copy
from collections import Counter

SRC_CAT = '/mnt/user-data/uploads/catalog_f5_g2.json'
SRC_Q   = '/mnt/user-data/uploads/Ф5_очередь_docx.json'
SRC_AL  = '/mnt/user-data/uploads/alignment_v17.json'

res = json.load(open('/home/claude/g3/g3_resolution.json', encoding='utf-8'))
SANCTION = {int(k): tuple(v) for k, v in res['sanction'].items()}   # cat -> (raw, canon, line, src)

cat0 = json.load(open(SRC_CAT, encoding='utf-8'))
q    = json.load(open(SRC_Q, encoding='utf-8'))
al   = json.load(open(SRC_AL, encoding='utf-8'))

qg_v2 = {e['cat'] for e in q['genre'] if e['vol'] == 'v2_1936-1957' and not e.get('note')}
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}

# ── Пред-ассерты ──
assert len(cat0) == 7232, f"И1(вход): {len(cat0)}"
assert len(al) == 7232 and len(strays) == 60, f"alignment: {len(al)}/{len(strays)}"
assert set(SANCTION) == qg_v2, \
    f"санкция != активное v2-подмножество очереди: {set(SANCTION) ^ qg_v2}"
assert not (set(SANCTION) & strays), f"страи в санкции: {set(SANCTION) & strays}"
for c in SANCTION:
    r = cat0[c]
    assert r['genre'] is None, f"cat{c}: genre не None: {r['genre']!r}"
    assert r['source'] == 'v2_1936-1957', f"cat{c}: source {r['source']!r}"

snap_before  = [{k: v for k, v in r.items() if k != 'genre'} for r in cat0]
genre_before = [r['genre'] for r in cat0]

# ── Применение ──
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
with open('/mnt/user-data/outputs/catalog_f5_g3.json', 'w', encoding='utf-8') as f:
    json.dump(cat1, f, ensure_ascii=False, indent=1)

# ── Обновление очереди: закрытые v2-позиции удалить ──
new_gq = [e for e in q['genre'] if e['cat'] not in SANCTION]
q['genre'] = new_gq
with open('/mnt/user-data/outputs/Ф5_очередь_docx.json', 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

# ── Протокол ──
json.dump({str(k): {'raw': v[0], 'canon': v[1], 'line': v[2], 'src': v[3]}
           for k, v in SANCTION.items()},
          open('/home/claude/g3/_g3_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"OK: применено {len(SANCTION)} правок genre; И1-И5 прошли; страёв в санкции нет.")
rest = Counter(e['vol'] for e in q['genre'] if not e.get('note'))
term = sum(1 for e in q['genre'] if e.get('note'))
print(f"очередь genre: {len(q['genre'])} (в т.ч. терминальных: {term})")
print("остаток по томам:", dict(sorted(rest.items())))
print("новые значения:", dict(Counter(v[1] for v in SANCTION.values()).most_common()))
print("источники:", dict(Counter(v[3] for v in SANCTION.values())))
