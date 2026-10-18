import json, sys, re
sys.path.insert(0,'work')
import f6_p2_lib as L
cat=json.load(open('state/catalog_final_v2.json',encoding='utf-8'))
gap={x['cat']:x for x in json.load(open('work/f6_ref_gap_scan_v2.json',encoding='utf-8'))}
s2={x[0]:x for x in json.load(open('work/f6_p3v_scan2.json',encoding='utf-8'))}
N=int(sys.argv[1]); cats=[int(c) for c in sys.argv[2:]]
for i in cats:
    r=cat[i]; v=r['source'].split('_')[0]; Ls=L.lines(v); g=gap[i]; x=s2.get(i)
    ks=x[4] if x else None
    print(f"===== cat{i} id{r['id']} {v} «{r['title'][:40]}» ({r['genre']}) ks=@{ks} kcast=@{x[5] if x else None} E={g['E']}")
    print("ANN: "+r['annotation'][:N].replace('\n',' '))
    lo=(ks-1) if ks else g['h2']+1
    for k in range(lo, min(lo+5, g['E'])): print(f"   @{k}: {Ls[k][1][:N]}")
