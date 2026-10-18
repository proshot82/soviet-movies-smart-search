# -*- coding: utf-8 -*-
"""k4: резолюция из work/p6_k4_parsed.json (restore аннотаций киножурналов)."""
import json, re, sys
GEN = sys.argv[1] if len(sys.argv) > 1 else '4'
CAT = {'4': 'state/catalog_f5_k3.json', '5': 'state/catalog_f5_k4.json'}[GEN]
cat = json.load(open(CAT, encoding='utf-8'))
P = json.load(open(f'work/p6_k{GEN}_parsed.json', encoding='utf-8'))
SET = {}
for k, v in P.items():
    if v['probs']: continue
    c = int(k)
    assert cat[c]['annotation'] == v['stub']
    lines = [v['head'], v['intro_line']] + [ln for s in v['sujets'] for ln in s['lines']]
    titles = '; '.join(s['title'] for s in v['sujets'])
    note = (f"стаб «{v['stub'][:60]}…» → полный текст статьи: интро + {len(v['sujets'])} сюжет(ов) [{titles}] "
            f"(голова @{v['head']}, интро @{v['intro_line']}, блоки до @{v['end'] - 1}); титры/студии сюжетов не включены")
    if v.get('accept'): note += '; ПРИНЯТО С ПОМЕТКОЙ: ' + v['accept'] + ' [' + '; '.join(v.get('probs_accepted', [])) + ']'
    if v.get('note'): note += f"; заметка перед интро: «{v['note']}»"
    SET[k] = {'field': 'annotation', 'before': v['stub'], 'after': v['text'], 'vol': v['vol'], 'line': lines,
              'class': 'restore', 'note': note}
json.dump({'set': SET, 'confirm': {}}, open(f'scripts/k{GEN}_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
import collections
print('SET', len(SET), collections.Counter(v['vol'] for v in SET.values()))
print('titles Фитиль/Ералаш:', sum(1 for k in SET if cat[int(k)]['title'].startswith('Фитиль')), sum(1 for k in SET if cat[int(k)]['title'].startswith('Ералаш')), 'other:', [k for k in SET if not re.match(r'^(Фитиль|Ералаш)', cat[int(k)]['title'])])
