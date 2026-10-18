# -*- coding: utf-8 -*-
"""Реконструкция мастер-индекса (утрачен вместе с чатом ф17) как проекции двух живых
источников: alignment_v17.json (все 7172 карточные строки мастера: xlsx_row, idx_num,
master_title, привязка к каталогу) + эталонный xlsx-указатель проекта (сырой титул, год/
интервал тома, примечание с альт-названиями; 31 некарточная строка).
Выход: index_master_v18r.json (r = reconstructed) + отчёт реконструкции.
Анти-фабрикация: ни одно значение не придумано — каждое поле несёт provenance."""
import json, re, openpyxl
from collections import Counter, defaultdict

AL  = '/mnt/user-data/uploads/alignment_v17.json'
CAT = '/mnt/user-data/outputs/catalog_f5_g5.json'
XL  = '/mnt/project/Госфильмофонд_именной_указатель_19181987.xlsx'
OUT = '/home/claude/GFF_cowork/state/index_master_v18r.json'
REP = '/home/claude/GFF_cowork/state/index_master_v18r_реконструкция.md'

al  = json.load(open(AL, encoding='utf-8'))
cat = json.load(open(CAT, encoding='utf-8'))
rows = list(openpyxl.load_workbook(XL, read_only=True, data_only=True)['Фильмы'].iter_rows(values_only=True))[1:]
xl = {int(r[0]): {'title': r[1], 'year': r[2], 'num': r[3], 'note': r[4]} for r in rows}
assert len(al) == len(cat) == 7232 and len(xl) == 7195

OLD = {'v1_1918-1935','v2_1936-1957','v3_1958-1963','v4_1964-1965'}
INTERVAL2VOL = {'1918–1935':'v1_1918-1935','1930–1957':'v2_1936-1957','1936–1957':'v2_1936-1957',
                '1958–1963':'v3_1958-1963','1964–1965':'v4_1964-1965'}
def vol_from_year(y):
    s = str(y or '').replace('-', '–')
    if s in INTERVAL2VOL: return INTERVAL2VOL[s]
    m = re.fullmatch(r'(19\d\d)', s)
    if not m: return None
    y = int(m.group(1))
    for a, v in ((1966,'v5_1966-1967'),(1968,'v6_1968-1969'),(1970,'v7_1970-1971'),(1972,'v8_1972-1973'),
                 (1974,'v9_1974-1975'),(1976,'v10_1976-1977'),(1978,'v11_1978-1979'),(1980,'v12_1980-1981'),
                 (1982,'v13_1982-1983'),(1984,'v14_1984-1985'),(1986,'v15_1986-1987')):
        if a <= y <= a+1: return v
    return None

def parse_note(note):
    """«Др. названия: A; B» → список альт-названий; прочее — как есть."""
    if not note: return [], None
    m = re.match(r'\s*Др\.?\s*названи[яе]\s*:\s*(.+)$', str(note), re.I)
    if m:
        alts = [t.strip(' «»"') for t in re.split(r'\s*;\s*', m.group(1)) if t.strip()]
        return alts, None
    return [], str(note)

master, fills, kinds = [], Counter(), Counter()
bound_rows = set()
for a in al:
    if a['xlsx_row'] is None:
        continue
    r = a['xlsx_row']; bound_rows.add(r)
    c = cat[a['cat_pos']]
    x = xl.get(r)
    title, tsrc = a['master_title'], 'alignment.master_title'
    if not title:
        title, tsrc = c['title'], 'catalog.title (канонизирован в Ф3 по мастеру; master_title в alignment пуст)'
        fills['title←catalog'] += 1
    alts, note_free = parse_note(x['note']) if x else ([], None)
    row = {
        'xlsx_row': r,
        'num': a['idx_num'],
        'title_canon': title,
        'title_source': tsrc,
        'vol': c['source'],
        'kind': 'card',
        'cat_pos': a['cat_pos'],
        'xlsx_title': x['title'] if x else None,
        'xlsx_num': x['num'] if x else None,
        'xlsx_year': x['year'] if x else None,
        'alt_titles': alts,
        'note': note_free,
        'provenance': 'xlsx+alignment' if x else f"synthetic: {a.get('note') or a.get('f4_group') or 'строка добавлена в Ф2–Ф4'}",
    }
    if x and a['idx_num'] is not None and re.sub(r'\D','',str(x['num'] or '')) != re.sub(r'\D','',str(a['idx_num'])):
        row['num_corrected_from_xlsx'] = x['num']; fills['num исправлен относительно xlsx'] += 1
    master.append(row); kinds['card'] += 1

# некарточные строки xlsx (перекрёстные ссылки, склейки, дубли альт-названий)
for r, x in xl.items():
    if r in bound_rows: continue
    alts, note_free = parse_note(x['note'])
    is_ref = bool(x['note'] and re.search(r'см\.|перекр', str(x['note']), re.I))
    master.append({
        'xlsx_row': r, 'num': None, 'title_canon': None, 'title_source': None,
        'vol': vol_from_year(x['year']), 'kind': 'crossref' if is_ref else 'unbound',
        'cat_pos': None, 'xlsx_title': x['title'], 'xlsx_num': x['num'], 'xlsx_year': x['year'],
        'alt_titles': alts, 'note': note_free,
        'provenance': 'xlsx; строка не привязана ни к одной записи каталога (перекрёстная ссылка / склейка OCR / дубль альт-названия — снята в Ф1–Ф3)',
    })
    kinds['crossref' if is_ref else 'unbound'] += 1

