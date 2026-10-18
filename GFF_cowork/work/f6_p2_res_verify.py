# независимая проверка РЕЗОЛЮЦИИ (аннотации): (1) для lead/tail/mid — ни одна печатная прозаическая строка своей статьи, присутствовавшая в before, не потеряна в after; after ⊂ before;
# (2) для restore/prefix — after начинается с прозы, без маркеров титров; (3) общие: after без краевых пробелов/двойных пробелов, ≠ before.
import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, re
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
scan={x['cat']:x for x in json.load(open('work/f6_p2_ann_scan.json',encoding='utf-8'))}
res=json.load(open('scripts/f6_p2_resolution.json',encoding='utf-8'))
MARKERS=re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиография|БИБЛИОГРАФИЯ|дир\. картины|худ\.-пост|Роли дублируют|Роли озвучива|Фильм дублирован)')
def nm(s): return re.sub(r'[^а-яa-z0-9]','',s.lower().replace('ё','е'))
def verified_head(Ls,k,hs):
    if k not in hs: return False
    t=Ls[k][1]
    if re.search(r'\d+\s?ч[.,]|мтр\. неизв', t[:160]): return True
    return any(re.match(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав|Реж|Сцен|Автор)', Ls[j][1]) for j in range(k+1,min(k+4,len(Ls))))
bad=[]; notsub=[]; markers=[]; startlow=[]
for d in res['set']:
    if d['field']!='annotation': continue
    a=d['after']; b=d['before']
    if a is None: continue
    assert a==a.strip() and '  ' not in a and a!=b, d['cat']
    if MARKERS.search(a): markers.append((d['cat'], d['class'], MARKERS.search(a).group(), a[max(0,MARKERS.search(a).start()-40):MARKERS.search(a).start()+40]))
    if not re.match(r'^[А-ЯЁ0-9«"(…A-Z\[XIV]', a): startlow.append((d['cat'], d['class'], a[:50]))
    if d['class'] in ('restore','none'): continue
    if 'prefix' not in d['class'] and nm(a) not in nm(b): notsub.append(d['cat'])
    x=scan.get(d['cat'])
    if not x: continue
    Ls=L.lines(d['vol']); hs=L.headset(d['vol'])
    bn=nm(b); an=nm(a); lost=[]; end=x['e']
    while end<len(Ls) and end<x['e']+40 and not verified_head(Ls,end,hs): end+=1
    for k in range(x['h'], end):
        t=Ls[k][1]; kd=x['kinds'][k-x['h']] if k<x['e'] else L.kind(t)
        if kd!='prose': continue
        pn=nm(t)[:25]
        if len(pn)<8: continue
        if pn in bn and pn not in an: lost.append(Ls[k][0])
    if lost: bad.append((d['cat'],d['class'],lost[:5],len(lost)))
print('lost printed prose:', len(bad))
for b in bad: print('  ', b, cat[b[0]]['title'][:30])
print('after не подстрока before:', notsub)
print('маркеры титров в after:', len(markers)); [print('  ',m) for m in markers]
print('after не с прописной/цифры:', len(startlow)); [print('  ',m) for m in startlow]
