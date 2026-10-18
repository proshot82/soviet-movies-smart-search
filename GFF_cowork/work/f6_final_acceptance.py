# -*- coding: utf-8 -*-
"""Ф6: отчёт приёмки финального каталога v2 (после П3а/П3б/П3в) по критериям готовности (handoff §4) + регрессионная сверка со старым каталогом → veto/ПРИЁМКА_Ф6.md"""
import json, re, hashlib, os
from collections import Counter, defaultdict
cat = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
cmp = json.load(open('work/f6_ref_compare_v2.json', encoding='utf-8'))
lost = json.load(open('work/f6_ref_lost3.json', encoding='utf-8'))
san_a = json.load(open('scripts/_f6_p3a_sanction.json', encoding='utf-8')); san_b = json.load(open('scripts/_f6_p3b_sanction.json', encoding='utf-8')); san_v = json.load(open('scripts/_f6_p3v_sanction.json', encoding='utf-8'))
cred_bl = json.load(open('work/f6_p3b_cred_cands.json', encoding='utf-8'))
old = json.load(open('reference/catalog_old_from_db.json', encoding='utf-8'))
al = json.load(open('state/alignment_final.json', encoding='utf-8'))
m = json.load(open('state/index_master_final.json', encoding='utf-8'))
reg = json.load(open('state/Ф5_стабы_реестр.json', encoding='utf-8'))
q = json.load(open('state/Ф5_очередь_docx.json', encoding='utf-8'))
N = len(cat); sha = hashlib.sha256(open('state/catalog_final_v2.json', 'rb').read()).hexdigest()
VOLS = [f'v{i}_' + s for i, s in zip(range(1, 16), ['1918-1935', '1936-1957', '1958-1963', '1964-1965', '1966-1967', '1968-1969', '1970-1971', '1972-1973', '1974-1975', '1976-1977', '1978-1979', '1980-1981', '1982-1983', '1984-1985', '1986-1987'])]
L = []
L.append('# ПРИЁМКА Ф6 — финальный каталог `state/catalog_final_v2.json`\n')
L.append(f'Дата: 2026-09-04. Каталог **{N}** записей, sha256 `{sha}`. Схема: `id` (1..{N}), `title`, `genre`, `year`, `studio`, `annotation`, `source`. '
         'Версия v2 = v1 (П3, 7173) + корректирующие пакеты П3а/П3б по итогам регрессионной сверки со старым каталогом (`veto/ВЕТО_Ф6_П3а.md`) + П3в — срез титров, поглощённых аннотациями (`veto/ВЕТО_Ф6_П3в.md`). Приёмка воспроизводима: `python3 scripts/f6_final_check.py` (сверяет с `backups/catalog_final_v1.json`, `scripts/_f6_p3a_sanction.json`, `scripts/_f6_p3b_sanction.json`, `scripts/_f6_p3v_sanction.json`). '
         'Сопутствующие файлы: `state/alignment_final.json`, `state/index_master_final.json`, `state/Ф5_стабы_реестр.json`, `state/Ф5_очередь_docx.json`.\n')
