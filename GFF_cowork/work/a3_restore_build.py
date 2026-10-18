# -*- coding: utf-8 -*-
"""П4 a3 — сборка restore-текстов для лид-всё записей (проза из томов)."""
import json, re, sys
sys.path.insert(0, 'scripts')
from g_locate_cowork import norm

cat = json.load(open('state/catalog_f5_a2.json', encoding='utf-8'))
LEADALL = [2557,2661,2752,2794,2820,2873,2878,3000,3008,3055,3121,3160,3267,3276,3304,3306,3324,3343,3451,3464,3478,3485,3640,3650,3674,3716,3718,5266,5438]
cache = {}
def lines_of(v):
    if v not in cache:
        cache[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    return cache[v]

CREDIT = re.compile(r'^(Авт\.|Реж\.?|Гл\. опер|Опер\.|Худ\.|Композ|Звукоопер|Монтаж|Ассист|Дир\. |Дирижер|Комб|Ред\.|В ролях|Роли дубл|Роли озвуч|Фильм дублирован|Пом\. реж|Консульт|Костюм|Грим|Авт\. текста|Text|Худ\.-|Муз\. |Гос\w+ симфонический|Симфонический оркестр|Оркестр |Камерный оркестр|Хор |Ансамбль |Эстрадн|Дрессировщик|В съемках|Худ\. руководитель|Государственный|Заслуженный)')
HEAD = re.compile(r'^[«»A-ZА-ЯЁ\d][^a-zа-яё]{4,}\.\s|^\S{1,25}\.\s+(Кино|Экраниз|Драма|Комедия|Мелодрама|Киноповесть)')
BIB = re.compile(r'^(Библиография|БИБЛИОГРАФИЯ)')
PRIZE = re.compile(r'^(На\s.{0,80}(фестивал|смотре|конкурс)|Приз|Диплом|Преми)')
def head_like(t):
    return bool(re.match(r'^[А-ЯЁ«][А-ЯЁ«»\-!,.?\s\d]{5,}\.\s', t)) and re.search(r'\d+\s*ч\.,|\bм,|\bг\.,\s*(ВЭ|РУ|ВРЭ)', t[:160])

out = open('work/a3_restore_ctx.txt', 'w', encoding='utf-8')
restores = {}
for c in LEADALL:
    r = cat[c]; v = r['source'].split('_')[0]
    L = lines_of(v)
    nl = [norm(t) for _, t, _ in L]
    nd = norm(r['title'])[:24]
    hits = [i for i, s in enumerate(nl) if nd and nd in s and head_like(L[i][1].strip())]
    print(f'##### cat{c} {v} «{r["title"]}» head-hits={hits}', file=out)
    if len(hits) != 1:
        print('   !! неоднозначно — вручную', file=out); continue
    h = hits[0]
    prose, state, used = [], 'credits', []
    for j in range(h+1, min(len(L), h+40)):
        t = L[j][1].strip()
        if not t: continue
        if BIB.match(t) or PRIZE.match(t): break
        if head_like(t): break
        if CREDIT.match(t):
            if state == 'prose': break   # титры после прозы = следующий блок
            continue
        state = 'prose'; prose.append((j, t)); used.append(j)
    if not prose:
        print('   !! прозы не найдено — вручную/None', file=out); continue
    txt = prose[0][1]
    for j, t in prose[1:]:
        txt = (txt[:-1] + t) if txt.endswith('-') else (txt + ' ' + t)
    txt = re.sub(r'\s+', ' ', txt).strip()
    restores[str(c)] = {'text': txt, 'vol': v, 'lines': used,
        'note': 'проза статьи (лид-всё: прежняя аннотация состояла из титров дубляжа/оркестра)'}
    print(f'   LINES {used}', file=out)
    print(f'   TEXT: {txt}', file=out)
    print(file=out)
json.dump(restores, open('work/a3_restores_draft.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out.close()
print('built:', len(restores), 'of', len(LEADALL))
