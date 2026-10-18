import json, re, collections
cat = json.load(open('state/catalog_f5_a5.json', encoding='utf-8'))
print('len', len(cat))
byid = {i: r for i, r in enumerate(cat)}
cands = [48,854,861,890,1072,1186,1224,1236,1347,2106,2116,2356,3064,3284,4035,4037,4259,4459,4463,4474,4486,4490,4504,4546,4634,4635,4636,4659,4699,4732,4734,4738,4797,4841,4850,4927,5038,5215,5244,5456,5542,5555,5606,5645,5652,5673,5693,5716,5718,5753,5894,5980,6102,6269,6446,6474,6478,6540,6546,6636,6876,6886,6946,6966,6967,7166]
print('=== кандидаты: текущее studio ===')
for c in cands:
    r = byid.get(c)
    if r is None: print(c, 'НЕТ ID'); continue
    print(f"{c}\t{r['source']}\t{r['title'][:38]!r}\t{r.get('studio')!r}")
print()
studios = [(i, r.get('studio'), r['source']) for i, r in enumerate(cat)]# for r in cat]
empty = [(i,s,src) for i,s,src in studios if not s]
print('пустых studio:', len(empty))
for i,s,src in empty: print('  ', i, src, byid[i]['title'][:40])
vals = collections.Counter(s for _,s,_ in studios if s)
print('уникальных значений studio:', len(vals))
print()
bad = collections.defaultdict(list)
for i,s,src in studios:
    if not s: continue
    if re.search(r'\d', s): bad['цифры'].append((i,s))
    if re.search(r'[€£$^<>=_@#%*+~\\|{}\[\]]', s): bad['глифы'].append((i,s))
    if s != s.strip() or '  ' in s: bad['пробелы'].append((i,s))
    if re.match(r'^[а-яё]', s): bad['строчная'].append((i,s))
    if re.search(r'(?i)библиограф|\bВЭ\b|\bРУ\b', s): bad['служебное'].append((i,s))
    if len(s) > 75: bad['длинные'].append((i,s))
    if re.match(r'^и\s', s): bad['лид-и'].append((i,s))
    if re.search(r'[«»"“”]', s) and (s.count('«') != s.count('»')): bad['кавычки-дисбаланс'].append((i,s))
for k, lst in bad.items():
    print(f'--- {k}: {len(lst)}')
    for i,s in lst[:25]: print('   ', i, repr(s[:90]))
    if len(lst) > 25: print('    ...')
