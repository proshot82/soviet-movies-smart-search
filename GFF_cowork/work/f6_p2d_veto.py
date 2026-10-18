# -*- coding: utf-8 -*-
"""Ф6-П2д: вето-протокол veto/ВЕТО_Ф6_П2д.md из scripts/f6_p2d_resolution.json (+ _sanction, если есть)."""
import json, re, collections, difflib, os, sys, hashlib
sys.path.insert(0, 'work')
res = json.load(open('scripts/f6_p2d_resolution.json', encoding='utf-8'))
SET = res['set']; META = res['_meta']; CL = META['classes']
san = json.load(open('scripts/_f6_p2d_sanction.json', encoding='utf-8')) if os.path.exists('scripts/_f6_p2d_sanction.json') else None
import f6_p2d_manual as M
def esc(s): return s.replace('|', '\\|').replace('\n', '⏎')
def q(s): return '«' + esc(s) + '»'
def diffs(b, a, w=28):
    sm = difflib.SequenceMatcher(None, b, a, autojunk=False); out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        out.append(f'…{esc(b[max(0, i1 - w):i2 + w])}… → …{esc(a[max(0, j1 - w):j2 + w])}…')
    return out
by = {x['cat']: x for x in SET}
ops_all = [(x['cat'], o) for x in SET for o in x['ops']]
cnt = collections.Counter(o[0] for _, o in ops_all)
L = []
L.append('# ВЕТО Ф6-П2д — механическая чистка OCR-мусора в аннотациях\n')
L.append(f'Вход: `state/catalog_f6_p2.json` (7173). Выход: `state/catalog_f6_p2d.json` (7173; удалений 0; правится ТОЛЬКО поле `annotation`). '
         f'Резолюция: `scripts/f6_p2d_resolution.json`; правила: `work/f6_p2d_rules.py`; ручные решения: `work/f6_p2d_manual.py`; '
         f'протокол применённого: `scripts/_f6_p2d_sanction.json`; приёмка: `scripts/f6_p2d_check.py`.\n')
if san: L.append(f'Применено: {san["_meta"]["applied"]}; результат: `{json.dumps(san["_meta"]["result"], ensure_ascii=False)}`.\n')
L.append('## §0. Сводка\n')
L.append(f'- Записей с правками: **{len(SET)}**; операций: **{sum(cnt.values())}**.')
L.append('- Alignment и мастер содержательно не менялись (переименованы p2 → p2d); титулы/годы/студии/жанры каталога — без изменений (И5′).')
L.append('- Реестр: +cat2958 annotation/source-only (после снятия библиографии осталась формула источника). Инварианты И1′–И6 в apply.')
L.append('- Принципы: (1) значения слов не домысливались — исключение класс M (латиница/цифра/символ вместо буквы при однозначном чтении, все перечислены в §2); '
         '(2) буквенные OCR-ошибки внутри кириллических слов («удовлетзорен», «Опа») в П2д НЕ правились — отдельный список кандидатов `veto/П2д_кандидаты_OCR_буквы.xlsx`; '
         '(3) «...» в начале аннотаций (авторский стиль каталога) сохранён; вложенные кавычки «…«…»» — как в каталоге.\n')
L.append('| класс | операций | описание |\n|---|---:|---|')
for k in ['B', 'M', "C'", 'C"', 'C*', 'WS', 'C•', 'C’', 'C■', 'C^', 'C.', 'P', 'T', 'D', 'A', 'BIB', 'C>', 'R', 'C<', 'J', 'C×', 'C|', 'C„', 'E', 'L']:
    if k in cnt: L.append(f'| {k} | {cnt[k]} | {CL[k]} |')
L.append('')
# §1 ручные правки M
L.append('## §1. Ручные точечные правки (класс M) — полный список\n')
L.append('Правило допуска: слово с латиницей/цифрой/мусорным символом вместо буквы восстановлено только если чтение однозначно по контексту и словарю; '
         'колонтитулы/сигнатуры («Зак. №», «Сов. худ. фильмы вып.», «ВЭ …», «Стр. …»), обрывки списков ролей с разрыва страницы и оглавление тома сняты как не-проза. '
         'Восстановления по печати помечены источником.\n')
L.append('| cat | название | том | было | стало |\n|---|---|---|---|---|')
for c, o in ops_all:
    if o[0] == 'M':
        x = by[c]; L.append(f'| {c} | {esc(x["title"])} | {x["vol"]} | {q(o[1][:160])} | {q(o[2][:160]) if o[2] else "—"}{" ("+o[3]+")" if len(o) > 3 else ""} |')
