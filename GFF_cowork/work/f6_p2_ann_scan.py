# -*- coding: utf-8 -*-
"""Ф6-П2-в: сверка аннотаций с печатью — лид (титры до прозы), хвост (за прозой: библиография/призы/мусор/
следующая статья), отсутствие прозы, утрата начала (PREFIX). Каждый срез валидируется: фрагменты лида/хвоста
должны соответствовать печатным НЕпрозаическим строкам (или строкам следующей статьи), не прозе своей статьи."""
import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, re
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
loc=json.load(open('work/f6_p2_ann_loc.json',encoding='utf-8'))
CONCERT=re.compile(r'(концерт|Концерт|опера|Опера|балет|Балет|ревю|Ревю|Музыкальн|музыкальн|Фильм-спектакль|спектакль|Оперетта|оперетта|Эстрадн|эстрадн|цирк|Цирк)')
HEADCONT=re.compile(r'^(?:[^А-ЯЁа-яё0-9]{0,6})(\d{4}\s?г[.,]|ВЭ\b|РУ\b|ВРЭ\b|им\. [А-Я]|«[^»]+»,? \d{4}|цв\.|ш\.-э|ш\.-ф|\d+\s?ч[.,]|\d+[,.]?\d*\s?м[,.]|киностудия|Киностудия|при участии|\(СССР\)|сер\.|2-я сер|1-я сер)')
HARD=re.compile(r'^(?:[^А-ЯЁа-яё0-9]{0,6})(Ав[тг]|Авт|Реж|Опер|Худ|Композ|Звукоопер|Монтаж|Ассист|Ред\.|Дир\. картины|Роли (озвуч|дубл|исполн)|В ролях|В роли|Кукловод|Мультипл|Комб|Костюм|Грим|Сцен|Автор|2-й|Гл\. |Тех\. ассист|Дубл|Фильм дублирован|Пом\. |Куклы|Балетмейстер|Дирижер|Хореограф|Пост\.|Звукооформ|Адм\. группа|Муз\. ред|Консульт|Лит\. |Над фильмом|Съемочная группа|Киногруппа|Студия благодарит|Группа каскадеров|Каскадер|Трюки|Мастер|Цветоуст|Инженер|Пиротехник|Фехтован|ВЭ|РУ)', re.I)
ENSLINE=re.compile(r'^(?:[^А-ЯЁа-яё]{0,4})(Государственн|Симфонич|Оркестр|Хор|Ансамбл|Балет|Солист|Эстрадн|Камерн|Академическ|Вокальн|Инструментальн|Рок-|Джаз|Духов|Народн|Русский народный|Песн|Романс|Исполнит|Исп\. |Дирижер|Хореограф|Балетмейстер|Партии|Играет|В фильме (исполня|звуч)|В концерте|В фильме-концерте|Музыка)', re.I)
SERIES=re.compile(r'^\s*((\d-я|[IVX]+)\s*серия|Часть (перв|втор|треть))[\s.:—-]*$')
def nmap(s):
    out=[]; idx=[]
    for k,ch in enumerate(s.lower().replace('ё','е')):
        if re.match(r'[а-яa-z0-9]', ch): out.append(ch); idx.append(k)
    return ''.join(out), idx
def find_in(A_n, A_idx, probe_n):
    if len(probe_n)<5: return None
    p=A_n.find(probe_n)
    return None if p<0 else (A_idx[p], A_idx[p+len(probe_n)-1]+1)
def chunks(text):
    parts=re.split(r'(?<=[.!?;])\s+', text.strip())
    return [p for p in parts if re.search(r'[а-яёА-ЯЁ0-9]', p)]
def match_chunks(text, allowed, forbidden):
    """→ (ok, notes): каждый фрагмент ≥6 норм. знаков должен встречаться в allowed-строках; встреча в forbidden без allowed — запрет"""
    ok=True; notes=[]
    for ch in chunks(text):
        cn,_=nmap(ch)
        if len(cn)<6: continue
        key=cn[:20] if len(cn)>=20 else cn
        in_a=any(key in s or (len(s)>=8 and s in cn) for s in allowed)
        in_f=any(key in s for s in forbidden)
        if in_f and not in_a: ok=False; notes.append('in-prose:'+ch[:40]); break
        if not in_a: notes.append('unmatched:'+ch[:40])
    return ok, notes
