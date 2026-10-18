# -*- coding: utf-8 -*-
"""Ф5 П1+П2: сборка выходного пакета в /mnt/user-data/outputs/."""
import json, shutil, subprocess
from collections import Counter, defaultdict
import f5_genre_map as G

OUT = '/mnt/user-data/outputs/'
cat0 = json.load(open('catalog_f4_волна17.json', encoding='utf-8'))
cat1 = json.load(open('catalog_f5_p12.json', encoding='utf-8'))
aln  = json.load(open('alignment_v17.json', encoding='utf-8'))
p2   = json.load(open('_p2_final.json', encoding='utf-8'))
sanc = json.load(open('_p12_sanction.json', encoding='utf-8'))
IND  = {int(k): v for k, v in json.load(open('_p2_individual.json')).items()}
STRAYS = {r['cat_pos'] for r in aln if r.get('cat_pos') is not None and r.get('xlsx_row') is None}

def t(i): return (cat0[i].get('title') or '')[:52]
def esc(x): return str(x).replace('|', '\\|') if x is not None else '—'

# ════════════════════════ ВЕТО-ПРОТОКОЛ ════════════════════════
L = []
L.append('# ВЕТО Ф5 — П1 (genre) + П2 (studio) + микро-правка annotation\n')
L.append('Статус: применено под действующим карт-бланшем; файл — протокол изменений.\n')
L.append('Инварианты И1–И5 apply-прогона: **все прошли** '
         '(длина 7232; изменения==санкция пополево; снимок-тест нетронутых полей; '
         'пер-томовые счётчики; состав и порядок записей).\n')
L.append('Итог: **genre 271** правка (267 словарных + 4 фитильных; из них 28 → None), '
         '**studio 2566** правок (2343 уникальные пары), **annotation 1** (cat1186). '
         'Страи (60 поз.) из П1/П2 исключены — их поля решаются пакетом §4.\n')

# ---- П1 ----
L.append('\n## П1. genre — канонический словарь\n')
L.append('Политика: развороты печатных сокращений; детерминированное восстановление OCR-форм; '
         'извлечение жанрового токена из обрывков; анимационная триада (Графич./Объемн./Комб.) '
         'и её OCR-формы → «Анимация» (итог по базе: 634); неизвлекаемое → None + docx-очередь; '
         'фитили с потерянным жанром → «Всесоюзный сатирический киножурнал» '
         '(только при title «Фитиль №…», проверка до словаря).\n')
L.append(f'Классы словаря: EXPAND {len(G.EXPAND)}, OCR {len(G.OCR)}, EXTRACT {len(G.EXTRACT)}, '
         f'ANIM {len(G.ANIM)}, TO_NONE {len(G.TO_NONE)}, FITIL_FORMS {len(G.FITIL_FORMS)}.\n')
L.append('\n### Полный список правок genre (271)\n')
L.append('| cat | том | название | до | после |')
L.append('|---|---|---|---|---|')
for i, old, new in sanc['genre']:
    L.append(f'| {i} | {cat0[i]["source"]} | {esc(t(i))} | {esc(old)} | {esc(new)} |')

# ---- П2 ----
L.append('\n## П2. studio — структурный нормализатор v8\n')
L.append('Пайплайн: глиф-фиксы (>>→», “”→«», I960/1J62/«19x x»/4 9xx/1 xx→19xx, *¡→1, $→5, '
         '’-стрип перед «г», <→«, "→«») → циклический лид-срез (серии, формат-слова, метраж+юнит, '
         'кляксы-лиды с охраной строчных легитимных форм и ординалов) → хвостовой срез '
         '(ВЭ/ВРЭ/РУ-коды, ч/б, хвостовой метраж, год-диапазоны и одиночные годы с расширенным '
         'классом OCR-мусора после «г» — срез с сохранением значения в год-кандидаты при '
         'несовпадении с годом записи) → починка инициалов → срединная чистка (формат-пары, '
         'мусорные токены; цифровые токены защищены) → склейка переносов (словарь SUPPLEMENT '
         'приоритетно, далее частотные таблицы корпуса; пробельные разрывы по аттестации) → '
         'второй хвостовой проход → лапки пер-эпоха (v1–v3 снять сиротскую, v4+ достроить пару).\n')
L.append('\n### SUPPLEMENT — словарь склейки переносов (26 пар)\n')
L.append('Обоснование: целевые формы аттестованы доминирующими написаниями в корпусе томов '
         'либо являются известными студиями каталога; Болгар-фильм и Кино-рабмол — '
         'консервативный дефисный вид + docx-флаг (слитность по печати не выяснена).\n')
