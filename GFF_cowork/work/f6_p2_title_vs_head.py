import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, re
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
al=json.load(open('state/alignment_f6_p1.json',encoding='utf-8'))
m=json.load(open('state/index_master_f6_p1.json',encoding='utf-8'))
card={r['cat_pos']:r for r in m['rows'] if r['kind']=='card'}
arts=json.load(open('work/f6_p2_articles.json',encoding='utf-8'))
def spaced_segment(s_sp, nt_ns):
    ns=''; idx=[]
    for k,ch in enumerate(s_sp):
        if ch!=' ': ns+=ch; idx.append(k)
    p=ns.find(nt_ns)
    if p<0: return None
    return s_sp[idx[p]:idx[p+len(nt_ns)-1]+1]
def headseg(t):
    """сегмент головы до жанра: до первой точки/запятой за которой строчная"""
    mm=re.search(r'[.,\-—]\s+[А-ЯЁ]?[а-яё]', t)
    return t[:mm.start()] if mm else t[:80]
out=[]
for i,r in enumerate(cat):
    a=arts.get(str(i))
    if not a: continue
    vol=r['source'].split('_')[0]
    t=L.lines(vol)[a['h']][1]
    base=re.sub(r'\s*\(«.*$','',r['title']).strip()
    base2=re.sub(r'\s*\([^)]*\)\s*$','',base).strip() or base
    nt_sp=L.norm_sp(base2); nt_ns=nt_sp.replace(' ','')
    s_sp=L.norm_sp(t)
    seg=spaced_segment(s_sp, nt_ns)
    cls=None
    if seg is None: cls='FUZZY'
    elif seg!=nt_sp: cls='SPACE'
    if cls:
        x=card[i]['xlsx_title']; f3=al[i]['cat_title']
        out.append({'cat':i,'cls':cls,'title':r['title'],'head':headseg(t).strip(),'line':L.lines(vol)[a['h']][0],'vol':vol,'xlsx':x if x!=r['title'] else '=','f3':f3 if f3!=r['title'] else '=','fuzzy':a['fuzzy']})
json.dump(out, open('work/f6_p2_title_vs_head.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out))
