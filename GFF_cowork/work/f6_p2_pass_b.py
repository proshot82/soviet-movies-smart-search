# -*- coding: utf-8 -*-
"""Ф6-П2 pass B: остаточные титры в аннотациях (после авто-черновика и ручных правок): лид из титров-продолжений
(строки титров, разорванные страницей и не начинающиеся с ключевого слова) и титры сюжетов внутри киноальманахов (MID).
Опирается на печать: срез до первой печатной прозаической строки статьи; удаление печатных строк титров, найденных внутри."""
import sys, json, re
sys.path.insert(0, 'work')
import f6_p2_lib as L
cat = json.load(open('state/catalog_f6_p1.json', encoding='utf-8'))
res = json.load(open('scripts/f6_p2_resolution.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p2_ann_scan.json', encoding='utf-8'))}
art = json.load(open('work/f6_p2_articles.json', encoding='utf-8'))
S = {(e['cat'], e['field']): e for e in res['set']}
cur = {i: (S[(i, 'annotation')]['after'] if (i, 'annotation') in S else r['annotation']) for i, r in enumerate(cat)}
M = re.compile(r'(Авт\. сцен|Авт\.сцен|Авт\. сцеп|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Фильм озвучен|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|монтаж\.|композ\.|консульт\.|Дирижер|дирижер|Гл\. опер|гл\. опер|Реж\.-пост|Опер\.-пост)')
CREDKEY = re.compile(r'(?:^|[;,.:] ?)(?:ред|дир\. картины|дир\. фильма|дир\. группы|монтаж|композ|консульт|консулы|звукоопер|опер|худ|реж|ассист|грим|костюм|дирижер[ы]?|адм|администр|муз\. ред|дубл|тех\. консульт|воен\. консульт|гл\. консульт|авт\. текст|исп\. песн|исполнит|солист|хормейстер|балетмейстер|худ\. руководитель|текст читает|читает за кадром|ведущий)\b', re.I)
INIT = re.compile(r'[А-ЯЁXBHKMTCAEOP]\.\s?-?[А-ЯЁXBHKMTCAEOP]?[а-яё]{2,}')
ENS = re.compile(r'(оркестр|ансамбль|хор\b|капелла|трио|квартет|балет|труппа)', re.I)
def credline(t):
    """титры-продолжение / оркестр-дирижёр: ключевые слова титров + плотность инициалов, без длинных фраз прозы"""
    if L.kind(t) == 'cred': return True
    k = len(CREDKEY.findall(t)); ini = len(INIT.findall(t))
    if ENS.search(t) and re.search(r'дирижер|руководител|балетмейстер|хормейстер|солист', t, re.I) and len(t) < 260 and not re.search(r'\b(он|она|они|его|ее|их|который|которая|которые)\b', t.lower()[:200]): return True
    if k >= 1 and ini >= 1 and t.count(';') >= 1 and len(t) < 400: return True
    if k >= 2 and ini >= 1 and len(t) < 300: return True
    if M.search(t) and ini >= 1 and len(t) < 200 and not re.search(r'\b(он|она|они|его|ее|их|который|которая|которые|что|как)\b', t.lower()): return True
    return False
def nmap(s):
    out = []; idx = []
    for i, ch in enumerate(s.lower().replace('ё', 'е').translate(L._TR)):
        if ('а' <= ch <= 'я') or ('a' <= ch <= 'z') or ('0' <= ch <= '9'): out.append(ch); idx.append(i)
    return ''.join(out), idx
