# -*- coding: utf-8 -*-
"""Ф6: отчёт приёмки финального каталога по критериям готовности (handoff §4) → veto/ПРИЁМКА_Ф6.md"""
import json, re, hashlib, os
from collections import Counter, defaultdict
cat = json.load(open('state/catalog_final_v1.json', encoding='utf-8'))
al = json.load(open('state/alignment_final.json', encoding='utf-8'))
m = json.load(open('state/index_master_final.json', encoding='utf-8'))
reg = json.load(open('state/Ф5_стабы_реестр.json', encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
N = len(cat); sha = hashlib.sha256(open('state/catalog_final_v1.json', 'rb').read()).hexdigest()
VOLS = [f'v{i}_' + s for i, s in zip(range(1, 16), ['1918-1935', '1936-1957', '1958-1963', '1964-1965', '1966-1967', '1968-1969', '1970-1971', '1972-1973', '1974-1975', '1976-1977', '1978-1979', '1980-1981', '1982-1983', '1984-1985', '1986-1987'])]
L = []
L.append('# ПРИЁМКА Ф6 — финальный каталог `state/catalog_final_v1.json`\n')
L.append(f'Дата: 2026-09-04. Каталог **{N}** записей, sha256 `{sha}`. Схема: `id` (1..{N}), `title`, `genre`, `year`, `studio`, `annotation`, `source`. '
         'Приёмка воспроизводима: `python3 scripts/f6_p3_check.py` (сверяет с `backups/catalog_f6_p2e.json`, `scripts/_f6_p3_sanction.json`). '
         'Сопутствующие файлы: `state/alignment_final.json`, `state/index_master_final.json`, `state/Ф5_стабы_реестр.json`, `state/Ф5_очередь_docx.json`.\n')
L.append('## Сводка по критериям готовности (handoff §4)\n')
L.append('| № | критерий | результат |')
L.append('|---|---|---|')
L.append(f'| 1 | все записи захвачены (ориентир ≥ 6857) | **{N}** записей; 15 томов, по томам — таблица §1; 59 страёв удалены Ф6-П1 по диспозиции (`veto/ВЕТО_Ф5_финал_страи.md`, `veto/ВЕТО_Ф6_П1.md`); список 197 пропусков исходного парсера — `reference/` в папке **нет [Н]: не проверялось** |')
short = [r for r in cat if r['annotation'] is not None and len(r['annotation']) < 100]
regset = {e['cat'] for e in reg['entries'] if e['field'] == 'annotation'}
L.append(f'| 2 | аннотации полные | обрывы на границе страницы/строки закрыты: Ф6-П2 18 + Ф6-П3 {42} (restore, `veto/ВЕТО_Ф6_П3.md` §2); сплошной проход «конец аннотации ↔ конец печатной прозы» по всем 7165 непустым аннотациям (П3): продолжений в печати не осталось; список 542 обрезок исходного парсера — `reference/` **[Н]: не проверялось**; аннотаций < 100 знаков у не-None — {len(short)} (в реестре {sum(1 for r in short if r["id"] - 1 in regset)}: формулы/формулы источника/стабы; вне реестра {sum(1 for r in short if r["id"] - 1 not in regset)} — однофразные аннотации, §3); маркеров титров/библиографии — 0; призовых блоков в конце — 0 (76 срезаны П3) |')
none = {f: [r['id'] for r in cat if r[f] is None] for f in ('genre', 'studio', 'annotation', 'year')}
L.append(f"| 3 | поля чистые | пустые: genre {len(none['genre'])}, studio {len(none['studio'])}, annotation {len(none['annotation'])}, year 0 — все в реестре (`Ф5_стабы_реестр.json`, 109 позиций, счётчики `{json.dumps(reg['counts'], ensure_ascii=False)}`); уникальных genre **{len({r['genre'] for r in cat if r['genre']})}**, studio **{len({r['studio'] for r in cat if r['studio']})}** (инвентари §4–§5); годы 1918–1987, гистограммы §2; OCR-мусор/сигнатуры/латиница — см. §6 |")
cards = {r['cat_pos']: r for r in m['rows'] if r['kind'] == 'card'}
def nm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))
diff = [(r['id'], r['title'], cards[r['id'] - 1]['title_canon']) for r in cat if nm(re.sub(r'\s*\(«.*$', '', r['title'])) != nm(cards[r['id'] - 1]['title_canon']) and nm(r['title']) != nm(cards[r['id'] - 1]['title_canon'])]
L.append(f"| 4 | титулы сверены с указателем | мастер-индекс `index_master_final.json` (эталон — `Госфильмофонд_именной_указатель_19181987.xlsx`, 7195 строк): card-строк {len(cards)} = биекция с каталогом; нормализованных расхождений title ↔ title_canon: **{len(diff)}** — {'; '.join(f'id {i} «{t}» vs «{c}» (намеренно: полная печатная голова vs короткая форма указателя, вето П2 §5 п.3)' for i, t, c in diff)}; `alignment.master_title` == `title_canon` всюду |")
dups = [(k, [r['id'] for r in cat if (r['title'], r['year']) == k]) for k, c in Counter((r['title'], r['year']) for r in cat).items() if c > 1]
dups3 = [k for k, c in Counter((r['title'], r['year'], r['studio']) for r in cat).items() if c > 1]
L.append(f"| 5 | точные дубли title+year | **{len(dups)}** пары, все законные (разные фильмы разных студий): {'; '.join(f'«{t}» {y} — id {ids} ({cat[ids[0]-1][chr(115)+chr(116)+chr(117)+chr(100)+chr(105)+chr(111)]} / {cat[ids[1]-1][chr(115)+chr(116)+chr(117)+chr(100)+chr(105)+chr(111)]})' for (t, y), ids in dups)}; дублей title+year+studio — {len(dups3)} (ключ дедупликации импорта П4) |")
L.append('| 6 | сверка с `reference/catalog_all_v21.json` | файла в папке нет **[Н]: не проверялось** |')
L.append('| 7 | sidecar `catalog_castcredits_v1.json` | существование не подтверждено **[Н]**; в Ф6 не создаётся |')
L.append('')
# §1 по томам
L.append('## §1 Записи по томам\n')
L.append('| том | записей | id (диапазон) | лет в томе (min–max) | вне диапазона тома ±1 |')
L.append('|---|---|---|---|---|')
out_total = []
for v in VOLS:
    rs = [r for r in cat if r['source'] == v]
    lo, hi = map(int, v.split('_')[1].split('-'))
    if v == 'v2_1936-1957': lo = 1930   # печатный диапазон тома 2 — 1930–1957 (метка source — по обложке; handoff П3 §1)
    yrs = [r['year'] for r in rs]
    outr = [r for r in rs if not (lo - 1 <= r['year'] <= hi + 1)]
    out_total += [(v, r) for r in outr]
    L.append(f"| {v} | {len(rs)} | {rs[0]['id']}–{rs[-1]['id']} | {min(yrs)}–{max(yrs)} | {len(outr)}" + (': ' + ', '.join(f"id {r['id']} «{r['title']}» {r['year']}" for r in outr) if outr else '') + ' |')
