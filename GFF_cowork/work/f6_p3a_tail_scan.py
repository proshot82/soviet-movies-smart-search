# -*- coding: utf-8 -*-
"""Ф6-П3: сплошной проход «конец аннотации ↔ конец печатной прозы» по текущему каталогу (П2е).
Для каждой аннотации: локализация статьи (work/f6_p2_ann_loc.json → ann_line; резерв — work/f6_p2_articles.json),
поиск печатной строки, содержащей конец аннотации (суффикс-пробы 30/22/16/12 норм. знаков), затем:
 - остаток той же строки после конца аннотации (MID-*: проза = обрыв внутри строки; мусор/титры/голова — законный срез);
 - следующие печатные строки до стоп-условия (верифицированная голова / титры / библиография / призы / указатель):
   проза → CONT-LOWER (строчная — продолжение с разрыва страницы) / CONT-UPPER (новый абзац);
 - конечная пунктуация печати за последним знаком прозы (END-PUNCT: в каталоге её нет, в печати есть).
Выход: work/f6_p3a_tail_scan.json, work/f6_p3a_tail_review.txt."""
import sys, json, re
sys.path.insert(0, 'work')
import f6_p2_lib as L
from collections import Counter
cat = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
loc = json.load(open('work/f6_p2_ann_loc.json', encoding='utf-8'))
arts = json.load(open('work/f6_p2_articles.json', encoding='utf-8'))
BC = 1628   # Ф6-П3а: вставка «Старый наездник» — ann_loc/articles индексированы по нумерации v1
def old_of(i): return None if i == BC else (i if i < BC else i - 1)
CONCERT = re.compile(r'(концерт|Концерт|опера|Опера|балет|Балет|ревю|Ревю|Музыкальн|музыкальн|Фильм-спектакль|спектакль|Оперетта|оперетта|Эстрадн|эстрадн|цирк|Цирк)')
JUNKLINE = re.compile(r'^\s*(\d{1,4}\*?\s*|[^А-ЯЁа-яё]{0,4}\d*\s?Заказ.*|\d*\s?Сов\. худ\. фильмы.*|Зак[.,]\s?№.*|[^А-ЯЁа-яё0-9]*)$')
PUNCT_OK = '.!?…»)"\''
def nmap(s):
    out = []; idx = []
    for k, ch in enumerate(s.lower().replace('ё', 'е').translate(L._TR)):
        if ('а' <= ch <= 'я') or ('a' <= ch <= 'z') or ('0' <= ch <= '9'): out.append(ch); idx.append(k)
    return ''.join(out), idx
def verified_head(vol, k, hs, Ls):
    if k not in hs: return False
    t = Ls[k][1]
    if re.search(r'\d+\s?ч[.,]|мтр\. неизв|\d+ м[,.]', t[:200]): return True
    for k2 in range(k + 1, min(k + 4, len(Ls))):
        if re.match(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав[тг]|Авт|Реж|Сцен|Автор|Пост\.|Опер)', Ls[k2][1]): return True
    return False
PRIZE2 = re.compile(r'^(?:[^А-ЯЁа-яё0-9]{0,6})(Сценари[йю] (фильма|картины)?\s?(получил|удостоен|отмечен|награжд|присужд)|Личная награда|Высшая преми|Большая преми|Памятная преми|(Актрис[ае]|Актер[ау]|Режиссер[ау]|Оператор[ау]|Художник[ау]|Композитор[ау]|Исполнител[юя])\b[^\n]{0,80}(приз|преми|диплом|награ)|Фильму (на|па) |На \S{1,6} (Всесоюзн|Международн|Всемирн|Московск|Республиканск|кинофестивал|фестивал|смотре|конкурсе)|Новелле «|Специальн|Первый приз|Второй приз|Третий приз|Первая преми|Вторая преми|Третья преми|Признан|Гран-при|Гоан-при|Гран-пр|Главн(ый|ая) (приз|преми|специальн)|Диплом|Приз[ыа]? |Приз\b|Преми[яи]|Почетн|Поощрительн|Лауреат|Золот|Серебрян|Бронзов|Большой приз|Кубок|Медаль|Ha [IVX]|На \*?[IVX1Х]+|На (перв|втор|треть|четверт|пят|шест|седьм|восьм|девят|десят|Всесоюзн|Международн|Всемирн|Московск|Республиканск|Ленинградск|Всероссийск|кинофестивал|фестивал|смотре|конкурсе|[А-Я][а-я]+ (Всесоюзн|Международн|кинофестивал|фестивал|смотр))|Фильм(у)? (удостоен|присужден|награжд|отмечен|получил|был удостоен|признан)|Картин(а|е) (удостоен|присужден|награжд|отмечен|получил|признан)|Отмечен|Удостоен|Награжден|В \d{4} г(оду|\.) (фильм|картин|на [IVX\dА-Я]|в ежегодном|Государственн|Ленинск|за )|В картине также использованы)', re.I)
def is_junk(t):
    if (not t.strip()) or JUNKLINE.match(t) is not None: return True
    words = re.findall(r'[А-ЯЁа-яё]{2,}', t)
    if not words: return True                       # орнаменты «О < <>», «fl fl», «Ъ Ъ», «^ ^»
    if len(''.join(words)) < 4 and len(t) < 40: return True
    return False
