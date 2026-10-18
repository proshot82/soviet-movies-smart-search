# -*- coding: utf-8 -*-
"""Ф6-П2д: сборка резолюции scripts/f6_p2d_resolution.json из черновика правил (work/f6_p2d_draft.json)."""
import sys, json, re, collections
sys.path.insert(0, 'work')
import f6_p2_lib as L
cat = json.load(open('state/catalog_f6_p2.json', encoding='utf-8'))
draft = json.load(open('work/f6_p2d_draft.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p2_ann_scan.json', encoding='utf-8'))}
CLASSES = {'B': 'внутристрочный перенос', 'A': 'номер страницы/колонтитул внутри переноса', 'P': 'номер страницы внутри прозы (граница страниц, без переноса)',
           'T': 'хвост — голова следующей статьи / колонтитул / оглавление тома', 'BIB': 'хвост — библиография (OCR-разрыв слова)',
           'L': 'контаминация начала (проза соседней статьи)', 'J': 'мусор после конечной пунктуации', 'R': 'реконструкция «1-я серия» (цифра потеряна сканом; далее есть «2-я серия»)',
           'C*': 'мусорный символ *', 'C^': 'мусорный символ ^', 'C’': 'мусорный апостроф ’‘`', "C'": 'мусорный апостроф ASCII (кроме д’Артаньян/О’Рори)',
           'C"': 'кавычки “ ” " — парные → « », непарные — мусор', 'C„': 'символ „ → запятая/убран', 'C.': 'одиночный знак препинания, приклеенный к началу слова',
           'C×': 'одиночные мусорные символы ।_[]{}\\#$£™¡¿', 'C|': 'мусорный символ |', 'C<': 'символ < → «/убран', 'C>': 'символ > → »/убран',
           'C■': 'символ ■ (тире/маркер)', 'C•': 'символ •', 'D': 'латиница/цифра вместо инициала', 'E': 'латиница внутри слова (авто)',
           'M': 'ручная точечная правка (латиница/цифра/символ вместо буквы — однозначное чтение; колонтитулы/сигнатуры/списки ролей с разрыва страницы; восстановление по печати)',
           'WS': 'пробелы/одиночные знаки препинания'}
def vol_of(c): return cat[c]['source'].split('_')[0]
def evid(c, text):
    v = vol_of(c); ls = L.lines(v); x = scan.get(c); n = L.norm_m(text)[:28]
    if not n: return None
    lo = x['h'] if x else 0; hi = (x['e'] + 3) if x else len(ls) - 1
    for j in range(lo, min(hi, len(ls) - 1) + 1):
        if n in L.norm_m(ls[j][1]): return j
    hits = [j for j in range(len(ls)) if n in L.norm_m(ls[j][1])]
    return hits[0] if len(hits) == 1 else None
out = []; ORDER = ['L', 'T', 'BIB', 'J', 'A', 'P', 'R', 'M', 'B', 'D', 'E', 'C"', "C'", 'C’', 'C„', 'C.', 'C×', 'C*', 'C^', 'C|', 'C<', 'C>', 'C■', 'C•', 'WS']
for k, d in sorted(draft.items(), key=lambda kv: int(kv[0])):
    c = int(k); b, a, ops = d['before'], d['after'], d['ops']
    assert b == cat[c]['annotation'] and a != b and a == a.strip() and '  ' not in a
    cnt = collections.Counter(o[0] for o in ops)
    cls = 'ocr:' + '+'.join(x for x in ORDER if x in cnt)
    note = '; '.join(f'{CLASSES[x]} ×{cnt[x]}' for x in ORDER if x in cnt)
    lines = []
    for o in ops:
        if o[0] in ('B', 'A', 'P', 'M', 'R', 'D', 'E', 'C.', 'C*', 'C^', "C'", 'C’') and o[1] and re.search(r'[А-ЯЁа-яё]{3}', o[1]):
            j = evid(c, o[1]); lines += [j] if j is not None else []
    if not lines:
        j = evid(c, b[:60]); lines += [j] if j is not None else []
    out.append({'cat': c, 'title': cat[c]['title'], 'source': cat[c]['source'], 'field': 'annotation', 'class': cls, 'vol': vol_of(c),
                'lines': sorted(set(lines)), 'note': note, 'ops': ops, 'before': b, 'after': a})
res = {'_meta': {'package': 'Ф6-П2д механическая чистка OCR-мусора в аннотациях', 'generated': '2026-09-02',
                 'input_catalog': 'state/catalog_f6_p2.json (7173)', 'expected_after': {'catalog': 7173, 'master_rows': 7203, 'master_card': 7173, 'strays': 0},
                 'rules': 'work/f6_p2d_rules.py (правила) + work/f6_p2d_manual.py (ручные решения: MANUAL_B, MANUAL_REPL, KEEP_HYPH, LEAD_CUTS, TAIL_CUTS, PAGES, SERIES); '
                          'словарь pymorphy3 для склейки переносов; печать (work/vN_lines.json) содержит тот же OCR — правки механические; '
                          'слова с латиницей/цифрами/символами вместо букв восстановлены только при однозначном чтении по контексту (класс M, все перечислены в вето); '
                          'буквенные OCR-ошибки внутри кириллических слов НЕ правились — отдельный список кандидатов',
                 'classes': CLASSES, 'counts': dict(collections.Counter(o[0] for d in draft.values() for o in d['ops'])), 'records': len(out)},
       'set': out,
       'register': {'add': [{'cat': 2958, 'field': 'annotation', 'state': 'source-only',
                             'reason': 'печатно только формула источника «По мотивам повести Н. В. Гоголя «Ночь перед Рождеством».» (v3 @4052); библиография снята П2д'}]}}
json.dump(res, open('scripts/f6_p2d_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('резолюция:', len(out), 'записей; классы:', res['_meta']['counts'])
print('без печатной привязки:', sum(1 for e in out if not e['lines']))
