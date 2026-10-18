# -*- coding: utf-8 -*-
"""Генерация veto/ВЕТО_Ф6_П1.md из scripts/_f6_p1_sanction.json (полные таблицы)."""
import json, hashlib
from collections import Counter
prot = json.load(open('scripts/_f6_p1_sanction.json', encoding='utf-8'))
cat = json.load(open('state/catalog_f6_p1.json', encoding='utf-8'))
cat0 = json.load(open('backups/catalog_f5.json', encoding='utf-8'))
m = json.load(open('state/index_master_f6_p1.json', encoding='utf-8'))
sha = hashlib.sha256(open('state/catalog_f6_p1.json', 'rb').read()).hexdigest()
def esc(s): return str(s).replace('|', '\\|').replace('\n', ' ') if s is not None else '—'
def cell(s, n=None):
    s = esc(s); return s if n is None or len(s) <= n else s[:n] + '…'
new_of = {int(k): v for k, v in prot['renumbering'].items()}
deleted = {x['cat'] for x in prot['delete']}
def nm(c): return None if c in deleted else new_of.get(c, c)
L = []
L.append('# ВЕТО Ф6-П1 — страи: RESTORE/APPEND у связанных записей, KEEP cat1197, удаление 59')
L.append('')
L.append(f"Сессия 02.09.2026 (Cowork), карт-бланш; протокол применённого. Резолюция — `scripts/f6_p1_resolution.json`, "
         f"apply — `scripts/f6_apply_p1.py` (пред-ассерты + И1′–И6), санкция — `scripts/_f6_p1_sanction.json`, "
         f"приёмка — `scripts/f6_p1_check.py`. Источник вердиктов — `state/Ф6_страи_диспозиция.json` "
         f"(протокол `veto/ВЕТО_Ф5_финал_страи.md`); тексты — verbatim по извлечениям томов `work/vN_lines.json`, "
         f"повторно сверены механически (каждый печатный сегмент @строк присутствует в after; остаток — только заголовки новелл по правилу k4).")
L.append('')
L.append('## 0. Контрольные цифры')
L.append('')
L.append('- Вход: `state/catalog_f5.json` — 7232 (sha256 `80f3b78f56959735…`), страёв 60 (`alignment_v17.json`), мастер `index_master_v18r.json` — rows 7203 (card 7172, crossref 22, unbound 9). Все цифры §0 хендоффа сошлись.')
r = prot['_meta']['result']
L.append(f"- Выход: `state/catalog_f6_p1.json` — **{r['catalog']}** (sha256 `{sha[:16]}…`); `state/alignment_f6_p1.json` — {r['alignment']} (страёв 0, `cat_pos` перенумерован, `cat_pos_f5` — прежний индекс); "
         f"`state/index_master_f6_p1.json` — rows {r['master_rows']} (card **{r['master_card']}**, crossref 22, unbound 8), `strays` пуст. Биекция каталог ↔ alignment ↔ card-строки — И6.")
