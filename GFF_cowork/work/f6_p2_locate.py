import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, time
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
t0=time.time()
miss=[]; multi=[]; fz=[]
res={}
for i,r in enumerate(cat):
    vol=r['source'].split('_')[0]
    fa=L.find_article(vol, r['title'], r['year'], fuzzy=False)
    if not fa:
        fa=L.find_article(vol, r['title'], r['year'], fuzzy=True)
        if fa: fz.append(i)
    if not fa: miss.append(i)
    else:
        res[i]={'h':fa[0],'e':fa[1],'cands':fa[2],'fuzzy':i in fz}
        if len(fa[2])>1: multi.append(i)
print('time', round(time.time()-t0,1), 'miss', len(miss), 'fuzzy-found', len(fz), 'multi', len(multi))
print('miss', miss)
json.dump({str(k):v for k,v in res.items()}, open('work/f6_p2_articles.json','w',encoding='utf-8'))
