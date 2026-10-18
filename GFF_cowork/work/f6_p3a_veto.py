# -*- coding: utf-8 -*-
"""Ф6-П3а/П3б: протокол применённого (карт-бланш) → veto/ВЕТО_Ф6_П3а.md"""
import json, hashlib, re
from collections import Counter
A = json.load(open('scripts/_f6_p3a_sanction.json', encoding='utf-8'))
B = json.load(open('scripts/_f6_p3b_sanction.json', encoding='utf-8'))
cat = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
cmp = json.load(open('work/f6_ref_compare_v2.json', encoding='utf-8'))
lost = json.load(open('work/f6_ref_lost3.json', encoding='utf-8'))
bl = [c for c in json.load(open('work/f6_p3b_cred_cands.json', encoding='utf-8')) if c['cat'] not in (2076, 4732)]
sha1 = A['_meta']['input_sha256']; sha2 = hashlib.sha256(open('state/catalog_final_v2.json', 'rb').read()).hexdigest()
ra = A['_meta']['result']
def esc(s): return (s or '').replace('|', '\\|').replace('\n', '⏎')
def added(x):
    b, a, c = x['before'], x['after'], x['class']
    if c in ('gap-pre', 'gap-head'): return a[:len(a) - len(b) - 1]
    if c == 'gap-post': return a[len(b) + 1:]
    if c == 'gap-mid':
        i = 0
        while i < min(len(a), len(b)) and a[i] == b[i]: i += 1
        return a[i:len(a) - (len(b) - i)]
    if c == 'gap-tailrepl': return a[len(b) - len('Фильм не сохранился.'):]
    if c == 'cred-cut': return '(снято) ' + b[:len(b) - len(a)]
    return a