L.append('- Предыдущие файлы → `backups/` (`catalog_f5.json`, `alignment_v17.json`, `index_master_v18r.json` + копии с меткой времени; реестр и очередь — копии с меткой времени). В `state/` ровно один каталог/alignment/мастер.')
L.append('- Правки: set 16 (annotation restore 12, append 3, studio 1 — все у 15 записей), delete 59; титулов не менялось; D1 (cat3405 → cat3388) — по умолчанию, v3 без изменений.')
L.append('- Реестр стабов `Ф5_стабы_реестр.json` (114) и очередь `Ф5_очередь_docx.json` перенумерованы (`cat` — Ф6, `cat_f5` — Ф5); очередь: `year_empty` 32 и `annotation` 489/1185 закрыты удалением страёв, остались терминалы genre 12, studio_empty 1 (cat3050 ← 3064), annotation 2 (cat3858/3859 ← 3876/3877).')
L.append('- Приёмка: пустые поля каталога == реестр (genre 12, studio 1, annotation 7, year 0; позиции совпадают); точные дубли title+year — 4 пары (3 законные + «Пес и Кот» 1938 cat1514/2243 — закрывается Ф6-П2); годы вне диапазона тома ±1 — 10 печатных (норма); маркеров титров в 15 правленных аннотациях — 0.')
L.append('')
L.append('## 1. Перенумерация')
L.append('')
L.append('Удалены 59 позиций Ф5; `cat_new = cat_old − |{удалённые с индексом < cat_old}|`. Полная карта — `alignment_f6_p1.json` (`cat_pos_f5 → cat_pos`) и `scripts/_f6_p1_sanction.json → renumbering`. '
         'Сдвиг по диапазонам Ф5: cat1–120 → −1; 122–169 → −2; 172–372 → −4; 374 → −5; 376–388 → −6; 390–412 → −7; 414–464 → −8; 466–470 → −9; 472–488 → −10; 490–1181 → −11; 1184 → −13; 1186–1197 → −14; '
         '1199–3146 → −14; 3150–3440 → −17; 3442–4793 → −18; 4797–4913 → −21; 4917–5244 → −24; 5246–5380 → −25; 5384–5571 → −28; 5573–5595 → −29; 5597–5601 → −30; 5603–5619 → −31; 5621–5762 → −32; '
         '5768–5802 → −37; 5804–5853 → −38; 5856–5862 → −40; 5864–5890 → −41; 5892–5938 → −42; 5942 → −45; 5946 → −48; 5949–6035 → −50; 6037–6239 → −51; 6241–6248 → −52; 6250–6270 → −53; 6272–6275 → −54; '
         '6277–6967 → −55; 6969–7197 → −56; 7201–7231 → −59. Ссылки хендоффа Ф6 §2 (П2) переведены в нумерацию Ф6 с прежним номером в скобках.')
L.append('')
L.append('## 2. Правки полей (set 16) — verbatim → канон')
L.append('')
L.append('| cat Ф6 (Ф5) | запись | том @строки | поле | класс | из страёв | before | after |')
L.append('|---|---|---|---|---|---|---|---|')
for x in prot['set']:
    b, a = x['before'], x['after']
    if x['class'] == 'append':
        a_show = f"= before + «{a[len(b):].strip()}»"
        b_show = cell(b, 160)
    else:
        a_show, b_show = a, b
    L.append(f"| {x['cat_new']} ({x['cat']}) | {cell(x['title'])} ({cell(x['source'])}) | {x['vol'].split('_')[0]} @{','.join(map(str, x['lines']))} | {x['field']} | {x['class']} | "
             f"{', '.join(map(str, x['from_strays'])) or '—'} | {esc(b_show)} | {esc(a_show)} |")
L.append('')
L.append('Примечания: заголовки новелл в слияниях k4 взяты из печатных голов новелл (например v3 @5429 «П и л и п к о» — печатная разрядка снята, @5433, @5437); '
         'титры новелл, ремарки «Фильм снят при участии…», призы/дипломы, библиография не включены (по диспозиции). '
         'cat1183 (Ф5 1197) «Рядом с нами» 1931: studio — снят хвост «, 1931 г» (печатно v2 @124), annotation — verbatim @127–128 без OCR-маркера «•» и библиографии @129; genre «Драма», year 1931 — печатно, без изменений.')
L.append('')
L.append('## 3. Удалённые страи (59) — полные записи в `scripts/_f6_p1_sanction.json → delete[].record`')
L.append('')
L.append('| cat Ф5 | том | титул (Ф5) | год | класс | вердикт | связанная запись Ф6 (Ф5, № мастера) | примечание |')
L.append('|---|---|---|---|---|---|---|---|')
for x in prot['delete']:
    tgt = '—' if x['target'] is None else f"cat{x['target_new']} ({x['target']}, №{x['target_num']}) {cell(x['target_title'], 40)}"
    L.append(f"| {x['cat']} | {x['source'].split('_')[0]} | {cell(x['title'], 60)} | {esc(x['year'])} | {x['stray_class']} | {x['verdict']} | {tgt} | {cell(x['note'], 220)} |")
