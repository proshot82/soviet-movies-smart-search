# показать запись каталога и печатный блок статьи: python3 work/f6_p3_show.py cat [before] [after] [maxlen]
import sys, json, re
sys.path.insert(0, 'work')
import f6_p2_lib as L
cat = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
res = {x['cat']: x for x in json.load(open('work/f6_p3a_tail_scan.json', encoding='utf-8'))}
arts = json.load(open('work/f6_p2_articles.json', encoding='utf-8'))
i = int(sys.argv[1]); before = int(sys.argv[2]) if len(sys.argv) > 2 else 1; after = int(sys.argv[3]) if len(sys.argv) > 3 else 4; maxlen = int(sys.argv[4]) if len(sys.argv) > 4 else 700
r = cat[i]; x = res.get(i, {}); vol = r['source'].split('_')[0]
print(f"cat{i} {r['source']} «{r['title']}» {r['year']} {r['genre']} | {r['studio']} | class={x.get('class')} h={x.get('h')} e={x.get('e')} last={x.get('last_line')}")
print('ANN:', repr(r['annotation']))
h, e = x.get('h'), x.get('e')
if h is None and str(i) in arts: h, e = arts[str(i)]['h'], arts[str(i)]['e']
if h is None:
    f = L.find_article(vol, r['title'], r['year'])
    if f: h, e, _ = f
if h is None: print('нет локализации'); sys.exit()
Ls = L.lines(vol)
for j in range(max(0, h - before), min(len(Ls), e + after)):
    t = Ls[j][1]
    print(f"@{j}{'*' if j == x.get('last_line') else ' '}{'H' if j in L.headset(vol) else ' '} {t[:maxlen]}{' …[' + str(len(t)) + ']' if len(t) > maxlen else ''}")