L = []
L.append('# ВЕТО Ф6-П3а (+П3б) — корректирующие пакеты по итогам регрессионной сверки со старым каталогом: вставка записи, титул, утерянные строки аннотаций\n')
L.append(f"Применено: П3а {A['_meta']['applied']}, П3б {B['_meta']['applied']}; результат П3а: `{json.dumps(ra, ensure_ascii=False)}`; П3б: `{json.dumps(B['_meta']['result'], ensure_ascii=False)}`.\n")
L.append('Карт-бланш: протокол применённого, не запрос одобрения. Откат любой позиции — по `before` из `scripts/_f6_p3a_sanction.json` / `scripts/_f6_p3b_sanction.json` (или целиком: `backups/catalog_final_v1.json` + `backups/alignment_final_p3_*.json`, `backups/index_master_final_p3_*.json`, реестр/очередь с меткой времени → `state/`). Печатные строки — индексы `work/vN_lines.json` (@строка). Номера cat в таблицах — **индексы v2** (0-based; id = cat + 1); в скобках — индекс v1 там, где он отличается.\n')
L.append('## §0 Контрольные числа (приёмка `scripts/f6_final_check.py`)\n')
L.append(f"- Вход: `backups/catalog_final_v1.json` — 7173 (sha256 {sha1[:16]}…); выход: `state/catalog_final_v2.json` — **7174** (sha256 {sha2[:16]}…), удалений 0, вставок 1.")
L.append(f"- П3а: аннотации **{ra['set']}** {json.dumps(ra['set_by_class'], ensure_ascii=False)}; титул 1 (cat708/id 709); вставка 1 (cat1628/id 1629 «Старый наездник» 1940) → `id` записей с 1629 сдвинуты на +1 (id_v2 = id_v1 + 1 для id_v1 ≥ 1629). П3б: аннотации 4 (gap-pre 2, cred-cut 2). Прочие поля — байт-в-байт (И3, И5′ с учётом вставки); по томам: v2 +1 (И4).")
L.append(f"- `state/alignment_final.json` (7174): строки П3 + сдвиг `cat_pos`/`id` ≥ 1628, новая строка cat1628 (xlsx_row **{ra['new_master_row']}** синтетический, idx_num «1628а», method manual), `master_title` cat708 исправлен. `state/index_master_final.json`: rows 7204 (card 7174, crossref 22, unbound 8); +1 card-строка (xlsx_row {ra['new_master_row']}, num «1628а»); row 1088: title_canon «Что должен знать рабочий и крестьянин о СССР» (склейка xlsx разобрана, note); `_meta.f6_p3a`, stats: карточных 7174, литерные +«1628а», v2 1337. Биекция каталог ↔ alignment ↔ card (И6), `master_title` == `title_canon`, страёв 0.")
L.append(f"- Реестр `state/Ф5_стабы_реестр.json`: cat/id ≥ 1628 сдвинуты (+1) во всех списках; П3б: +cat4732 `annotation/source-only` → **110** позиций: `{json.dumps(B['_meta']['result']['register'], ensure_ascii=False)}`. Очередь docx: cat/id сдвинуты, терминалы без изменений.")
L.append('- Дубли title+year — те же 3 законные пары (id 28/29, 1207/1219, 7065/7066 — последняя сдвинута); title+year+studio — 0. Маркеры титров — 0; аннотаций без конечного знака — 118 (+1: вставленная запись, печать без знака).')
L.append('- Бэкапы: `backups/catalog_final_v1.json` (+ копия с меткой времени), `backups/alignment_final_p3_*.json`, `backups/index_master_final_p3_*.json`, `backups/catalog_final_v2_до_П3б_*.json`, реестр/очередь с метками времени. В `state/` ровно один каталог (`catalog_final_v2.json`), alignment, мастер.\n')
L.append('## §1 Метод\n')
L.append('1. **Регрессионная сверка** (`work/f6_ref_compare_v2.py`): старый каталог движка `reference/catalog_old_from_db.json` (слой catalog_all_v4.json, 6857; экспорт владельца из старой gosfilmofond.db) сопоставлен с финальным по норм. титулу (+без скобок) и году (±1), затем по началу аннотации (60 норм. знаков), по схожести титула (≥ 0.85), по окну аннотации; 6 остатков с OCR-мусорным титулом — вручную. Первый прогон (по v1) дал 8 несопоставленных старых записей: 6 OCR-титулов, «Что должен знать рабочий и крестьянин о СССР» (в v1 титул склеен из двух строк указателя) и «Старый наездник» (в v1 отсутствует).')
L.append('2. **Регрессия аннотаций** (`work/f6_ref_lost2.py` → `work/f6_ref_lost3.py`): предложения старой аннотации, отсутствующие в новой (проба 30 норм. знаков, ratio < 0.75), локализуются в печати тома: вне статьи записи → контаминация старого; внутри статьи → класс печатной строки (проза / титры / библиография / призы / голова / соседняя запись). Первый прогон вскрыл классы потерь: примечания «Сценарий…» и «В РСФСР/УССР…» (ложные головы), логлайны перед прозой, новеллы альманахов.')
L.append('3. **Печатный скан пропусков** (`work/f6_ref_gap_scan.py`, все 7165 непустых аннотаций; независим от старого каталога): область статьи [h2, E) по *настоящим* головам (метраж в строке / прописной титул + титры в следующих строках; ложные головы «В РСФСР фильм не демонстрировался.» больше не режут статью); покрытие каждой печатной строки аннотацией по пробам (устойчиво к чистке П2д); непокрытые строки классифицируются (PRE/GAP/POST × проза/титры/библиография/призы/голова/индекс) и отбираются (`work/f6_ref_gap_select.py`): не киножурналы (k4 — отдельный проход), не формулы, не титроподобные, не покрытые аннотацией соседней записи (границы статей при неопознанных головах). Каждый кандидат верифицирован по печатному контексту (`work/f6_p3_show.py`).')
L.append('4. **Резолюция** (`work/f6_p3a_manual.py` — спецификации @строк; `work/f6_p3a_build.py` → `scripts/f6_p3a_resolution.json`): текст — verbatim печать + чистка П2д (`work/f6_p3_clean.py`) + точечные OCR-правки с основанием (столбец M); титулы новелл/сюжетов — только начала печатных строк титров (анти-фабрикация, проверка в build). Apply `scripts/f6_apply_p3a.py` (пред-ассерты: вход = вход резолюции по sha256, before байт-в-байт, классы; И1′–И6 с учётом вставки; `--dry`). П3б: `work/f6_p3b_build.py` → `scripts/f6_p3b_resolution.json` → `scripts/f6_apply_p3b.py`.')
L.append('5. **Приёмка**: `scripts/f6_final_check.py` (независимо от apply: схема, по томам, биекции, реестр, санкции П3а+П3б воспроизводимы, прочие поля байт-в-байт, маркеры/мусор/латиница/переносы, титул ↔ мастер, годы); повторные проходы после применения: tail-scan (`work/f6_p3a_tail_scan.py`), gap-scan (`work/f6_ref_gap_scan_v2.py` + select) и регрессия (`work/f6_ref_lost3.py`) — печатной прозы вне аннотаций не осталось; отчёт `veto/ПРИЁМКА_Ф6.md` §9.\n')
ins = A['insert']; rec = ins['record']
L.append('## §2 Состав: вставка записи (1)\n')
L.append(f"- **cat1628 / id 1629 «{rec['title']}»** ({rec['year']}, {rec['genre']}, {rec['studio']}, `{rec['source']}`) — вставлена перед «Суворов» (id 1630, было 1629). Печать v2 @{ins['head_line']}: «{esc(ins['raw_head'])}»; титры @{ins['head_line'] + 1}–{ins['head_line'] + 2} (в аннотацию не входят); проза @{ins['lines'][0]}–{ins['lines'][-1]}. {ins['note']}.")
L.append(f"- Аннотация (verbatim после чистки; печать без конечного знака и с пропущенными OCR точками внутри — не правились, бэклог П2ж): «{esc(rec['annotation'])}»")
L.append(f"- Мастер: синтетическая card-строка xlsx_row {ra['new_master_row']} (num «1628а», provenance «synthetic: Ф6-П3а…»); alignment: method manual, confidence high, second_signal — печатная голова.\n")
t = A['title'][0]
L.append('## §3 Титул (1)\n')
L.append(f"- cat708 / id 709: «{esc(t['before'])}» → **«{t['after']}»**. {t['note']} Мастер row 1088: title_canon → новая форма, title_source «печатная голова v1 @{t['print_line']}», note о склейке; alignment.master_title синхронно; реестр/очередь: поле title у cat708 обновлено.\n")
S = A['set']
L.append(f"## §4 Аннотации П3а — {len(S)} записей {json.dumps(ra['set_by_class'], ensure_ascii=False)}\n")
L.append('Классы: gap-pre — утерянная строка перед началом аннотации (логлайн «О …», примечание «Сценарий…», формула источника «По мотивам…/Экранизация…») → префикс; gap-post — примечание после прозы, принятое парсером за голову статьи (прописная аббревиатура «В РСФСР/УССР…») и следующая за ним формула → суффикс; gap-mid — строка между покрытыми строками → вставка на печатное место; gap-head — обрыв начала аннотации внутри печатной строки; gap-tailrepl — последняя строка была взята частично; gap-almanac — альманах/киножурнал с утерянной прозой новелл/сюжетов → канон k4 «Название. Проза.» (титры сюжетов не входят; для двух «Фитилей» — полная пересборка, снятые титры сюжетов — в столбце операций). Полный `before`/`after` — `scripts/_f6_p3a_sanction.json`.\n')
L.append('| cat (v1) | id | том | класс | @строки | добавлено / изменено (verbatim после чистки) | операции, ручные чтения (M) | обоснование |')
L.append('|---|---|---|---|---|---|---|---|')
for x in S:
    ops = [o for o in x['ops'] if o[0] in ('M', 'DOT', 'B', 'C^', 'C*', 'DROP', 'REBUILD', 'PREFIX') and not (o[0] == 'PREFIX' and x['class'] != 'gap-almanac')]
    opstr = '; '.join((f"{o[0]} «{esc(o[1])}»→«{esc(o[2])}»" + (f" ({esc(o[3])})" if len(o) > 3 and o[3] else '')) if o[0] in ('M', 'B') else f"{o[0]} «{esc(str(o[1]))[:60]}»" for o in ops) or '—'
    ad = esc(added(x)); ad = ad if len(ad) <= 700 else ad[:700] + '…'
    cv1 = f"{x['cat']} ({x['cat_v1']})" if x['cat'] != x['cat_v1'] else str(x['cat'])
    L.append(f"| {cv1} | {x['id']} | {x['vol']} | {x['class']} | {', '.join('@' + str(k) for k in x['lines'])} | {ad} | {opstr} | {esc(x['note'])} |")