L.append('| разрыв | склейка |')
L.append('|---|---|')
import f5_studio_norm4 as N
for (a, b), v in sorted(N.SUPPLEMENT.items()):
    mark = ' *(docx-флаг)*' if (a, b) in N.DOCX_FLAG_PAIRS else ''
    L.append(f'| {a}- {b} | {v}{mark} |')
L.append('\n### INDIVIDUAL — адресные решения (40)\n')
L.append('| cat | название | до | после |')
L.append('|---|---|---|---|')
for i in sorted(IND):
    L.append(f'| {i} | {esc(t(i))} | {esc((cat0[i].get("studio") or "").strip() or None)} | {esc(IND[i])} |')
L.append('\n### Уникальные пары нормализации (до → после), по убыванию частоты\n')
pairs = Counter()
for i, s, new, tags in p2['changes']:
    pairs[(s, new if new is not None else '—NULL—')] += 1
L.append('| n | до | после |')
L.append('|---|---|---|')
for (s, new), n in sorted(pairs.items(), key=lambda x: (-x[1], x[0][0])):
    L.append(f'| {n} | {esc(s)} | {esc(new)} |')
L.append(f'\nВсего уникальных пар: {len(pairs)}; правок: {len(p2["changes"])}.\n')

# ---- микро-П4 ----
L.append('\n## Микро-правка annotation — cat1186 «Звуковая сборная программа № 3»\n')
L.append('Вытесненный в studio состав программы «Агитпропфильм «Участок фронта» («Хлеб»).» '
         'возвращён в начало аннотации (в аннотации фильм упомянут не был — проверено); '
         'studio ← «Межрабпомфильм» (INDIVIDUAL), genre ← None (TO_NONE, форма «Межрабпомфильм»). '
         'Верификация по тому v2 — в docx-очереди.\n')
open(OUT + 'ВЕТО_Ф5_П1_П2.md', 'w', encoding='utf-8').write('\n'.join(L))

# ════════════════════════ ОЧЕРЕДЬ DOCX ════════════════════════
q = {'genre': [], 'studio_empty': [], 'studio_flags': [], 'year_empty': [],
     'year_candidates': [], 'annotation': []}

new_none = {i for i, o, n in sanc['genre'] if n is None}
for i, r in enumerate(cat1):
    if i in STRAYS: continue
    if not r.get('genre'):
        q['genre'].append({'cat': i, 'vol': r['source'], 'title': cat0[i].get('title'),
                           'new_none': i in new_none,
                           'old_genre': cat0[i].get('genre') if i in new_none else None})
for i, r in enumerate(cat1):
    if i in STRAYS: continue
    if not r.get('studio'):
        q['studio_empty'].append({'cat': i, 'vol': r['source'], 'title': cat0[i].get('title'),
                                  'old_studio': (cat0[i].get('studio') or '').strip() or None})
for i, ttl, y, s, new, f in p2['docxflags']:
    q['studio_flags'].append({'cat': i, 'title': cat0[i].get('title'), 'year': y,
                              'flag': f, 'before': s, 'after': new})
for i, r in enumerate(cat1):
    if not r.get('year'):
        q['year_empty'].append({'cat': i, 'vol': r['source'], 'title': cat0[i].get('title'),
                                'stray': i in STRAYS})
q['year_empty'].append({'cat': 854, 'vol': cat1[854]['source'], 'title': cat0[854].get('title'),
                        'stray': 854 in STRAYS, 'note': 'year=1905 — вне 1918–1987, вероятно взят из альт-названия «1905 год»'})
for i, ttl, y, s, new, f in p2['yearflags']:
    q['year_candidates'].append({'cat': i, 'title': cat0[i].get('title'), 'year_record': y,
                                 'flag': f, 'studio_before': s})
ANN12 = [388, 464, 470, 489, 1185, 2024, 2525, 2739, 3318, 5244, 5890, 6966]
for i in ANN12:
    q['annotation'].append({'cat': i, 'vol': cat1[i]['source'], 'title': cat0[i].get('title'),
                            'kind': 'пустая аннотация (доволновая)', 'stray': i in STRAYS})
q['annotation'].append({'cat': 3554, 'vol': cat1[3554]['source'], 'title': cat0[3554].get('title'),
                        'kind': 'аннотация = библиография (нужна настоящая из тома)', 'stray': False})
q['annotation'].append({'cat': 1186, 'vol': cat1[1186]['source'], 'title': cat0[1186].get('title'),
                        'kind': 'верифицировать prepend «Агитпропфильм «Участок фронта» («Хлеб»).» по тому', 'stray': False})
q['annotation'].append({'cat': 3876, 'vol': cat1[3876]['source'], 'title': cat0[3876].get('title'),
                        'kind': 'законный стаб — НЕ трогать', 'stray': False})
