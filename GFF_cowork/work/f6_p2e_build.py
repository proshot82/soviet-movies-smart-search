# -*- coding: utf-8 -*-
"""Ф6-П2е: резолюция буквенных OCR-правок из списка кандидатов (только auto=да минус ручные исключения + 2 ручных варианта).
Вход: work/f6_p2d_cand.json, state/catalog_f6_p2d.json. Выход: scripts/f6_p2e_resolution.json."""
import json, re, sys, collections
sys.path.insert(0, 'work')
import f6_p2_lib as L
cat = json.load(open('state/catalog_f6_p2d.json', encoding='utf-8'))
rows = json.load(open('work/f6_p2d_cand.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p2_ann_scan.json', encoding='utf-8'))}
# исключения из auto после ручного просмотра: (cat, слово) → причина
EXCLUDE = {
 (890, 'тутпат'): 'вероятно «тушат костры» — не «тут пат»; чтение неоднозначно → вручную',
 (1842, 'хирур'): 'контекст «новатора-хирур! а.» — правится целиком отдельной ручной заменой (см. MANUAL)',
 (1960, 'стройучастка'): 'законное сложносокращённое слово (стройучасток)',
 (1963, 'маршаллизировать'): 'законное слово (план Маршалла)',
 (2216, 'еиерь'): 'контекст «Только 1еиерь» = «Только теперь», не «егерь» (см. MANUAL)',
 (2556, 'невольничьем'): 'законное слово (невольничий рынок)',
 (2739, 'ухажор'): 'просторечный вариант написания, не OCR',
 (3113, 'долгосмотрела'): 'разрыв должен быть «долго смотрела», не «долг осмотрела» → вручную',
 (3137, 'считалочка'): 'законное слово',
 (3519, 'апплодируют'): 'орфографический вариант печати, не OCR → вручную',
 (3519, 'безхозяйственность'): 'орфографический вариант печати, не OCR → вручную',
 (3585, 'хронометристки'): 'законное слово (хронометристка)',
 (4306, 'скульптурку'): 'законное слово (уменьшительное)',
 (5745, 'опергруппу'): 'законное сложносокращённое слово', (6718, 'опергруппе'): 'законное сложносокращённое слово',
 (5892, 'разведуправление'): 'законное сложносокращённое слово',
 (6161, 'претемной'): 'законное слово (темной-претемной)',
 (6733, 'прилипалочку'): 'законное слово (палочка-прилипалочка)',
 (6796, 'топталочке'): 'законное просторечное слово (в кавычках)', (6796, 'топталочку'): 'законное просторечное слово (в кавычках)',
}
MANUAL = {1842: [('новатора-хирур! а.', 'новатора-хирурга.', 'мусор «! а» внутри слова; чтение однозначно')],
          2216: [('Только 1еиерь,', 'Только теперь,', '«1еиерь» = «теперь» (цифра и латиница вместо букв)')]}
def evid(c, text):
    v = cat[c]['source'].split('_')[0]; ls = L.lines(v); x = scan.get(c); n = L.norm_m(text)[:28]
    if not n: return None
    lo = x['h'] if x else 0; hi = (x['e'] + 3) if x else len(ls) - 1
    for j in range(lo, min(hi, len(ls) - 1) + 1):
        if n in L.norm_m(ls[j][1]): return j
    hits = [j for j in range(len(ls)) if n in L.norm_m(ls[j][1])]
    return hits[0] if len(hits) == 1 else None
by = collections.defaultdict(list); excluded = []
for r in rows:
    if r['auto'] != 'да': continue
    key = (r['cat'], r['word'])
    if key in EXCLUDE: excluded.append({'cat': r['cat'], 'word': r['word'], 'candidate': r['candidate'], 'reason': EXCLUDE[key]}); continue
    by[r['cat']].append(r)
assert len(excluded) == len(EXCLUDE), (len(excluded), len(EXCLUDE))
out = []
for c in sorted(set(by) | set(MANUAL)):
    a0 = cat[c]['annotation']; a = a0; ops = []
    for r in by.get(c, []):
        w, new = r['word'], r['candidate']
        if r['kind'] == 'склейка':
            pat = re.compile(r'(?<![А-ЯЁа-яё-])' + re.escape(w) + r'(?![А-ЯЁа-яё-])')
        else:
            pat = re.compile(r'(?<![А-ЯЁа-яё])' + re.escape(w) + r'(?![А-ЯЁа-яё])')
        hits = pat.findall(a)
        assert len(hits) == 1, f'cat{c}: «{w}» ×{len(hits)}'
        a = pat.sub(new, a); ops.append(['O', w, new, r['edit'], f'встреч. кандидата в корпусе {r["freq_candidate"]}'])
    for old, new, why in MANUAL.get(c, []):
        assert a.count(old) == 1, f'cat{c}: MANUAL «{old}» ×{a.count(old)}'
        a = a.replace(old, new); ops.append(['M', old, new, 'вручную', why])
    assert a != a0 and a == a.strip() and '  ' not in a
    lines = []
    for o in ops:
        j = evid(c, o[1]); lines += [j] if j is not None else []
    if not lines:
        j = evid(c, a0[:60]); lines += [j] if j is not None else []
    out.append({'cat': c, 'title': cat[c]['title'], 'source': cat[c]['source'], 'field': 'annotation', 'class': 'ocr-letters',
                'vol': cat[c]['source'].split('_')[0], 'lines': sorted(set(lines)),
                'note': '; '.join(f'{o[1]} → {o[2]} ({o[3]})' for o in ops), 'ops': ops, 'before': a0, 'after': a})
res = {'_meta': {'package': 'Ф6-П2е буквенные OCR-ошибки внутри слов аннотаций (auto-строки списка кандидатов)', 'generated': '2026-09-02',
                 'input_catalog': 'state/catalog_f6_p2d.json (7173)', 'expected_after': {'catalog': 7173, 'master_rows': 7203, 'master_card': 7173, 'strays': 0},
                 'rule': 'применены строки veto/П2д_кандидаты_OCR_буквы.xlsx с auto=да (ровно один словарный кандидат на расстоянии одной правки/разрыва; '
                         'искажённая форма встречается в корпусе 1 раз; правка — OCR-пара с кандидатом ≥1 в корпусе, или кандидат ≥3 в корпусе, или разрыв '
                         'склеенных слов с предлогом/глаголом/местоимением) минус ручные исключения после просмотра всех auto-строк; + 2 ручных варианта; '
                         'ручные строки (auto=нет) НЕ применялись; правило подтверждено владельцем 02.09.2026 («меня все устраивает»)',
                 'counts': {'auto_rows': sum(1 for r in rows if r['auto'] == 'да'), 'applied_auto': sum(1 for e in out for o in e['ops'] if o[0] == 'O'),
                            'excluded': len(excluded), 'manual': sum(1 for e in out for o in e['ops'] if o[0] == 'M'), 'records': len(out)}},
       'set': out, 'excluded': excluded, 'register': {'add': []}}
json.dump(res, open('scripts/f6_p2e_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(res['_meta']['counts'], 'без печатной привязки:', sum(1 for e in out if not e['lines']))