L.append('')
byc = Counter(x['stray_class'] for x in prot['delete'])
L.append(f"Итого по классам: {', '.join(f'{k} {v}' for k, v in sorted(byc.items()))}. Покрытие прозы страёв связанными записями проверено в финале Ф5 (класс B — 1.0; C/D — RESTORE/слияние выше).")
L.append('')
L.append('## 4. Alignment и мастер-индекс')
L.append('')
r2106 = prot['master']['row_2106']; a1197 = prot['master']['alignment_1197']
L.append(f"- 59 позиций страёв выбыли из alignment; card-строки мастера перенумерованы (`cat_pos_f5 → cat_pos`); прочие поля строк/позиций байт-в-байт (И3).")
L.append(f"- cat1183 (Ф5 1197) «Рядом с нами»: строка мастера **xlsx row 2106** (была unbound: склейка «{r2106['xlsx_title']}», xlsx_num «1184а») → `kind=card`, `num=\"1184а\"`, `title_canon=\"Рядом с нами\"`, "
         f"`cat_pos={r2106['cat_pos']}`; «Рядовой Александр Матросов» №1888 остаётся на синтетической row 7182 → cat1887 (Ф5 1901). Сырое поле `xlsx_title` сохранено, разделение зафиксировано в `note`/`provenance`. "
         f"alignment: xlsx_row 2106, idx_num «1184а», method manual, confidence high, master_title «Рядом с нами».")
L.append(f"- `_meta.stats`: карточных 7173, некарточных 30 (crossref 22, unbound 8), страёв 0, литерные номера + «1184а», «по томам» v2 1335 → 1336; `strays` = [].")
L.append('')
L.append('## 5. Наблюдения и передача в П2/П3')
L.append('')
L.append('1. Точные дубли title+year после П1 — 4 пары: «Красная звезда» 1919 (cat27/28), «Интернационал» 1932 (cat1206/1218), «Клиника» 1987 (cat7063/7064) — законные (разные студии); «Пес и Кот» 1938 (cat1514/2243) — закрывается П2-а (cat2243 → 1955, Союзмультфильм, «Графич.»). §4 п.5 хендоффа уточнён: 3 пары — после П2.')
L.append('2. Инвентарь после П1 (непустые значения, все 7173 записи): уникальных genre 139, studio 506. В Ф5 среди не-страёв было 139/506 — цифры «140/507» §4 п.3 хендоффа не воспроизводятся (507 = не-страи + cat1197 с неочищенной студией «Союзкино (М.), 1931 г»; основа 140 не установлена) — §4 п.3 исправлен. Из инвентаря ушли только значения страёв (genre 5: «(», «Цв», «Союзкинохроника», «Метраж фильма сократился до», «Фильм был перемонтирован (»; studio 36 — обрывки голов/титров/метража, «Союзкино (М.), 1931 г»); новых значений нет.')
L.append('3. Аннотации короче 100 знаков у не-None — 208 (в реестре аннотаций 73; вне реестра 135 — однофразные формулы, П3-приёмка выборочно).')
L.append('4. Служебные ключи Ф4: `_merged` 6775, `_f4_recovered` 398 — снять в П3.')
L.append('5. D1 не решался владельцем — исполнен вариант по умолчанию (v3); текст v4 остаётся в диспозиции (`actions.decisions`).')
L.append('6. Свободный текст `note`/`reason`/`second_signal` в alignment, мастере, реестре и очереди содержит номера cat эпох Ф4/Ф5 — не перенумеровывался (провенанс).')
open('veto/ВЕТО_Ф6_П1.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('veto written', len('\n'.join(L)), 'chars')