L.append('')
L.append('## §5 Аннотации П3б — 4 записи (gap-pre 2, cred-cut 2)\n')
L.append('| cat | id | том | класс | @строки | добавлено / снято | обоснование |')
L.append('|---|---|---|---|---|---|---|')
for x in B['set']:
    L.append(f"| {x['cat']} | {x['id']} | {x['vol']} | {x['class']} | {', '.join('@' + str(k) for k in x['lines'])} | {esc(added(x))[:600]} | {esc(x['note'])} |")
L.append('')
L.append('## §6 Итоги регрессионной сверки (после П3а/П3б)\n')
lc = Counter((x['loc'], x['kind']) for x in lost)
L.append(f"- Старый каталог 6857 → v2: сопоставлены 6857/6857 (автоматически {cmp['matched']}, вручную 6), кратных привязок 0. Записей v2 без пары в старом — {len(cmp['unmatched_new'])} (по томам {dict(Counter(u['source'].split('_')[0] for u in cmp['unmatched_new']))}; список — `work/f6_ref_compare_v2.json`).")
L.append(f"- Классы аннотаций пар: {json.dumps(cmp['ann_classes'], ensure_ascii=False)}.")
L.append(f"- Предложения старого, отсутствующие в новом ({len(lost)} в {len({x['id'] for x in lost})} записях): контаминация соседними статьями {lc[('elsewhere', None)]}; внутри статьи: библиография {lc[('in_article', 'bib')]}, титры {lc[('in_article', 'cred')]}, призы {lc[('in_article', 'prize')]}, головы {lc[('in_article', 'head')]}, проза соседней записи {lc[('in_article', 'neighbour')]}, проза {lc[('in_article', 'prose')]} (поштучно: OCR-склейки старого, титульные строки сюжетов, контаминация — потерь нет); не найдены в печати {lc[('not_found', None)]}.")
L.append('- Повторный печатный скан пропусков по v2: кандидатов класса «утерянная проза/примечание» не осталось (остаток списка `work/f6_ref_gap_sel_v2.json` — титры-продолжения, призы, библиография v4, контаминация при неопознанных головах, OCR-варианты уже восстановленного).\n')
L.append('## §7 Наблюдения и бэклог (для владельца)\n')
L.append(f"1. **Титроподобные предложения внутри аннотаций** — {len(bl)} предложений в {len({c['cat'] for c in bl})} записях (строка печати класса «титры», поглощённая аннотацией: «В фильме снимались…», «Роли исполняли…», «Съемочная группа благодарит…», «В фильме использована музыка…», «Над фильмом также работали…», списки исполнителей): по канону (титры не входят) — кандидаты на срез, но часть — производственные примечания v1 (конвенция П1 сохраняла примечания). Список `work/f6_p3b_cred_cands.json`; id: {sorted({c['id'] for c in bl})}. Решение — за владельцем (пакет П3в).")
L.append('2. Титроблочные примечания *до* «В ролях» (например id 3456 «Капитан Нуль»: «Фильм снимался на рыболовецком траулере…», id 6577 «Наследство»: «В фильм включены материалы…») в аннотацию не восстанавливались — по расположению это блок титров; в старом каталоге их тоже нет.')
L.append('3. OCR-остатки в восстановленном (как в печати): id 3059 «заведущая», id 3476 «Попраный обет», id 3158 «кочетару Лапше», id 1629 — пропущенные точки внутри прозы; бэклог П2ж (буквенные OCR-ошибки внутри слов).')
L.append('4. Ложные головы: строки вида «В РСФСР/УССР фильм…» в v1 распознаются `work/f6_p2_lib.heads()` как головы (прописная аббревиатура); в П3а границы статей определялись по «настоящим» головам (`true_head` в `work/f6_ref_gap_scan.py`). Для будущих проходов по печати использовать этот критерий.')
L.append('5. `work/f6_p2_ann_loc.json` / `work/f6_p2_articles.json` индексированы по нумерации v1: для v2 индексы ≥ 1628 сдвигать на −1 (см. `work/f6_p3a_tail_scan.py`, `work/f6_ref_gap_scan_v2.py`).')
L.append('6. 62 записи «Фитиль» со студиями сюжетов после заголовков (бэклог П3 §6 п.1): П3а пересобрал 2 (id 4016, 6810); остальные — без изменений.\n')
L.append('## §8 Проверки\n')
L.append('- `python3 scripts/f6_apply_p3a.py --dry` / apply: И1′–И6 пройдены; `python3 scripts/f6_apply_p3b.py`: И2/И3/И5′ пройдены.')
L.append('- `python3 scripts/f6_final_check.py`: OK (7174; схема; по томам; alignment/мастер == П3 + сдвиг + новая строка + row 1088; реестр 110; дубли 3/0; санкции П3а+П3б воспроизводимы; прочих полей сверено байт-в-байт 42977; маркеры 0; латиница 2; переносы 1; переводы строк 4; титул ↔ мастер 1 (намеренно); без конечного знака 118).')
L.append('- Повторные проходы по v2: `work/f6_p3a_tail_scan.py` (END-OK 6970, END-NOPUNCT 115, CONT-UPPER 46 — все призовые строки, срезанные П3, NOMATCH 9 — прежние), `work/f6_ref_gap_scan_v2.py` + `work/f6_ref_gap_select.py` (287 остатков — не потери), `work/f6_ref_lost3.py` (in_article/prose 24 — не потери).')
open('veto/ВЕТО_Ф6_П3а.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('written', len('\n'.join(L)))