L.append('## Сводка по критериям готовности (handoff §4)\n')
L.append('| № | критерий | результат |')
L.append('|---|---|---|')
L.append(f'| 1 | все записи захвачены (ориентир ≥ 6857) | **{N}** записей; 15 томов, по томам — таблица §1; 59 страёв удалены Ф6-П1 по диспозиции (`veto/ВЕТО_Ф5_финал_страи.md`, `veto/ВЕТО_Ф6_П1.md`); **регрессия со старым каталогом движка** (`reference/catalog_old_from_db.json` = слой `catalog_all_v4.json`, 6857 записей, экспорт владельца 04.09.2026): сопоставлены **6857 из 6857** (§9), потерянных записей 0; найденная сверкой отсутствовавшая статья «Старый наездник» (1940, v2 @3136, литерный №1628а) вставлена П3а (id 1629); записей нового каталога, которых нет в старом, — {len(cmp["unmatched_new"])} (§9); список 197 пропусков исходного парсера как файл в `reference/` отсутствует — критерий закрыт сверкой с самим старым каталогом |')
short = [r for r in cat if r['annotation'] is not None and len(r['annotation']) < 100]
regset = {e['cat'] for e in reg['entries'] if e['field'] == 'annotation'}
L.append(f'| 2 | аннотации полные | обрывы на границе страницы/строки закрыты: Ф6-П2 18 + Ф6-П3 42 (restore, `veto/ВЕТО_Ф6_П3.md` §2); сплошной проход «конец аннотации ↔ конец печатной прозы» (П3, все непустые аннотации); **печатный скан пропусков** (П3а, `work/f6_ref_gap_scan.py`: строки статьи, не покрытые аннотацией, все 7165 записей) — восстановлено {len(san_a["set"])} + {len([x for x in san_b["set"] if x["class"] == "gap-pre"])} аннотаций (утерянные логлайны/примечания/формулы источника, ложные головы «В РСФСР…», новеллы альманахов, обрыв начала; `veto/ВЕТО_Ф6_П3а.md` §4–§5); повторный скан после П3а/П3б — печатной прозы вне аннотаций не осталось (остаток — титры/библиография/призы/соседние статьи); регрессия аннотаций со старым каталогом (§9): предложений старого, отсутствующих в новом и лежащих в печати внутри статьи как проза, — 0 после П3б (24 позиции — OCR-склейки старого каталога, титры сюжетов, соседние статьи; §9); список 542 обрезок исходного парсера как файл отсутствует — закрыт той же сверкой; аннотаций < 100 знаков у не-None — {len(short)} (в реестре {sum(1 for r in short if r["id"] - 1 in regset)}; вне реестра {sum(1 for r in short if r["id"] - 1 not in regset)} — однофразные, §3); маркеров титров/библиографии — 0; призовых блоков в конце — 0 |')
none = {f: [r['id'] for r in cat if r[f] is None] for f in ('genre', 'studio', 'annotation', 'year')}
L.append(f"| 3 | поля чистые | пустые: genre {len(none['genre'])}, studio {len(none['studio'])}, annotation {len(none['annotation'])}, year 0 — все в реестре (`Ф5_стабы_реестр.json`, 111 позиций, счётчики `{json.dumps(reg['counts'], ensure_ascii=False)}`); уникальных genre **{len({r['genre'] for r in cat if r['genre']})}**, studio **{len({r['studio'] for r in cat if r['studio']})}** (инвентари §4–§5); годы 1918–1987, гистограммы §2; OCR-мусор/сигнатуры/латиница — см. §6 |")
cards = {r['cat_pos']: r for r in m['rows'] if r['kind'] == 'card'}
def nm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))
diff = [(r['id'], r['title'], cards[r['id'] - 1]['title_canon']) for r in cat if nm(re.sub(r'\s*\(«.*$', '', r['title'])) != nm(cards[r['id'] - 1]['title_canon']) and nm(r['title']) != nm(cards[r['id'] - 1]['title_canon'])]
L.append(f"| 4 | титулы сверены с указателем | мастер-индекс `index_master_final.json` (эталон — `Госфильмофонд_именной_указатель_19181987.xlsx`, 7195 строк): card-строк {len(cards)} = биекция с каталогом; нормализованных расхождений title ↔ title_canon: **{len(diff)}** — {'; '.join(f'id {i} «{t}» vs «{c}» (намеренно: полная печатная голова vs короткая форма указателя, вето П2 §5 п.3)' for i, t, c in diff)}; `alignment.master_title` == `title_canon` всюду |")
dups = [(k, [r['id'] for r in cat if (r['title'], r['year']) == k]) for k, c in Counter((r['title'], r['year']) for r in cat).items() if c > 1]
dups3 = [k for k, c in Counter((r['title'], r['year'], r['studio']) for r in cat).items() if c > 1]
L.append(f"| 5 | точные дубли title+year | **{len(dups)}** пары, все законные (разные фильмы разных студий): {'; '.join(f'«{t}» {y} — id {ids} ({cat[ids[0]-1][chr(115)+chr(116)+chr(117)+chr(100)+chr(105)+chr(111)]} / {cat[ids[1]-1][chr(115)+chr(116)+chr(117)+chr(100)+chr(105)+chr(111)]})' for (t, y), ids in dups)}; дублей title+year+studio — {len(dups3)} (ключ дедупликации импорта П4) |")
L.append(f'| 6 | сверка с `reference/catalog_all_v21.json` | файла в папке нет; вместо него — **сверка со старым каталогом движка** (`reference/catalog_old_from_db.json`, слой catalog_all_v4, 6857): все 6857 сопоставлены с записями v2 (методы §9), аннотации по классам §9; расхождения объяснены (обрезки/контаминация старого, титры/библиография/призы, вырезанные по канону) — §9; по итогам: +1 запись, 1 титул, 60 аннотаций (П3а/П3б) |')
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
L.append('- Канон аннотаций киножурналов: 62 записи «Фитиль» содержат студии сюжетов после заголовков (разнобой с каноном k4) — бэклог (вето П3 §6 п.1); П3а пересобрал по канону 2 из них (id 4016, 6810).')
bl = [c for c in cred_bl if c['cat'] not in (2076, 4732)]
L.append(f"- Титры, поглощённые аннотациями (строки блока титров до первой строки прозы, титровые строки/обрывки списков ролей внутри аннотаций): по решению владельца («срезать», список §7 п.1 вето П3а — {len({c['cat'] for c in bl})} записей) пакет **П3в** срезал их во всех записях того же класса, найденных печатными сканами: **{len(san_v['set'])} записей** {json.dumps(san_v['_meta']['result']['set_by_class'], ensure_ascii=False)} (`veto/ВЕТО_Ф6_П3в.md`, протокол `scripts/_f6_p3v_sanction.json`); П3б ранее срезал 2 (id 2077, 4733). Не срезались по конвенциям: записи концертных жанров (П2), примечания о производстве без исполнителей («по заказу…», «при участии киностудий…», «Съемки производились…»), статусные примечания, предложения внутри абзаца прозы, студийные хвосты сюжетов «Фитиля» (бэклог) — списки в вето П3в §4. Повторные сканы после П3в: остаток — только эти классы.")
L.append('- OCR-остатки в восстановленных П3а текстах (как в печати, не правились): id 3059 «заведущая», id 3476 «Попраный обет», id 3158 «кочетару», id 1629 (вставленная запись) — пропущенные OCR точки внутри прозы («испытания Старый», «рекордсмена Иные», «ипподрома Это») и без конечного знака; бэклог П2ж.\n')
# §7 alignment / master / реестр
L.append('## §7 Alignment, мастер-индекс, реестр, очередь\n')
kinds = Counter(r['kind'] for r in m['rows'])
L.append(f"- `alignment_final.json`: {len(al)} строк, `cat_pos` = индекс, `id` = cat_pos + 1, `xlsx_row` всюду заполнен и уникален, `cat_pos_f5` — индекс Ф5; методы: {dict(Counter(a['method'] for a in al))}.")
L.append(f"- `index_master_final.json`: rows {len(m['rows'])} = {dict(kinds)}; card = биекция с каталогом (`cat_pos`, `id`); некарточные 30 (crossref 22 — перекрёстные ссылки указателя «см. …», unbound 8 — строки xlsx без записи каталога: склейки OCR/дубли альт-названий, сняты в Ф1–Ф3); литерные номера {m['_meta']['stats']['литерные номера']}; синтетических xlsx_row > 7195 — {sum(1 for r in m['rows'] if r['xlsx_row'] > 7195)}.")
L.append(f"- Реестр законных пустот/формул/стабов: {len(reg['entries'])} позиций: {json.dumps(reg['counts'], ensure_ascii=False)}; закрытые: closed_f6_p2 {len(reg.get('closed_f6_p2', []))}, closed_f6_p3 {len(reg.get('closed_f6_p3', []))}. Очередь docx: терминалы genre {len(q['genre'])}, studio_empty {len(q['studio_empty'])}, annotation {len(q['annotation'])}.\n")
# §8 П4
L.append('## §8 Готовность к Ф6-П4 (импорт в чистую БД)\n')
L.append('- Ключ дедупликации `film_search.py import` расширить до (title, year, studio) — решение владельца 02.09.2026; патч и обновлённый `db_check.py` — `scripts/p4/` (`db_check.py` с эталонными счётчиками **7174** / дубли title+year = 3 законных; каталог для импорта — `state/catalog_final_v2.json`).')
L.append('- Импорт только в **чистую** `gosfilmofond.db` (файла в папке быть не должно); `film_id` при чистом импорте совпадёт с `id` каталога (autoincrement по порядку записей, пропусков нет: пустых титулов 0, дублей по ключу 0).')
L.append('- Порядок: `import` → `make_chunks` (в import) → `embed` (единственный платный шаг) → `build_fts` → `db_check` → смок-тесты. Импортировать **только v2** (7174): `id` со «Старого наездника» (1629) сдвинуты на +1 относительно v1 — импорт v1 дал бы иные film_id.')
# §9 регрессия
L.append('\n## §9 Регрессионная сверка со старым каталогом движка (`reference/catalog_old_from_db.json`)\n')
meth = Counter(re.sub(r'\(.*\)', '', p['method']) for p in cmp['pairs'])
L.append(f"- Старый каталог: {cmp['old_n']} записей (слой catalog_all_v4.json старой gosfilmofond.db; титулы в верхнем регистре, OCR-мусор в титулах/студиях, аннотации без чистки). Сопоставление старый → v2 (`work/f6_ref_compare_v2.py`): автоматически {cmp['matched']} — по методам {dict(meth)}; вручную 6 (OCR-мусор титула старого: «М. Горького в новой редакции» → id 1683 «Первопечатник Иван Федоров»; «ВАНЯ» → id 4335 «Дядя Ваня»; «РУ 22.1» → id 4620 «Иванов катер»; «ЖГГПШ! № 158» → id 5155 «Фитиль № 158»; «НЕСКОЛЬКО ДНЕЙ ИЗ ЖИЗНИ И» → id 5741; «ЖАПО&А» → id 6861 «Жалоба»). Итого **6857/6857**, кратных привязок 0.")
L.append(f"- Записи v2 без пары в старом каталоге — **{len(cmp['unmatched_new'])}** (пропуски исходного парсера, восстановленные Ф4/Ф5/Ф6, и записи, отсутствовавшие в старой БД): по томам {dict(Counter(u['source'].split('_')[0] for u in cmp['unmatched_new']))}; полный список — `work/f6_ref_compare_v2.json` (`unmatched_new`).")
ac = cmp['ann_classes']
L.append(f"- Аннотации сопоставленных пар (норм. текст): equal {ac.get('equal', 0)}; старая — префикс новой (обрезка старого закрыта) {ac.get('old_prefix', 0)}; старая внутри новой (снят лид/восстановлено начало) {ac.get('old_inside', 0)}; общий префикс ≥ 40 знаков {ac.get('common_prefix', 0)}; новая — префикс/внутри старой (в старом — титры/библиография/призы/контаминация соседней статьёй, срезанные по канону) {ac.get('new_prefix_of_old', 0)}+{ac.get('new_inside_old', 0)}; different {ac.get('different', 0)}; пустые: old-none {ac.get('old-none', 0)}, new-none {ac.get('new-none', 0)}, both {ac.get('both-none', 0)}.")
lc = Counter((x['loc'], x['kind']) for x in lost)
L.append(f"- Предложения старых аннотаций, отсутствующие в новой аннотации той же записи (probe/ratio ≥ 0.75; `work/f6_ref_lost3.py`): {len(lost)} в {len({x['id'] for x in lost})} записях; локализация в печати: вне статьи записи (контаминация старого каталога соседними статьями) {lc[('elsewhere', None)]}; внутри статьи — библиография {lc[('in_article', 'bib')]}, титры/списки ролей {lc[('in_article', 'cred')]}, призы {lc[('in_article', 'prize')]}, головы/метраж {lc[('in_article', 'head')]}, проза соседней записи (границы статей) {lc[('in_article', 'neighbour')]}, проза {lc[('in_article', 'prose')]}; в печати не найдены (OCR-варианты/иной источник старого) {lc[('not_found', None)]}. Остаток «проза» ({lc[('in_article', 'prose')]}) проверен поштучно: OCR-склейки старого каталога (обрывки предложений с инициалами), титульные строки сюжетов, контаминация — потерь нет.")
from collections import defaultdict as _dd
bp = _dd(list)
for x in lost: bp[x['i']].append((x['loc'], x['kind']))
def _pc(i):
    ks = bp.get(i)
    if not ks: return 'потерь предложений нет'
    if all(l == 'elsewhere' for l, k in ks): return 'только контаминация (текст соседних статей в старом)'
    if all(l == 'in_article' and k in ('bib', 'cred', 'prize', 'head', 'cast') for l, k in ks): return 'только титры/библиография/призы (срезаны по канону)'
    if all(l == 'not_found' for l, k in ks): return 'только OCR-варианты/иной источник'
    if any(l == 'in_article' and k in ('prose', 'neighbour') for l, k in ks): return 'проверено поштучно (проза соседей / OCR-склейки старого)'
    return 'смешанное (титры + контаминация + OCR)'
pcs = Counter(_pc(p['i']) for p in cmp['pairs'])
L.append(f"- По парам: {'; '.join(f'{k} — {v}' for k, v in pcs.most_common())} (ручные 6 пар — в классе «проверено поштучно»).")
L.append(f"- По итогам сверки и печатного скана пропусков применены П3а (`scripts/_f6_p3a_sanction.json`: {len(san_a['set'])} аннотаций {json.dumps(san_a['_meta']['result']['set_by_class'], ensure_ascii=False)}, титул id 709, вставка id 1629 «Старый наездник») и П3б (`scripts/_f6_p3b_sanction.json`: gap-pre 2, cred-cut 2). Протокол — `veto/ВЕТО_Ф6_П3а.md`. Затем П3в (`scripts/_f6_p3v_sanction.json`: {len(san_v['set'])} аннотаций {json.dumps(san_v['_meta']['result']['set_by_class'], ensure_ascii=False)}, только срезы титров) — `veto/ВЕТО_Ф6_П3в.md`.")
open('veto/ПРИЁМКА_Ф6.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('written', sum(len(x) for x in L))