SOFT = re.compile(r'^(В фильме (звуч|исполня|использован[аы]? (музык|фрагмент|произведени|симфони|песн|романс|увертюр))|Музыка |Муз\. |Мелодии |Песн[июя] |Исполн|Фильм (дублирован|озвучен)|(Русский )?[Тт]екст чита|Роли (озвуч|дубл)|В эпизодах|Государственный|Симфонический|Оркестр|Ансамбль|Камерный|Вокальн|Лебедей вырастили|Авт\. (стихотворения|муз)|Ведущ|Танцы исполня|Исполняется|Звуч[аи]т|Дикторы?|Хор |Балет |Над фильмом|Дублир|В работе над фильмом|Инструментальн|Эстрадн|Джаз|Квартет|Трио |Текст[ыа]? песен|Стихи |Романс)')
TITLE_CRED = re.compile(r'^((?:[«"][^»"]{1,60}[»"]|[А-ЯЁ][^.!?]{1,60})[.!?»]\s+)(Авт|Реж|Сцен|Автор|Опер|Худ|Композ)')
props = []; manual = []
for c, a in cur.items():
    if not a or not M.search(a): continue
    x = scan.get(c); ar = art.get(str(c))
    h = x['h'] if x else (ar['h'] if ar else None)
    if h is None: manual.append((c, 'нет статьи')); continue
    v = cat[c]['source'].split('_')[0]; Ls = L.lines(v); hs = L.headset(v)
    e = x['e'] if x else ar['e']
    end = e
    while end < len(Ls) and end < e + 40 and not (end in hs and (re.search(r'\d+\s?ч[.,]|мтр\. неизв', Ls[end][1][:160]) or any(re.match(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав|Реж|Сцен|Автор)', Ls[j][1]) for j in range(end + 1, min(end + 4, len(Ls)))))): end += 1
    an, idx = nmap(a)
    # классификация строк блока
    rows = []
    for k in range(h + 1, end):
        t = Ls[k][1].strip(); kd = L.kind(t, bool(x and x['concert']))
        if kd in ('junk', 'bib', 'prize'): rows.append((k, kd, t)); continue
        if credline(t): rows.append((k, 'cred', t)); continue
        if k <= h + 3 and re.search(r'\d{4}\s?г[.,]|ВЭ|РУ|ВРЭ|\d+\s?ч[.,]|\d+ м\b|киностудия', t) and len(t) < 220 and not re.match(r'^[А-ЯЁ][а-яё]+ [а-яё]', t): rows.append((k, 'headcont', t)); continue
        rows.append((k, kd, t))
    # позиции строк в аннотации
    pos = []
    for k, kd, t in rows:
        tn, _ = nmap(t)
        if len(tn) < 12: pos.append((k, kd, t, None)); continue
        q = an.find(tn[:25])
        pos.append((k, kd, t, q if q >= 0 else None))
    prose_found = [(k, q) for k, kd, t, q in pos if kd == 'prose' and q is not None and not (q == 0 and M.search(t))]
    if not prose_found: manual.append((c, 'проза печати не найдена в аннотации')); continue
    first_q = min(q for k, q in prose_found)
    new = a; ops = []
    # LEAD: всё до первой найденной печатной прозы, если там есть маркер титров / титроподобная строка
    if first_q > 0:
        lead_raw = a[:idx[first_q]]
        if M.search(lead_raw) or credline(lead_raw) or len(lead_raw.strip()) < 3:
            ops.append(('lead', 0, idx[first_q], lead_raw))
        else:
            manual.append((c, f'начало без маркера, но проза печати позже: {lead_raw[:80]!r}')); continue
    # MID: строки титров, найденные внутри (после первой прозы) — удалить до следующей найденной прозы
    cred_in = []
    for k, kd, t, q in pos:
        if kd != 'cred' or q is None or q <= first_q: continue
        m = TITLE_CRED.match(t)
        if m:  # титул сюжета + титры на одной строке: удалять после титула
            tn2, _ = nmap(t[m.end(1):]); q2 = an.find(tn2[:25], q)
            if q2 < 0: continue
            q = q2
        cred_in.append((k, q, t))
    for k, q, t in sorted(cred_in, key=lambda z: z[1]):
        nxt = [qq for kk, qq in prose_found if qq > q]
        if not nxt: manual.append((c, f'титры внутри без последующей прозы: @{k} {t[:60]!r}')); continue
        ops.append(('mid', idx[q], idx[min(nxt)], a[idx[q]:idx[min(nxt)]]))
    # SOFT-лид: музыкальные/исполнительские/дубляжные примечания в начале (вне концертных жанров) — срез до первой печатной прозы без таких примечаний
    tmp = a
    for kind, s0, s1, txt in sorted(ops, key=lambda z: -z[1]): pass
    concert = bool(x and x['concert'])
    if not concert:
        lead_end = max([s1 for kind, s0, s1, txt in ops if kind == 'lead'] + [0])
        rest = a[lead_end:]
        if SOFT.match(rest.lstrip()):
            cands = [q for k, kd, t, q in pos if kd == 'prose' and q is not None and idx[q] > lead_end and not SOFT.match(t) and not credline(t) and not M.search(t[:40])]
            if cands:
                q = min(cands)
                ops = [o for o in ops if not (o[0] == 'mid' and o[1] < idx[q])]  # MID внутри срезаемого лида не нужны
                ops.append(('lead', 0, idx[q], a[:idx[q]]))
            else:
                manual.append((c, f'soft-лид без последующей прозы: {rest[:60]!r}'))
    if not ops: 
        manual.append((c, 'маркер в прозе (ложный) или титры не сопоставлены')); continue
    # слить пересекающиеся интервалы, применить справа налево
    spans = sorted([(s0, s1) for kind, s0, s1, txt in ops])
    merged = []
    for s0, s1 in spans:
        if merged and s0 <= merged[-1][1]: merged[-1] = (merged[-1][0], max(merged[-1][1], s1))
        else: merged.append((s0, s1))
    for s0, s1 in sorted(merged, key=lambda z: -z[0]):
        new = new[:s0] + new[s1:]
    new = re.sub(r'\s+', ' ', new).strip()
    props.append({'cat': c, 'title': cat[c]['title'], 'vol': v, 'before': a, 'after': new, 'ops': [(o[0], o[3][:120]) for o in ops],
                  'lines': [k for k, kd, t, q in pos if kd == 'prose' and q is not None][:3] + [k for k, q, t in cred_in]})
json.dump(props, open('work/f6_p2_passb.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(manual, open('work/f6_p2_passb_manual.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('proposals:', len(props), 'manual:', len(manual))
with open('work/f6_p2_passb_review.txt', 'w', encoding='utf-8') as f:
    for p in props:
        f.write(f"\n=== cat{p['cat']} «{p['title']}» {p['vol']} lines {p['lines']}\n")
        for o in p['ops']: f.write(f"  {o[0].upper()}: {o[1]!r}\n")
        f.write(f"  AFTER[:160]: {p['after'][:160]!r}\n")
    f.write('\n\n==== MANUAL\n')
    for m in manual: f.write(f'{m}\n')
