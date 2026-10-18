import json, sys
sys.path.insert(0,'work')
import f6_p2_lib as L
cat=json.load(open('state/catalog_final_v2.json',encoding='utf-8'))
gap={x['cat']:x for x in json.load(open('work/f6_ref_gap_scan_v2.json',encoding='utf-8'))}
scan=json.load(open('work/f6_p3v_scan.json',encoding='utf-8'))
W=int(sys.argv[1]); cats=[int(c) for c in sys.argv[2:]]
for i in cats:
    r=cat[i]; v=r['source'].split('_')[0]; Ls=L.lines(v); g=gap[i]; x=scan.get(str(i),{})
    print(f"===== cat{i} id{r['id']} {v} «{r['title']}» ({r['genre']}) h2={g['h2']} kc={x.get('kc')} P={x.get('P')} E={g['E']}")
    print("ANN: "+r['annotation'][:W].replace('\n',' ')); print("ANN-END: …"+r['annotation'][-120:])
    ks=set(k for _,k,_,_ in x.get('cut',[]))
    hi=max([x.get('P') or g['h2']]+list(ks))+3
    for k in range(g['h2'], min(hi+1, g['E'])):
        print(f"  {'*' if k in ks else ' '}@{k}: {Ls[k][1][:W]}")