def is_headlike(t):
    s = t.lstrip()
    if re.match(r'^\d{1,4}\s?[аa]?\.\s*[А-ЯЁ«]', s): return True                 # «1191 а. …», «2031а. СЧАСТЬЕ»
    if re.match(r'^(УКАЗАТЕЛЬ|АЛФАВИТНЫЙ|ПРИЛОЖЕНИЕ|СОДЕРЖАНИЕ|ОГЛАВЛЕНИЕ|Стр\. \d{4}|Здесь и в других случаях|Сведения о наличии)', s): return True
    if re.search(r'(фитиль|ералаш|кино-крокодил)\s?№', s[:60], re.I): return True
    if (re.search(r'\d+\s?ч[.,„]', s[:160]) and re.search(r'\d{4}\s?г|\d+[,.]?\d*\s?м\b|цв\.|ш\.-э|ш\.-ф|Драма|Комедия|Киноповесть|Кинокомедия|Мелодрама|Киноочерк|Фантастич|Психологич|Психологии|Истори|Детектив|Приключ|Экраниз|Сказка|Мультипл|Кукольн|Рисован|Киноновелл|Киноальманах|Трагед|Кинороман|Кинопоэма|Опера|Балет|Концерт|Хроник', s[:220])) or re.search(r'мтр\. неизв', s[:160]): return True
    letters = re.sub(r'[^А-ЯЁа-яё]', '', s)[:10]
    if len(letters) >= 5 and letters == letters.upper(): return True            # первые 10 букв прописные — голова (в т.ч. с орнаментом-мусором)
    if len([w for w in re.findall(r'[А-ЯЁ]{3,}', s[:80]) if w == w.upper()]) >= 2 and not re.match(r'^[А-ЯЁ][а-яё]', s): return True
    if re.match(r'^(Всесоюзного сатирического киножурнала|Детского юмористического)', s): return True
    return False
