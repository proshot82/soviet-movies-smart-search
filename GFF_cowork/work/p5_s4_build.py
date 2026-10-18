# -*- coding: utf-8 -*-
import json, importlib.util, collections
spec = importlib.util.spec_from_file_location('m', 'work/p5_s4_map.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
MAP = dict(m.MAP)
del MAP['Туркмепкино']  # канона в каталоге нет — в s5 по печати
cat = json.load(open('state/catalog_f5_s3.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
canon = collections.Counter(r.get('studio') for r in cat if r.get('studio'))
NOTE = {'junk': 'срез глиф/метраж-кляксы (класс П2 «клякса-лид/срез:метраж»)',
        'tail': 'срез хвостового мусора (класс П2 tail)',
        'ocr': 'OCR-опечатка'}
res = {'set': {}, 'confirm': {}, 'notfound': {}}
skipped, unmatched = [], set(MAP)
for i, r in enumerate(cat):
    s = r.get('studio')
    if s in MAP:
        unmatched.discard(s)
        if i in strays:
            skipped.append((i, s)); continue
        after, cls = MAP[s]
        n = canon.get(after, 0)
        note = NOTE[cls] + (f'; канон каталога «{after}» — {n} зап.' if cls == 'ocr' and n else
                            (f'; целевая форма в каталоге — {n} зап.' if n else '; целевая форма — очистка значения'))
        res['set'][str(i)] = {'before': s, 'after': after, 'vol': r['source'].split('_')[0],
                              'line': None, 'class': cls, 'note': note}
json.dump(res, open('scripts/s4_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('s4 set:', len(res['set']), 'записей;', len(set(v["before"] for v in res["set"].values())), 'уникальных значений')
by_cls = collections.Counter(v['class'] for v in res['set'].values())
print('по классам:', dict(by_cls))
if skipped: print('ПРОПУЩЕНЫ СТРАИ:', skipped)
if unmatched: print('значения без записей (уже ушли/опечатка словаря):', sorted(unmatched))
