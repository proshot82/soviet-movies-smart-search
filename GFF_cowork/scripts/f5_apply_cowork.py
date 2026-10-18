# -*- coding: utf-8 -*-
"""Ф5 добор genre — apply, режим Cowork (относительные пути от корня папки).
Запуск из КОРНЯ: python3 scripts/f5_apply_cowork.py <N> <vol1> [vol2 ...]
Читает scripts/g{N}_resolution.json: {"sanction": {cat: [raw, canon, line, src]},
"terminal": {cat: {note,...}}, "notfound": {cat: {note,...}}}.
Порядок: пред-ассерты -> бэкапы (копии с меткой времени ДО записи) -> инварианты
И1-И5 -> запись state/catalog_f5_g{N}.json + state/Ф5_очередь_docx.json ->
перемещение state/catalog_f5_g{N-1}.json в backups/ (в state/ ровно один каталог) ->
протокол scripts/_g{N}_sanction.json.
Три класса: санкция / терминал / недобор. Стоп-ассерт: страи в санкции запрещены."""
import json, copy, os, shutil, sys, datetime
from collections import Counter

N = int(sys.argv[1])
VOLS = set(sys.argv[2:])
assert VOLS, "укажи тома"

SRC_CAT = f'state/catalog_f5_g{N-1}.json'
SRC_Q   = 'state/Ф5_очередь_docx.json'
SRC_AL  = 'state/alignment_v17.json'
RES     = f'scripts/g{N}_resolution.json'

res = json.load(open(RES, encoding='utf-8'))
SANCTION = {int(k): tuple(v) for k, v in res['sanction'].items()}   # cat -> (raw, canon, line, src)
TERMINAL = {int(k): v for k, v in res['terminal'].items()}          # cat -> {note, ...}
NOTFOUND = {int(k): v for k, v in res['notfound'].items()}          # cat -> {note, ...}

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
    f"санкция+терминал+недобор != активное подмножество очереди {VOLS}: {touched ^ qv_active}"
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

# ── Бэкапы ДО записи ──
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M')
shutil.copy2(SRC_CAT, f'backups/catalog_f5_g{N-1}_{ts}.json')
shutil.copy2(SRC_Q,   f'backups/Ф5_очередь_docx_g{N-1}_{ts}.json')

# ── Запись каталога ──
with open(f'state/catalog_f5_g{N}.json', 'w', encoding='utf-8') as f:
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
with open(SRC_Q, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

# ── Предыдущий каталог из state/ в backups/ (в state/ ровно один каталог) ──
os.replace(SRC_CAT, f'backups/catalog_f5_g{N-1}.json')

# ── Протокол ──
json.dump({str(k): {'raw': v[0], 'canon': v[1], 'line': v[2], 'src': v[3]}
           for k, v in SANCTION.items()} |
          {str(k): {'terminal': True, **v} for k, v in TERMINAL.items()} |
          {str(k): {'notfound': True, **v} for k, v in NOTFOUND.items()},
          open(f'scripts/_g{N}_sanction.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"OK g{N}: применено {len(SANCTION)} правок genre; терминалов: {len(TERMINAL)}; "
      f"недоборов: {len(NOTFOUND)}; И1-И5 прошли; страёв в санкции нет.")
rest = Counter(e['vol'] for e in q['genre'] if not e.get('note'))
mark = sum(1 for e in q['genre'] if e.get('note'))
print(f"очередь genre: {len(q['genre'])} (активных: {len(q['genre'])-mark}, с пометкой: {mark})")
print("остаток активной очереди по томам:", dict(sorted(rest.items())))
print("новые значения:", dict(Counter(v[1] for v in SANCTION.values()).most_common()))
print("источники:", dict(Counter(v[3] for v in SANCTION.values())))
