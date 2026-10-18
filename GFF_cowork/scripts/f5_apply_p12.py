# -*- coding: utf-8 -*-
"""Ф5 apply П1 (genre) + П2 (studio) + микро-П4 (annotation cat1186).

Инварианты (все обязаны пройти до записи выходного файла):
  И1. Длина каталога == 7232.
  И2. Изменения == санкция пополево: genre-правки строго по словарю f5_genre_map
      (вне страёв), studio-правки строго по _p2_final.json + _p2_individual.json,
      annotation-правка строго одна (cat1186).
  И3. Снимок-тест: все несанкционированные поля байт-в-байт идентичны исходнику.
  И4. Пер-томовые счётчики записей не изменились (нулевой дефицит).
  И5. Последовательность (title, source) не изменилась (состав и порядок нетронуты).
"""
import json, copy, sys
from collections import Counter
import f5_genre_map as G

CAT_IN  = 'catalog_f4_волна17.json'
ALN_IN  = 'alignment_v17.json'
P2_IN   = '_p2_final.json'
CAT_OUT = 'catalog_f5_p12.json'

cat  = json.load(open(CAT_IN, encoding='utf-8'))
aln  = json.load(open(ALN_IN, encoding='utf-8'))
p2   = json.load(open(P2_IN, encoding='utf-8'))
STRAYS = {r['cat_pos'] for r in aln if r.get('cat_pos') is not None and r.get('xlsx_row') is None}
before = copy.deepcopy(cat)

# ── Санкция П1: genre ────────────────────────────────────────────────
genre_sanction = []            # (i, old, new)
for i, r in enumerate(cat):
    if i in STRAYS: continue
    g = r.get('genre')
    if g is None: continue
    title = r.get('title') or ''
    if title.startswith('Фитиль №') and g in G.FITIL_FORMS:
        new = G.FITIL_CANON
    elif g in G.MAP:
        new = G.MAP[g]
    else:
        continue
    if new != g:
        genre_sanction.append((i, g, new))

# ── Санкция П2: studio ───────────────────────────────────────────────
studio_sanction = [(i, s, new) for i, s, new, tags in p2['changes']]
assert all(i not in STRAYS for i, _, _ in studio_sanction), 'страй в санкции П2!'

# ── Санкция микро-П4: annotation cat1186 ─────────────────────────────
ANN_I = 1186
ANN_PREPEND = 'Агитпропфильм «Участок фронта» («Хлеб»). '
ann_old = cat[ANN_I].get('annotation') or ''
assert 'Участок фронта' not in ann_old, 'cat1186: фильм уже упомянут — prepend не нужен'
ann_sanction = [(ANN_I, ann_old, ANN_PREPEND + ann_old)]

# ── Проверка непересечения индексов внутри одного поля ───────────────
assert len({i for i,_,_ in genre_sanction})  == len(genre_sanction)
assert len({i for i,_,_ in studio_sanction}) == len(studio_sanction)

# ── Применение с пред-ассертами ──────────────────────────────────────
for i, old, new in genre_sanction:
    assert cat[i].get('genre') == old, f'genre cat{i}: ожидалось {old!r}, в файле {cat[i].get("genre")!r}'
    cat[i]['genre'] = new
for i, old, new in studio_sanction:
    cur = (cat[i].get('studio') or '').strip()
    assert cur == old, f'studio cat{i}: ожидалось {old!r}, в файле {cur!r}'
    cat[i]['studio'] = new
for i, old, new in ann_sanction:
    assert (cat[i].get('annotation') or '') == old
    cat[i]['annotation'] = new

# ── И1: длина ────────────────────────────────────────────────────────
assert len(cat) == 7232 == len(before), 'И1: длина каталога изменилась!'

# ── И2+И3: изменения == санкция пополево, остальное байт-в-байт ──────
gs = {i: (o, n) for i, o, n in genre_sanction}
ss = {i: (o, n) for i, o, n in studio_sanction}
as_ = {i: (o, n) for i, o, n in ann_sanction}
FIELDS = ['id', 'title', 'genre', 'year', 'studio', 'annotation', 'source',
          'cast', 'credits', 'director', 'screenwriter']
diffs = Counter()
for i, (b, a) in enumerate(zip(before, cat)):
    keys = set(b) | set(a)
    assert keys == set(b) == set(a), f'cat{i}: изменился набор полей'
    for k in keys:
        if b.get(k) != a.get(k):
            diffs[k] += 1
            if k == 'genre':
                assert i in gs and b.get(k) == gs[i][0] and a.get(k) == gs[i][1], f'несанкц. genre cat{i}'
            elif k == 'studio':
                assert i in ss and a.get(k) == ss[i][1], f'несанкц. studio cat{i}'
            elif k == 'annotation':
                assert i in as_ and a.get(k) == as_[i][1], f'несанкц. annotation cat{i}'
            else:
                raise AssertionError(f'несанкционированное поле {k} в cat{i}')
assert diffs['genre']  == len(genre_sanction),  f"И2 genre: {diffs['genre']} != {len(genre_sanction)}"
assert diffs['studio'] == len(studio_sanction), f"И2 studio: {diffs['studio']} != {len(studio_sanction)}"
assert diffs['annotation'] == 1

# ── И4: пер-томовые счётчики ─────────────────────────────────────────
cb = Counter(r['source'] for r in before); ca = Counter(r['source'] for r in cat)
assert cb == ca, 'И4: пер-томовые счётчики разошлись!'

# ── И5: состав и порядок ─────────────────────────────────────────────
assert [(r.get('title'), r.get('source')) for r in before] == \
       [(r.get('title'), r.get('source')) for r in cat], 'И5: состав/порядок изменился!'

json.dump(cat, open(CAT_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ── Отчёт ────────────────────────────────────────────────────────────
to_none = [x for x in genre_sanction if x[2] is None]
fitili  = [x for x in genre_sanction if x[2] == G.FITIL_CANON and (cat[x[0]].get('title') or '').startswith('Фитиль №')]
anim    = sum(1 for r in cat if r.get('genre') == 'Анимация')
print(f'ИНВАРИАНТЫ И1-И5: OK')
print(f'genre-правок: {len(genre_sanction)} (из них ->None: {len(to_none)}, фитилей: {len(fitili)})')
print(f'studio-правок: {len(studio_sanction)} | annotation-правок: 1 (cat1186)')
print(f'"Анимация" итого: {anim}')
print(f'genre пустых (не-страи): {sum(1 for i,r in enumerate(cat) if i not in STRAYS and not r.get("genre"))}')
print(f'studio пустых (не-страи): {sum(1 for i,r in enumerate(cat) if i not in STRAYS and not r.get("studio"))}')
print(f'-> {CAT_OUT}')
json.dump({'genre': genre_sanction, 'studio': studio_sanction, 'annotation': ann_sanction},
          open('_p12_sanction.json', 'w', encoding='utf-8'), ensure_ascii=False)