master.sort(key=lambda m: m['xlsx_row'])
strays = [{'cat_pos': a['cat_pos'], 'cat_title': a['cat_title'], 'vol': a['source'],
           'method': a['method'], 'f4_group': a.get('f4_group'), 'note': a.get('note')}
          for a in al if a['xlsx_row'] is None]

# ── проверки ──
cards = [m for m in master if m['kind'] == 'card']
assert len(cards) == 7172 and len({m['xlsx_row'] for m in master}) == len(master) == 7172 + 31
assert len({m['cat_pos'] for m in cards}) == 7172 and len(strays) == 60
def numint(n):
    m = re.match(r'(\d+)', str(n)); return int(m.group(1)) if m else None
old = sorted(numint(m['num']) for m in cards if m['vol'] in OLD and numint(m['num']) is not None)
new = sorted(numint(m['num']) for m in cards if m['vol'] not in OLD and numint(m['num']) is not None)
lit = sorted(str(m['num']) for m in cards if isinstance(m['num'], str) and not str(m['num']).isdigit())
def coverage(seq, hi):
    s = set(seq); gaps = [n for n in range(1, hi+1) if n not in s]
    dup = [n for n, k in Counter(seq).items() if k > 1]
    return gaps, dup
og, od = coverage(old, 3759); ng, nd = coverage(new, 3428)
stats = {
 'карточных строк': len(cards), 'некарточных строк xlsx': 31, 'страёв каталога': len(strays),
 'старая серия: номеров': len(old), 'старая серия: дыр в 1..3759': len(og), 'старая серия: дубли': od,
 'новая серия: номеров': len(new), 'новая серия: дыр в 1..3428': len(ng), 'новая серия: дубли': nd,
 'литерные номера': lit, 'заполнения': dict(fills), 'по томам': dict(sorted(Counter(m['vol'] for m in cards).items())),
}
json.dump({'_meta': {'name': 'index_master_v18r', 'reconstructed_on': '2026-08-31',
                     'basis': 'alignment_v17.json (карточные строки) + Госфильмофонд_именной_указатель_19181987.xlsx (сырые поля, некарточные строки)',
                     'replaces': 'index_master_v18.json (утрачен с чатом ф17)', 'stats': stats},
           'rows': master, 'strays': strays},
          open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(stats, ensure_ascii=False, indent=1))
print('дыры старой серии:', og[:40]); print('дыры новой серии:', ng[:40])

# ── отчёт ──
unb = [m for m in master if m['kind'] != 'card']
lines = [f"# Реконструкция мастер-индекса — index_master_v18r.json (31.08.2026)\n",
 "Оригинал `index_master_v18.json` утрачен вместе с чатом ф17. Файл пересобран как проекция двух живых",
 "источников, без единого придуманного значения; каждая строка несёт `provenance`, каждый титул — `title_source`.\n",
 "## Источники и правила\n",
 "- **Карточные строки (7172)** — из `alignment_v17.json`: `xlsx_row` (= колонка «№» эталона), `num` (= `idx_num`,",
 "  исправленный номер мастера), `title_canon` (= `master_title`), `vol` (= `source` записи каталога), `cat_pos`.",
 f"- У {fills.get('title←catalog',0)} строк `master_title` в alignment пуст — взят титул каталога (канонизирован в Ф3 по мастеру), `title_source` это фиксирует.",
 f"- У {fills.get('num исправлен относительно xlsx',0)} строк номер мастера отличается от сырого номера xlsx (правки Ф1–Ф4) — сырой сохранён в `num_corrected_from_xlsx`.",
 "- Сырые поля xlsx (`xlsx_title`, `xlsx_num`, `xlsx_year`, альт-названия из «Примечания») приложены к каждой строке ≤ 7195.",
 "- **Синтетические строки (8, xlsx_row > 7195)** — добавлены в Ф2–Ф4 (закрытие дыр мастера, вставка «Зоя», литеры 1981а/2031а); xlsx-полей у них нет.",
 f"- **Некарточные строки xlsx (31)** — не привязаны ни к одной записи: {kinds['crossref']} перекрёстных ссылок («см. …») и {kinds['unbound']} склеек/дублей, снятых в Ф1–Ф3; включены с `kind` для полноты эталона.",
 "- **Страи (60)** — записи каталога без строки мастера — отдельным списком `strays` (cat_pos, титул, том, метод, Ф4-группа).\n",
 "## Что НЕ восстановлено\n",
 "- Поля оригинального мастера, которых нет ни в alignment, ни в xlsx: флаги Ф1–Ф4 (`flags`), примечания к правкам, история слияний строк. На биекцию не влияют.\n",
 "## Проверки\n",
 f"- Карточных строк 7172, все `xlsx_row` уникальны, все `cat_pos` уникальны; страёв 60; 7172 + 60 = 7232 = каталог.",
 f"- Старая серия (v1–v4): номеров {len(old)}, дыр в 1..3759 — {len(og)} {og[:12]}{'…' if len(og)>12 else ''}, дублей {od}.",
 f"- Новая серия (v5–v15): номеров {len(new)}, дыр в 1..3428 — {len(ng)} {ng[:12]}{'…' if len(ng)>12 else ''}, дублей {nd}.",
 f"- Литерные номера ({len(lit)}): {', '.join(lit)}.\n",
 "## Некарточные строки xlsx (31)\n", "| xlsx_row | №xlsx | титул | год/том | вид | примечание |", "|---|---|---|---|---|---|"]
for m in unb:
    lines.append(f"| {m['xlsx_row']} | {m['xlsx_num'] or ''} | {m['xlsx_title']} | {m['xlsx_year']} | {m['kind']} | {(m['note'] or '').replace('|','/')} |")
open(REP, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('→', OUT, '|', REP)