q['annotation'].append({'cat': 3877, 'vol': cat1[3877]['source'], 'title': cat0[3877].get('title'),
                        'kind': 'законный стаб — НЕ трогать', 'stray': False})
json.dump(q, open(OUT + 'Ф5_очередь_docx.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

M = []
M.append('# Ф5 — очередь добора по docx-томам (после П1+П2)\n')
M.append('Правило добора: (а) печатная голова статьи в томе, (б) контекст аннотации, '
         '(в) «не определено»/None. Веб не используется.\n')
byvol = defaultdict(list)
for e in q['genre']: byvol[e['vol']].append(e)
M.append(f"\n## 1. genre — пустые, не-страи: {len(q['genre'])} (из них {sum(1 for e in q['genre'] if e['new_none'])} новых → None из П1)\n")
def volkey(v): return int(v.split('_')[0][1:])
for vol in sorted(byvol, key=volkey):
    M.append(f'\n### {vol} — {len(byvol[vol])}\n')
    M.append('| cat | название | примечание |')
    M.append('|---|---|---|')
    for e in byvol[vol]:
        note = f'новый → None (было: {esc(e["old_genre"])})' if e['new_none'] else ''
        M.append(f'| {e["cat"]} | {esc(e["title"])} | {note} |')
M.append(f"\n## 2. studio — пустые, не-страи: {len(q['studio_empty'])}\n")
M.append('| cat | том | название | что было в поле |')
M.append('|---|---|---|---|')
for e in q['studio_empty']:
    M.append(f'| {e["cat"]} | {e["vol"]} | {esc(e["title"])} | {esc(e["old_studio"])} |')
M.append(f"\n## 3. studio — docx-флаги: {len(q['studio_flags'])} (35 «лид-и»: возможна утрата первого копродюсера; 2 «слитность»)\n")
M.append('| cat | название | флаг | до | после |')
M.append('|---|---|---|---|---|')
for e in q['studio_flags']:
    M.append(f'| {e["cat"]} | {esc(e["title"])} | {e["flag"]} | {esc(e["before"])} | {esc(e["after"])} |')
M.append(f"\n## 4. year — пустые: {len(q['year_empty'])-1} + cat854 (year=1905)\n")
M.append('| cat | том | название | примечание |')
M.append('|---|---|---|---|')
for e in q['year_empty']:
    note = ('СТРАЙ (пакет §4); ' if e['stray'] else '') + e.get('note', '')
    M.append(f'| {e["cat"]} | {e["vol"]} | {esc(e["title"])} | {note} |')
M.append(f"\n## 5. year — кандидаты из хвостов studio: {len(q['year_candidates'])}\n")
M.append('Хвостовой год из поля studio срезан; значение сохранено здесь. '
         'Сверить с печатной головой тома: где кандидат = год производства, а поле year — год ВЭ, заменить year.\n')
M.append('| cat | название | year записи | кандидат | исходная строка studio |')
M.append('|---|---|---|---|---|')
for e in q['year_candidates']:
    M.append(f'| {e["cat"]} | {esc(e["title"])} | {e["year_record"]} | {e["flag"].split(":",1)[1]} | {esc(e["studio_before"])} |')
M.append(f"\n## 6. annotation: {len(q['annotation'])}\n")
M.append('| cat | том | название | что сделать |')
M.append('|---|---|---|---|')
for e in q['annotation']:
    note = ('СТРАЙ (пакет §4); ' if e['stray'] else '') + e['kind']
    M.append(f'| {e["cat"]} | {e["vol"]} | {esc(e["title"])} | {note} |')
open(OUT + 'Ф5_очередь_docx.md', 'w', encoding='utf-8').write('\n'.join(M))

# ════════════════════════ каталог + архив ════════════════════════
shutil.copy('catalog_f5_p12.json', OUT + 'catalog_f5_p12.json')
subprocess.run(['tar', 'czf', OUT + 'f5_scripts.tar.gz',
                'f5_genre_map.py', 'f5_studio_norm4.py', 'f5_apply_p12.py',
                'f5_build_outputs.py', '_p2_individual.json', '_p2_final.json',
                '_p12_sanction.json'], check=True)
print('OK:', OUT)
for f in ('catalog_f5_p12.json', 'ВЕТО_Ф5_П1_П2.md', 'Ф5_очередь_docx.md', 'Ф5_очередь_docx.json', 'f5_scripts.tar.gz'):
    import os
    print(f'  {f}: {os.path.getsize(OUT+f):,} байт')
print('очередь: genre', len(q['genre']), '| studio_empty', len(q['studio_empty']),
      '| studio_flags', len(q['studio_flags']), '| year_empty', len(q['year_empty']),
      '| year_cand', len(q['year_candidates']), '| ann', len(q['annotation']))
