# -*- coding: utf-8 -*-
"""П4 a4 — лид-обрывки списков ролей (аннотация начинается со строчной/скобки)."""
import json, re
from collections import Counter

cat = json.load(open('state/catalog_f5_a3.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
A1 = {388,464,470,2024,2525,2739,3318,5244,5890,6966,3554,1186,
      1184,4767,5456,5468,5606,5645,5894,6334,6335,6546,7230,7231}

ABBR = {'им', 'Им', 'гос', 'Гос', 'засл', 'арт', 'худ', 'рук', 'руков', 'дир', 'реж',
        'ст', 'мл', 'проф', 'акад', 'т', 'тт', 'кап', 'п', 'о', 'др', 'дубл', 'исп', 'г', 'с', 'обл', 'оз', 'р'}
def sentences(text):
    bounds = [0]
    for m in re.finditer(r'[.!?…]+[»)]?\s+', text):
        end = m.end()
        prev = text[:m.start()].rstrip()
        wm = re.search(r'([А-ЯЁа-яёA-Za-z]+)$', prev)
        w = wm.group(1) if wm else ''
        if len(w) == 1 and (w.isupper() or w.isdigit()): continue
        if not w and re.search(r'\d$', text[:m.start()].rstrip()): continue
        if len(w) == 2 and w[0].isupper() and w[1].islower(): continue
        if w in ABBR: continue
        nxt = text[end:end+1]
        if nxt and not (nxt.isupper() or nxt in '«(0123456789'): continue
        bounds.append(end)
    bounds.append(len(text))
    return [(bounds[i], bounds[i+1]) for i in range(len(bounds)-1) if bounds[i+1] > bounds[i]]

PLOT_VERB = re.compile(r'\b(мечта|реша|хоче|прода|приезжа|прихо|узна|влюб|собира|отправ|попада|начина|станов|оказыва|живет|живут|работа|погиба|спаса|помога|встреча|уезжа|рассказыва|говор|дает|идет|едет|ведет)')
INIT = re.compile(r'\b[А-ЯЁ]\.\s*[А-ЯЁ][а-яё]+')
CREW = re.compile(r'(ред\.|адм\. группа|дир\. картины|консульт|монтаж\.|таж\.|ассист|комб\. съемки|мастер по свету|мастер-|опер\.|композ|звукоопер|дирижер|худ\.|грим|костюм|освет|муз\. ред|пост\.|механики аппаратуры|цветоуст)')
HEADFRAG = re.compile(r'^[^.]{0,60}?(ВЭ|РУ|ВРЭ)\s+[\dIVX]|^[^.]{0,45}?\d{4}\s*г\.')
SING = re.compile(r'^(Поет|Поют|Танцует|Исп\.|Исполняет|Играет оркестр|Диктор|Текст читает)')
def castlike(s):
    s = s.strip()
    if len(s) > 900: return False
    commas = s.count(',') + s.count(';')
    inits = len(INIT.findall(s))
    parens = s.count('(')
    crew = len(CREW.findall(s))
    if HEADFRAG.match(s) and len(s) < 130: return True          # обрывок собственной головы (ВЭ/год)
    if SING.match(s) and len(s) < 160 and not PLOT_VERB.search(s): return True
    if crew >= 2 and (commas >= 2 or s.count(';') >= 1) and not PLOT_VERB.search(s): return True
    if PLOT_VERB.search(s) and inits < 2 and crew < 2: return False
    if inits >= 2 and commas >= 2: return True
    if parens >= 2 and commas >= 1: return True
    if commas >= 3 and inits >= 1: return True
    fullnames = len(re.findall(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+', s))
    if fullnames >= 3 and commas >= 3 and not PLOT_VERB.search(s): return True
    if len(s) < 60 and (parens >= 1 or inits >= 1) and commas >= 1: return True
    if re.match(r'^[а-яё\-]+[),.;]', s) and (commas >= 1 or parens >= 1): return True
    if re.match(r'^\([«»А-ЯЁа-яё\s.]{2,30}\)[.,]', s) and len(s) < 60: return True
    return False

res, points, log = {}, [], []
for i, r in enumerate(cat):
    if i in strays or i in A1: continue
    t = r.get('annotation')
    if not t: continue
    if not re.match(r'\s*[а-яё(]', t): continue
    mj = re.match(r'\(\s+(?=[А-ЯЁО])', t)
    if mj:
        res[str(i)] = {'lead': mj.group(0), 'tail': None, 'class': 'лид-мусор (скобка)'}
        log.append((i, mj.group(0), t[mj.end():mj.end()+70])); continue
    sents = sentences(t)
    cut_end = 0
    for (s0, s1) in sents:
        if castlike(t[s0:s1]):
            cut_end = s1
        else:
            break
    if cut_end == 0:
        points.append((i, 'не-списочный строчный старт', t[:180])); continue
    lead = t[:cut_end]; rem = t[cut_end:].strip()
    if len(rem) < 40 and not re.match(r'(По\s|Экранизация|О\s|Об\s)', rem):
        points.append((i, 'остаток короток', t[:200])); continue
    if not (rem[0].isupper() or rem[0].isdigit() or rem[0] in '«…('):
        points.append((i, 'остаток не проза', lead[-60:] + ' ||| ' + rem[:70])); continue
    res[str(i)] = {'lead': lead, 'tail': None, 'class': 'лид-обрывок списка ролей'}
    log.append((i, lead[:90], rem[:70]))

json.dump({'cut': res}, open('work/a4_res_auto2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = open('work/a4_review2.txt', 'w', encoding='utf-8')
print(f'авто: {len(res)}; точечных: {len(points)}', file=out)
print('\n=== ТОЧЕЧНЫЕ ===', file=out)
for i, k, ctx in points: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== ВСЕ СРЕЗЫ ===', file=out)
for i, lead, rem in log:
    print(f'cat{i}: {lead!r} ||| {rem}', file=out)
out.close()
print('auto:', len(res), 'points:', len(points))
