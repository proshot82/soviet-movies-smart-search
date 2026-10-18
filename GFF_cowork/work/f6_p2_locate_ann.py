import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, re, time
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
arts=json.load(open('work/f6_p2_articles.json',encoding='utf-8'))
t0=time.time()
NL={}
def nlines(vol):
    if vol not in NL:
        NL[vol]=[L.norm_sp(t).replace(' ','') for n,t,p in L.lines(vol)]
    return NL[vol]
res={}
stats={'none':0,'found':0,'nomatch':0,'multi':0}
for i,r in enumerate(cat):
    a=r['annotation']
    if not a: stats['none']+=1; continue
    vol=r['source'].split('_')[0]
    # берём первые ~45 нормализованных знаков ПЕРВОГО предложения прозы (после возможного лида ищем по нескольким окнам)
    na=L.norm_sp(a).replace(' ','')
    probes=[na[:40]]
    if len(na)>200: probes.append(na[100:140]); probes.append(na[-60:-20])
    hits=None
    for pr in probes:
        if len(pr)<25: continue
        h=[j for j,s in enumerate(nlines(vol)) if pr in s]
        if h: hits=h; break
    if not hits: stats['nomatch']+=1; res[i]={'ann_line':None}; continue
    if len(hits)>1: stats['multi']+=1
    stats['found']+=1
    best=hits[0]
    a_t=arts.get(str(i))
    if a_t and len(hits)>1:
        inside=[h for h in hits if a_t['h']<=h<a_t['e']+3]
        best=inside[0] if inside else min(hits, key=lambda h: abs(h-a_t['h']))
    res[i]={'ann_line':best,'ann_hits':hits[:5]}
print('time',round(time.time()-t0,1),stats)
# сверка с расположением по титулу
bad=[]
for i,r in enumerate(cat):
    x=res.get(i); a=arts.get(str(i))
    if not x or x['ann_line'] is None or not a: continue
    if not (a['h']<=x['ann_line']<a['e']):
        bad.append(i)
print('аннотация вне статьи, найденной по титулу:', len(bad))
json.dump({str(k):v for k,v in res.items()}, open('work/f6_p2_ann_loc.json','w',encoding='utf-8'))
json.dump(bad, open('work/f6_p2_ann_mismatch.json','w',encoding='utf-8'))