L.append('')
# §2 реконструкции и вырезки
L.append('## §2. Реконструкции и вырезки\n')
L.append('### §2.1. Класс R — «1-я серия» (цифра «1» потеряна сканом; в той же аннотации далее есть «2-я серия»)\n')
L.append('| cat | название | было | стало |\n|---|---|---|---|')
for c, o in ops_all:
    if o[0] == 'R': L.append(f'| {c} | {esc(by[c]["title"])} | {q(o[1])} | {q(o[2])} |')
L.append('\n### §2.2. Класс P — номер страницы внутри прозы (граница страниц без переноса); проверка: число ≈ ожидаемой странице записи по якорям класса A\n')
L.append('| cat | название | том | убрано | контекст |\n|---|---|---|---|---|')
for c, o in ops_all:
    if o[0] == 'P':
        x = by[c]; b = x['before']; k = re.search(r'\s' + re.escape(o[1]) + r'\s', b).start()
        L.append(f'| {c} | {esc(x["title"])} | {x["vol"]} | {o[1]} | …{esc(b[max(0, k - 35):k + len(o[1]) + 36])}… |')
L.append('\n### §2.3. Класс A — номер страницы/колонтитул внутри переноса\n')
L.append('| cat | было | стало |\n|---|---|---|')
for c, o in ops_all:
    if o[0] == 'A': L.append(f'| {c} | {q(o[1])} | {q(o[2])} |')
L.append('\n### §2.4. Классы T / BIB / L / J — вырезки хвостов и голов\n')
L.append('| cat | название | класс | вырезано (начало) |\n|---|---|---|---|')
for c, o in ops_all:
    if o[0] in ('T', 'BIB', 'L', 'J'): L.append(f'| {c} | {esc(by[c]["title"])} | {o[0]} | {q(o[1][:120])} |')
L.append('')
# §3 символьные классы
L.append('## §3. Символьные классы — полные списки\n')
for k in ('C*', 'C^', 'C’', "C'", 'C.', 'C<', 'C>', 'D', 'E', 'C„', 'C×', 'C|'):
    if k not in cnt: continue
    L.append(f'### {k} — {CL[k]} ({cnt[k]})\n')
    L.append('| cat | было | стало |\n|---|---|---|')
    for c, o in ops_all:
        if o[0] == k: L.append(f'| {c} | {q(o[1][:100])} | {q(o[2][:100]) if o[2] else "—"} |')
    L.append('')
for k in ('C"', 'C■', 'C•'):
    if k not in cnt: continue
    L.append(f'### {k} — {CL[k]} ({cnt[k]}) — по записям (дифф)\n')
    L.append('| cat | изменения |\n|---|---|')
    for x in SET:
        if any(o[0] == k for o in x['ops']):
            L.append(f'| {x["cat"]} | ' + '<br>'.join(diffs(x['before'], x['after'])[:6]) + ' |')
    L.append('')
L.append(f'### WS — пробелы/одиночные знаки препинания ({cnt.get("WS", 0)}): cat ' + ', '.join(str(c) for c, o in ops_all if o[0] == 'WS') + '\n')
# §4 переносы B
L.append('## §4. Класс B — внутристрочные переносы «w1- w2» — полный список по правилам\n')
groups = collections.defaultdict(list)
for c, o in ops_all:
    if o[0] == 'B': groups[o[3] if len(o) > 3 else '?'].append((c, o))
for why, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    L.append(f'### {why} ({len(items)})\n')
    L.append('| cat | было | стало |\n|---|---|---|')
    for c, o in items: L.append(f'| {c} | {q(o[1])} | {q(o[2])} |')
    L.append('')
L.append('### KEEP_HYPH — дефис сохранён вручную\n')
for c, w in sorted(M.KEEP_HYPH): L.append(f'- cat{c}: {q(w)}')
L.append('\n### Не решено (оставлено как есть)\n')
for c, ms in json.load(open('work/f6_p2d_manual.json', encoding='utf-8')):
    for m in ms: L.append(f'- cat{c}: {q(m[1])} — {m[2]}')
L.append('')
# §5 полный дифф
L.append('## §5. Полный дифф по записям (все изменения, контекст ±28 зн.)\n')
L.append('| cat | название | классы | изменения |\n|---|---|---|---|')
for x in SET:
    L.append(f'| {x["cat"]} | {esc(x["title"])} | {x["class"][4:]} | ' + '<br>'.join(diffs(x['before'], x['after'])[:12]) + ' |')
L.append('')
L.append('## §6. Реестр\n\n- +cat2958 «' + esc(by[2958]['title']) + '» annotation/source-only: ' + esc(res['register']['add'][0]['reason']) + '\n')
os.makedirs('veto', exist_ok=True)
open('veto/ВЕТО_Ф6_П2д.md', 'w', encoding='utf-8').write('\n'.join(L))
print('veto:', len(L), 'строк;', os.path.getsize('veto/ВЕТО_Ф6_П2д.md') // 1024, 'KB')