res = []
for i, r in enumerate(cat):
    a = r['annotation']
    if not a: continue
    vol = r['source'].split('_')[0]; Ls = L.lines(vol); hs = L.headset(vol)
    concert = bool(CONCERT.search(r['genre'] or ''))
    x = loc.get(str(old_of(i))); art = arts.get(str(old_of(i)))
    rec = {'cat': i, 'vol': vol, 'title': r['title'], 'year': r['year']}
    if x and x.get('ann_line') is not None:
        j = x['ann_line']; h = j
        while h > 0 and h not in hs: h -= 1
        e = j + 1
        while e < len(Ls) and e not in hs: e += 1
        rec['loc'] = 'ann_line'
    elif art:
        h, e = art['h'], art['e']; rec['loc'] = 'title'
    else:
        rec['class'] = 'UNLOCATED'; res.append(rec); continue
    rec.update({'h': h, 'e': e})
    A_n, A_idx = nmap(a)
    LN = {}
    hi = min(len(Ls), e + 80)
    for k in range(h, hi): LN[k] = nmap(Ls[k][1])
    # поиск строки с концом аннотации
    hit = None
    for plen in (30, 22, 16, 12):
        pr = A_n[-plen:]
        if len(pr) < min(plen, 8): continue
        cands = [k for k in range(h, e) if pr in LN[k][0]]
        if not cands: cands = [k for k in range(e, hi) if pr in LN[k][0]]
        if cands:
            k = cands[-1] if cands[-1] < e else cands[0]
            p = LN[k][0].rfind(pr) + len(pr)
            hit = (k, p, plen); break
    if hit is None:
        rec['class'] = 'NOMATCH'; res.append(rec); continue
    k_last, p_end, plen = hit
    rec.update({'last_line': k_last, 'probe': plen, 'in_article': h <= k_last < e})
    ln, lidx = LN[k_last]
    text = Ls[k_last][1]
    raw_after = text[lidx[p_end - 1] + 1:] if p_end > 0 else text
    rest_n = ln[p_end:]
    rec['raw_after'] = raw_after[:120]
    cls = []
    cont = []       # строки-продолжения (k, text)
    stop = None
    mid = None
    if rest_n:
        ra = raw_after.strip()
        if re.match(r'^[^А-ЯЁа-яё]*$', ra): mid = 'MID-JUNK'
        elif re.match(r'^[^А-ЯЁа-яё]{0,8}[А-ЯЁ][А-ЯЁ0-9\s\-—,!?«»:;()№.’]{3,}', ra) and not re.match(r'^[^А-ЯЁа-яё]{0,8}[А-ЯЁ][а-яё]', ra): mid = 'MID-HEAD'
        elif L.kind(re.sub(r'^[^А-ЯЁа-яё]+', '', ra), concert) in ('cred', 'bib', 'prize'): mid = 'MID-' + L.kind(re.sub(r'^[^А-ЯЁа-яё]+', '', ra), concert).upper()
        elif re.match(r'^[^А-ЯЁа-яё]{0,6}(Фильм дублирован|Фильм озвучен|Библиограф|ВЭ |РУ |Приз|На [IVX])', ra): mid = 'MID-CRED'
        else: mid = 'MID-PROSE'; rec['mid_text'] = ra
        cls.append(mid)
    # конечная пунктуация печати
    m_p = re.match(r'[.!?…»)"\'’\s]*', raw_after)
    print_punct = ''.join(ch for ch in m_p.group(0) if ch in PUNCT_OK) if not rest_n or mid != 'MID-PROSE' else ''
    cat_tail = re.search(r'[^А-ЯЁа-яё0-9A-Za-z]*$', a).group(0)
    rec['print_punct'] = print_punct; rec['cat_tail'] = cat_tail
    if not re.search(r'[.!?…]', cat_tail) and re.search(r'[.!?…]', print_punct) and (not rest_n or mid in ('MID-JUNK', 'MID-HEAD', 'MID-CRED', 'MID-BIB', 'MID-PRIZE')):
        if print_punct.startswith(cat_tail.strip()) or not cat_tail.strip():
            cls.append('END-PUNCT'); rec['add_punct'] = print_punct[len(cat_tail.strip()):] if cat_tail.strip() and print_punct.startswith(cat_tail.strip()) else print_punct
        else:
            cls.append('END-PUNCT?')
    # продолжение на следующих строках (только если остаток строки не проза/титры/голова)
    if mid in (None, 'MID-JUNK'):
        k = k_last + 1
        while k < hi and len(cont) < 8:
            t = Ls[k][1]
            if is_junk(t): k += 1; continue
            if L.IDX.search(t): stop = ('idx', k); break
            if verified_head(vol, k, hs, Ls) or is_headlike(t): stop = ('head', k); break
            kd = L.kind(t, concert)
            if kd == 'prose' and PRIZE2.match(t): kd = 'prize'
            if kd in ('cred', 'bib', 'prize'): stop = (kd, k); break
            if kd == 'junk': k += 1; continue
            tn = nmap(t)[0]
            if len(tn) >= 8 and tn in A_n: stop = ('dup', k); k += 1; continue
            cont.append((k, t)); k += 1
        if cont:
            first = cont[0][1].lstrip()
            cls.append('CONT-LOWER' if re.match(r'^[^А-ЯЁа-яё0-9]{0,3}[а-яё]', first) else 'CONT-UPPER')
            rec['cont'] = [(k, t) for k, t in cont]
        rec['stop'] = stop
    if not cls: cls.append('END-OK' if re.search(r'[.!?…]', cat_tail) else ('END-NOPUNCT' if not print_punct else 'END-CLOSE'))
    rec['class'] = '+'.join(cls)
    res.append(rec)
cnt = Counter(x['class'] for x in res)
print(len(res), dict(cnt.most_common()))
json.dump(res, open('work/f6_p3a_tail_scan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
with open('work/f6_p3a_tail_review.txt', 'w', encoding='utf-8') as f:
    for x in res:
        if 'CONT' in x['class'] or 'MID-PROSE' in x['class'] or x['class'] in ('NOMATCH', 'UNLOCATED') or 'END-PUNCT?' in x['class']:
            f.write(f"\n### cat{x['cat']} {x['vol']} «{x['title']}» {x['year']} [{x['class']}] h={x.get('h')} e={x.get('e')} last={x.get('last_line')} stop={x.get('stop')}\n")
            f.write('  ANN-END: ' + repr(cat[x['cat']]['annotation'][-160:]) + '\n')
            if 'raw_after' in x: f.write('  RAW-AFTER: ' + repr(x['raw_after']) + '\n')
            if 'mid_text' in x: f.write('  MID: ' + repr(x['mid_text'][:300]) + '\n')
            for k, t in x.get('cont', []): f.write(f'  @{k}: {t[:400]}\n')