res=[]
for i,r in enumerate(cat):
    a=r['annotation']
    x=loc.get(str(i))
    if not a or not x or x['ann_line'] is None: continue
    vol=r['source'].split('_')[0]; Ls=L.lines(vol); hs=L.headset(vol)
    j=x['ann_line']
    h=j
    while h>0 and h not in hs: h-=1
    e=j+1
    while e<len(Ls) and e not in hs: e+=1
    concert=bool(CONCERT.search(r['genre'] or ''))
    kinds={}; LN={}
    lo=max(0,h-12); hi=min(len(Ls), e+40)
    for k in range(lo,hi):
        t=Ls[k][1]; LN[k]=nmap(t)[0]
        if k in hs: kinds[k]='head'; continue
        kd=L.kind(t, concert)
        if kd=='prose' and h<k<=h+3 and HEADCONT.match(t) and len(t)<220: kd='headcont'
        kinds[k]=kd
    A_n,A_idx=nmap(a)
    prose_idx=[k for k in range(h,e) if kinds[k]=='prose']
    rec={'cat':i,'vol':vol,'h':h,'e':e,'head':Ls[h][0],'concert':concert,'kinds':[kinds[k] for k in range(h,e)]}
    if not prose_idx:
        rec['class']='NOPROSE-PRINT'; res.append(rec); continue
    a0=A_n[:25]
    start=None
    for k in range(h,e):
        s=LN[k]
        if not s: continue
        if s.startswith(a0) or (len(s)<25 and A_n.startswith(s) and len(s)>=5): start=('line',k); break
    if start is None:
        for k in range(h,e):
            if a0 and a0 in LN[k]: start=('mid',k); break
    if start is None:
        for k in range(lo,h):
            if a0 and a0 in LN[k]: start=('prev',k); break
    rec['start']=start
    if start and start[0]=='mid' and kinds[start[1]]!='prose':
        t=Ls[start[1]][1]; tn,tidx=nmap(t); off=tn.find(a0)
        if off>=0:
            sub=t[tidx[off]:]
            if L.kind(sub, concert)=='prose' and re.match(r'^[А-ЯЁ0-9«"(…]', sub):
                start=('line',start[1]); kinds[start[1]]='prose'; rec['start']=start; rec['note']='mid-line prose after credits'
    firstp=None
    for k in prose_idx:
        s=LN[k]; pr=s[:30] if len(s)>=30 else s
        if len(pr)<5: continue
        f=find_in(A_n,A_idx,pr)
        if f: firstp=(k,f[0]); break
    last=None
    for k in reversed(prose_idx):
        s=LN[k]; pr=s[-30:] if len(s)>=30 else s
        if len(pr)<5: continue
        f=find_in(A_n,A_idx,pr)
        if f: last=(k,f[1]); break
    own_prose=[LN[k] for k in prose_idx]
    nonprose_own=[LN[k] for k in range(lo,e) if kinds[k]!='prose']
    next_all=[LN[k] for k in range(e,hi)]
    cls=[]
    if start is None:
        cls.append('START-UNMATCHED')
    else:
        kd=kinds[start[1]]
        if start[0]=='mid' and kd=='prose':
            t=Ls[start[1]][1]; tn,tidx=nmap(t); off=tn.find(a0)
            rec['prefix']=t[:tidx[off]] if off>=0 else None; rec['prefix_line']=Ls[start[1]][0]
            cls.append('PREFIX?')
        elif kd!='prose' or start[0]=='prev':
            if firstp is None:
                cls.append('NOPROSE-ANN')
            elif firstp[1]>0:
                p1=firstp[1]; lead=a[:p1]; after=a[p1:]
                rec.update({'lead_pos':p1,'lead':lead,'first_prose_line':Ls[firstp[0]][0]})
                if SERIES.match(lead):
                    cls.append('LEAD-SERIES')
                else:
                    ok,notes=match_chunks(lead, nonprose_own, own_prose)
                    rec['lead_ok']=ok; rec['lead_notes']=notes
                    if concert:
                        # для концертной группы допустимы только «жёсткие» титры: каждая строка-источник лида должна быть HARD и не оркестровой
                        soft=[]
                        for c in chunks(lead):
                            cn=nmap(c)[0]
                            if len(cn)<6: continue
                            key=cn[:20] if len(cn)>=20 else cn
                            srcs=[k for k in range(lo,e) if kinds[k]!='prose' and (key in LN[k] or (len(LN[k])>=8 and LN[k] in cn))]
                            if not srcs or any((not HARD.match(Ls[k][1])) or ENSLINE.match(Ls[k][1]) for k in srcs): soft.append(c[:30])
                        if soft: notes=notes+['concert-soft:'+str(soft)]; rec['lead_notes']=notes; ok=False
                    cls.append(('LEAD' if not notes else 'LEAD?') if ok else 'LEAD-X')
                    if not re.match(r'^[А-ЯЁ0-9«"(…A-Z\[]', after): cls.append('after-lower')
                    if len(after)<40: cls.append('after-short')
            else:
                cls.append('LEAD-ZERO'); rec['lead_pos']=0; rec['lead']=''
        else:
            if start[0]=='mid': cls.append('START-MID-PROSE')
    if last:
        tp=last[1]
        # сохраняем завершающую пунктуацию после последнего печатного знака прозы
        m=re.match(r'[.!?…»)"\']*', a[tp:]); tp2=tp+len(m.group(0))
        tail=a[tp2:]
        rec.update({'tail':tail,'tail_pos':tp2,'last_prose_line':Ls[last[0]][0]})
        if re.search(r'[а-яёА-ЯЁ0-9]', tail):
            if re.fullmatch(r'[\s.\-—,;:!?»«\'’()*^<>❖♦■>/\\|]*\d{1,4}[\s.\-—,;:!?»«\'’()*^<>❖♦■]*', tail) or not re.search(r'[а-яёА-ЯЁ]', tail):
                cls.append('TAIL-JUNK')
            else:
                # классификация фрагментов хвоста по печатным строкам: своя проза → продолжение; титры/библиография/призы/мусор/голова следующей → срез
                def kind_of_chunk(ch):
                    cn,_=nmap(ch)
                    if len(cn)<6: return 'short'
                    key=cn[:20] if len(cn)>=20 else cn
                    for k in range(h,e):
                        if key in LN[k] or (len(LN[k])>=8 and LN[k] in cn): return 'own-'+kinds[k]
                    for k in list(range(e,hi))+list(range(lo,h)):
                        if key in LN[k] or (len(LN[k])>=8 and LN[k] in cn): return ('next-' if k>=e else 'prev-')+kinds[k]
                    return 'unmatched'
                cks=[(ch,kind_of_chunk(ch)) for ch in chunks(tail)]
                rec['tail_chunks']=[(c[:40],k) for c,k in cks]
                kk=[k for c,k in cks if k!='short']
                # проверенная голова следующей статьи: за строкой-головой в 1–3 строках идут титры «Авт. сцен./Реж.» либо в голове есть метраж
                def verified_head(k):
                    if k not in hs: return False
                    if re.search(r'\d+\s?ч[.,]|мтр\. неизв', Ls[k][1][:160]): return True
                    return any(kinds.get(kk2)=='cred' and re.match(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав|Реж|Сцен|Автор)', Ls[kk2][1]) for kk2 in range(k+1, min(k+4, hi)))
                def first_next_head_ok():
                    cn,_=nmap(cks[0][0]); key=cn[:20] if len(cn)>=20 else cn
                    for k in range(e,hi):
                        if key in LN[k] or (len(LN[k])>=8 and LN[k] in cn): return verified_head(k)
                    return False
                if not kk: cls.append('TAIL-JUNK')
                elif kk[0]=='own-prose' or kk[0]=='next-prose' or kk[0]=='prev-prose': cls.append('TAIL-CONT')
                elif kk[0]=='unmatched': cls.append('TAIL?')
                elif kk[0]=='next-head' and not first_next_head_ok(): cls.append('TAIL-CONT')
                elif any(k=='own-prose' for k in kk): cls.append('TAIL-MIXED')
                elif any(k=='unmatched' for k in kk): cls.append('TAIL?')
                else: cls.append('TAIL')
    else:
        cls.append('LAST-UNMATCHED')
    rec['class']='+'.join(cls) if cls else 'OK'
    res.append(rec)
from collections import Counter
print(Counter(x['class'] for x in res))
json.dump(res, open('work/f6_p2_ann_scan.json','w',encoding='utf-8'), ensure_ascii=False)