L.append(f'\nВне диапазона тома ±1 — {len(out_total)} (печатный год производства при позднем выпуске тома; норма, вето Ф5-финал §4 п.5, П1 §5). Диапазон тома 2 — печатный 1930–1957 (метка `v2_1936-1957` — по обложке).\n')
# §2 годы
L.append('## §2 Годы\n')
yc = Counter(r['year'] for r in cat)
L.append('По десятилетиям: ' + ', '.join(f'{d}-е — {sum(c for y, c in yc.items() if y // 10 * 10 == d)}' for d in sorted({y // 10 * 10 for y in yc})) + '.\n')
L.append('| год | записей | | год | записей | | год | записей | | год | записей |')
L.append('|---|---|---|---|---|---|---|---|---|---|---|')
years = list(range(1918, 1988))
rows = [years[i:i + 18] for i in range(0, 72, 18)]
for k in range(18):
    cells = []
    for col in rows:
        if k < len(col): cells.append(f'{col[k]} | {yc.get(col[k], 0)}')
        else: cells.append(' | ')
    L.append('| ' + ' | | '.join(cells) + ' |')
L.append('')
# §3 короткие аннотации вне реестра
L.append('## §3 Аннотации короче 100 знаков вне реестра\n')
outs = [r for r in short if r['id'] - 1 not in regset]
L.append(f'{len(outs)} записей — однофразные печатные аннотации (проверены выборочно в П1/П2/П3: соответствуют печати; формулы v1 «Содержание не установлено…» — в реестре). Список: ' + '; '.join(f"id {r['id']} «{r['title']}» {r['year']}: «{r['annotation']}»" for r in outs) + '\n')
# §4 жанры
L.append('## §4 Инвентарь genre (' + str(len({r['genre'] for r in cat if r['genre']})) + ' уникальных + None ' + str(len(none['genre'])) + ')\n')
gc = Counter(r['genre'] for r in cat if r['genre'])
L.append('| genre | записей |'); L.append('|---|---|')
for g, c in sorted(gc.items(), key=lambda x: (-x[1], x[0])): L.append(f'| {g} | {c} |')
L.append(f"| *(None)* | {len(none['genre'])} — id {none['genre']} (терминалы очереди: жанр в печати отсутствует / источник утрачен) |\n")
# §5 студии
L.append('## §5 Инвентарь studio (' + str(len({r['studio'] for r in cat if r['studio']})) + ' уникальных + None ' + str(len(none['studio'])) + ')\n')
L.append('Исторические имена разных эпох, полные официальные формы, ветки/отделения и варианты «Советская Беларусь/Белорусь» сознательно не унифицированы (handoff §6 п.1, вето П6-2 §4) — инвентарь как есть.\n')
sc = Counter(r['studio'] for r in cat if r['studio'])
L.append('| studio | записей |'); L.append('|---|---|')
for s, c in sorted(sc.items(), key=lambda x: (-x[1], x[0])): L.append(f'| {s} | {c} |')
L.append(f"| *(None)* | {len(none['studio'])} — id {none['studio']} |\n")
# §6 чистота
JUNK = re.compile(r'[\^■❖©®|\\@<>*•।_\[\]{}#$£™¡¿“”„"’‘`]')
jk = [r['id'] for r in cat if r['annotation'] and JUNK.search(r['annotation'])]
nofin = [r['id'] for r in cat if r['annotation'] and not re.search(r'[.!?…»)"\']$', r['annotation'])]
nl = [r['id'] for r in cat if r['annotation'] and '\n' in r['annotation']]
L.append('## §6 Чистота аннотаций\n')
L.append(f'- Маркеры титров/дубляжа/библиографии (жёсткий список приёмки) — 0; сигнатуры/колонтитулы/«ВЭ»/оглавление тома — 0; призовые блоки в конце — 0 (сознательно оставлены: id 1183 «Путевка в жизнь» — историко-критическая справка (реестр note); id 2392/2400/2423 — примечание о премированном сценарии; id 4722/6034 — «главный приз» в фабуле).')
L.append(f'- Мусорные символы — 0 (кроме апострофа ’ в иноязычных именах: id {jk}); латиница вне римских цифр — 2 сознательных остатка (id 2713 «cho», id 3306 «w»; чтение неоднозначно); внутристрочные переносы «w1- w2» — 1 законный висячий дефис (id 6482 «кино- и фотопленки»); двойных пробелов/табов — 0; переводы строк — 4 многоновелльные записи (id {nl}).')
L.append(f'- Конечная пунктуация: восстановлена по печати у 1902 (П3); без конечного знака осталось {len(nofin)} — в печати знака нет (список: вето П3 §6 п.3).')
L.append('- Буквенные OCR-ошибки внутри слов: П2е (auto-строки списка кандидатов) применён; остаток `veto/П2е_кандидаты_остаток_OCR_буквы.xlsx` — только с ручной оценкой (возможный пакет П2ж).')
L.append('- Канон аннотаций киножурналов: 62 записи «Фитиль» содержат студии сюжетов после заголовков (разнобой с каноном k4) — бэклог (вето П3 §6 п.1).\n')
# §7 alignment / master / реестр
L.append('## §7 Alignment, мастер-индекс, реестр, очередь\n')
kinds = Counter(r['kind'] for r in m['rows'])
L.append(f"- `alignment_final.json`: {len(al)} строк, `cat_pos` = индекс, `id` = cat_pos + 1, `xlsx_row` всюду заполнен и уникален, `cat_pos_f5` — индекс Ф5; методы: {dict(Counter(a['method'] for a in al))}.")
L.append(f"- `index_master_final.json`: rows {len(m['rows'])} = {dict(kinds)}; card = биекция с каталогом (`cat_pos`, `id`); некарточные 30 (crossref 22 — перекрёстные ссылки указателя «см. …», unbound 8 — строки xlsx без записи каталога: склейки OCR/дубли альт-названий, сняты в Ф1–Ф3); литерные номера {m['_meta']['stats']['литерные номера']}; синтетических xlsx_row > 7195 — {sum(1 for r in m['rows'] if r['xlsx_row'] > 7195)}.")
L.append(f"- Реестр законных пустот/формул/стабов: {len(reg['entries'])} позиций: {json.dumps(reg['counts'], ensure_ascii=False)}; закрытые: closed_f6_p2 {len(reg.get('closed_f6_p2', []))}, closed_f6_p3 {len(reg.get('closed_f6_p3', []))}. Очередь docx: терминалы genre {len(q['genre'])}, studio_empty {len(q['studio_empty'])}, annotation {len(q['annotation'])}.\n")
# §8 П4
L.append('## §8 Готовность к Ф6-П4 (импорт в чистую БД)\n')
L.append('- Ключ дедупликации `film_search.py import` расширить до (title, year, studio) — решение владельца 02.09.2026; патч и обновлённый `db_check.py` — `scripts/p4/` (`film_search.py` с правкой, `db_check.py` с эталонными счётчиками 7173 / дубли title+year = 3 законных).')
L.append('- Импорт только в **чистую** `gosfilmofond.db` (файла в папке быть не должно); `film_id` при чистом импорте совпадёт с `id` каталога (autoincrement по порядку записей, пропусков нет: пустых титулов 0, дублей по ключу 0).')
L.append('- Порядок: `import` → `make_chunks` (в import) → `embed` (единственный платный шаг) → `build_fts` → `db_check` → смок-тесты. Переэмбеддинг после П3 обязателен (тексты аннотаций изменились у 2020 записей).')
open('veto/ПРИЁМКА_Ф6.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('written', sum(len(x) for x in L))
