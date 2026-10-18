# -*- coding: utf-8 -*-
"""Ф6-П2-в: сборка черновика резолюции по аннотациям из скана (work/f6_p2_ann_scan.json):
LEAD (лид → срез до первой печатной прозы), TAIL (хвост после последней прозы: библиография/призы/мусор/следующая статья),
PREFIX (восстановление утраченного начала абзаца по печати). Каждая позиция несёт vol/@строки-свидетельства."""
import sys; sys.path.insert(0,'work')
import f6_p2_lib as L, json, re
cat=json.load(open('state/catalog_f6_p1.json',encoding='utf-8'))
res=json.load(open('work/f6_p2_ann_scan.json',encoding='utf-8'))
reg=json.load(open('state/Ф5_стабы_реестр.json',encoding='utf-8'))
regc={e['cat']:e['state'] for e in reg['entries'] if e['field']=='annotation'}
STRONG=re.compile(r'(дирижер|дириж\.|дубл\.|дублирован|дубляж|озвучива|худ\. рук|руководител|соло|песню исполня|песни исполня|исполнит|текст чита|перевод чита|балетмейстер|солист|под управлением|под упр\.|звукоопер|опер\.|ассист|монтаж|композ|авт\. текст|авт\. сцен|реж\.|худ\.|костюм|грим|декор|\bред\.|дир\. картины|комб\. съемки|консульт|роли озвучива|роли дублир|в ролях|в роли|каскадер|снимались|принимал[иа]? участие|благодарит|работали|кукловод|мультипл|интермеди|поет |от автора|блок дир|подбор музыки|музыку записал|дикторы|диктор|исп\.|соло-рояль|оркестр|ансамбл|хор\b|записал|\d{4} г\.|ВЭ |РУ )', re.I)
out=[]
def rec(cat_i, cls, before, after, lines, note):
    assert after!=before and after==after.strip() and after
    out.append({'cat':cat_i,'title':cat[cat_i]['title'],'source':cat[cat_i]['source'],'field':'annotation','class':cls,'before':before,'after':after,'vol':cat[cat_i]['source'].split('_')[0],'lines':lines,'note':note})
skipped=[]
for x in res:
    i=x['cat']; a=cat[i]['annotation']; cls=x['class'].split('+'); Ls=L.lines(x['vol'])
    if regc.get(i) in ('formula','source-only','content','note'): 
        if any(c.startswith(('LEAD','TAIL','PREFIX')) for c in cls): skipped.append((i,'register:'+regc[i],x['class']))
        continue
    lead_pos=None; tail_pos=None; prefix=None; notes=[]
    # LEAD
    if 'LEAD' in cls:
        lead_pos=x['lead_pos']; notes.append(f"лид {lead_pos} зн. до печатной прозы @{x['first_prose_line']}")
    elif 'START-UNMATCHED' in cls and x.get('lead_pos') is None:
        pass
    # TAIL
    if 'TAIL' in cls or 'TAIL-JUNK' in cls:
        tail_pos=x['tail_pos']; notes.append(f"хвост {len(a)-tail_pos} зн. после последней печатной прозы @{x['last_prose_line']}" + (' (мусор/номер страницы)' if 'TAIL-JUNK' in cls else ''))
    # PREFIX
    if 'PREFIX?' in cls and x.get('prefix') is not None:
        p=x['prefix']
        if re.match(r'^(\.\.\.)?\s*[А-ЯЁ0-9«"]', p) and not re.match(r'^\s*$', p):
            prefix=p; notes.append(f"утраченное начало абзаца по печати @{x['prefix_line']}")
        else:
            skipped.append((i,'prefix-midline',x['class']))
    if lead_pos is None and tail_pos is None and prefix is None: continue
    if 'after-lower' in cls or 'after-short' in cls: skipped.append((i,'after-check',x['class'])); continue
    after=a
    if tail_pos is not None: after=after[:tail_pos]
    if lead_pos is not None: after=after[lead_pos:]
    after=after.strip()
    if prefix is not None: after=(prefix+after).strip()
    after=re.sub(r'\s+',' ',after)
    if lead_pos is not None and not re.match(r'^[А-ЯЁ0-9«"(…A-Z\[]', after): skipped.append((i,'after-lower2',x['class'])); continue
    if len(after)<40 and prefix is None: skipped.append((i,'after-short2',x['class'])); continue
    c=[]
    if lead_pos is not None: c.append('lead')
    if tail_pos is not None: c.append('tail')
    if prefix is not None: c.append('prefix')
    lines=sorted(set(v for v in (x.get('first_prose_line'), x.get('last_prose_line'), x.get('prefix_line')) if v is not None))
    rec(i,'+'.join(c),a,after,lines,'; '.join(notes)+('; концертная группа: срезаны только жёсткие титры' if x['concert'] else ''))
from collections import Counter
print('draft:', len(out), Counter(o['class'] for o in out)); print('skipped:', len(skipped), Counter(s[1] for s in skipped))
json.dump(out, open('work/f6_p2_ann_draft.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(skipped, open('work/f6_p2_ann_skipped.json','w',encoding='utf-8'), ensure_ascii=False)
