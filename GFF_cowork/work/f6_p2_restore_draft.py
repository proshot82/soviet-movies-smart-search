import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, re
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
res={x['cat']:x for x in json.load(open('work/f6_p2_ann_scan.json',encoding='utf-8'))}
arts=json.load(open('work/f6_p2_articles.json',encoding='utf-8'))
CATS=[1111,1439,1646,1647,1649,1653,1677,1722,1724,2052,2149,2300,2519,2782,2795,2922,3031,3129,3157,3234,3245,3328,3584,3736,3742,4172,4259,4276,4486,5750,6173,6580,6597,6871,7078,994,1690,2106,2242,4462,5080,6117,6431,6361,7032,3046,4503,4604,5198,7034,7102,3805,3841,5316,5368,4116,3248,3579,3837,3166,3275,4275,1440,1974,2071,2546,5138,5724,5777,6662,6872,6940,3698,4349,5144,6911,6796]
out={}
for c in CATS:
    r=cat[c]; vol=r['source'].split('_')[0]; Ls=L.lines(vol); hs=L.headset(vol)
    x=res.get(c); a=arts.get(str(c))
    if x: h,e=x['h'],x['e']
    elif a: h,e=a['h'],a['e']
    else: print('=== cat',c,'NO BLOCK'); continue
    # расширяем блок до проверенной головы следующей статьи
    def verified_head(k):
        if k not in hs: return False
        t=Ls[k][1]
        if re.search(r'\d+\s?ч[.,]|мтр\. неизв', t[:160]): return True
        return any(re.match(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав|Реж|Сцен|Автор)', Ls[j][1]) for j in range(k+1,min(k+4,len(Ls))))
    while e<len(Ls) and e<h+60 and not verified_head(e): e+=1
    print(f'=== cat{c} «{r["title"]}» {r["year"]} {r["genre"]} | A[{len(r["annotation"] or "")}]: {(r["annotation"] or "")[:90]!r}')
    prose=[]
    for k in range(h,e):
        t=Ls[k][1]; kd='head' if k==h else L.kind(t)
        if kd=='prose' and k-h<=3 and re.match(r'^(?:[^А-ЯЁа-яё0-9]{0,6})(\d{4}\s?г[.,]|ВЭ\b|РУ\b|ВРЭ\b|им\. [А-Я]|цв\.|ш\.-э|ш\.-ф|\d+\s?ч[.,]|\d+[,.]?\d*\s?м[,.])', t) and len(t)<220: kd='headcont'
        mark='*' if kd=='prose' else ' '
        print(f'  {mark}[{k}] @{Ls[k][0]} {kd:8} {t[:130]}')
        if kd=='prose': prose.append((Ls[k][0], t.strip()))
    out[c]={'h':h,'e':e,'prose':prose}
json.dump(out, open('work/f6_p2_restore_blocks.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
