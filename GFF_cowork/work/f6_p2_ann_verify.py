# независимая проверка черновика: ни одна печатная прозаическая строка своей статьи (до проверенной головы следующей) не потеряна
import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, re
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
res={x['cat']:x for x in json.load(open('work/f6_p2_ann_scan.json',encoding='utf-8'))}
draft=json.load(open('work/f6_p2_ann_draft.json',encoding='utf-8'))
def nm(s): return re.sub(r'[^а-яa-z0-9]','',s.lower().replace('ё','е'))
def verified_head(Ls,k,hs):
    if k not in hs: return False
    t=Ls[k][1]
    if re.search(r'\d+\s?ч[.,]|мтр\. неизв', t[:160]): return True
    return any(re.match(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав|Реж|Сцен|Автор)', Ls[j][1]) for j in range(k+1,min(k+4,len(Ls))))
bad=[]
for d in draft:
    x=res[d['cat']]; Ls=L.lines(d['vol']); hs=L.headset(d['vol'])
    b=nm(d['before']); a=nm(d['after'])
    lost=[]
    end=x['e']
    while end<len(Ls) and end<x['e']+40 and not verified_head(Ls,end,hs): end+=1
    for k in range(x['h'], end):
        t=Ls[k][1]
        kd=x['kinds'][k-x['h']] if k<x['e'] else L.kind(t)
        if kd!='prose': continue
        pn=nm(t)[:25]
        if len(pn)<8: continue
        if pn in b and pn not in a: lost.append(Ls[k][0])
    if lost: bad.append((d['cat'],d['class'],lost[:5],len(lost)))
print('lost printed prose:', len(bad))
for b in bad: print('  ', b, cat[b[0]]['title'][:30], '| after[-70:]', repr([dd for dd in draft if dd['cat']==b[0]][0]['after'][-70:]))
mid=[d['cat'] for d in draft if 'prefix' not in d['class'] and nm(d['after']) not in nm(d['before'])]
print('after не подстрока before:', mid)
