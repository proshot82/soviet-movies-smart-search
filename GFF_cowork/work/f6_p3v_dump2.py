import json, sys, re
sys.path.insert(0,'work')
import f6_p2_lib as L
cat=json.load(open('state/catalog_final_v2.json',encoding='utf-8'))
gap={x['cat']:x for x in json.load(open('work/f6_ref_gap_scan_v2.json',encoding='utf-8'))}
RX=re.compile(sys.argv[1]); N=int(sys.argv[2]); cats=[int(c) for c in sys.argv[3:]]
for i in cats:
    r=cat[i]; v=r['source'].split('_')[0]; Ls=L.lines(v); g=gap.get(i)
    a=r['annotation']; m=RX.search(a)
    print(f"===== cat{i} id{r['id']} {v} «{r['title']}» ({r['genre']}) h2={g and g.get('h2')} E={g and g.get('E')}")
    print("ANN[:200]: "+a[:200].replace('\n',' '))
    if m: print(f"HIT@{m.start()}: …{a[max(0,m.start()-100):m.start()]}[[{a[m.start():m.start()+160]}]]…")
    if g and 'h2' in g:
        for k in range(g['h2'], min(g['h2']+N, g['E'])):
            print(f"   @{k}: {Ls[k][1][:200]}")
