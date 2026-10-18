# -*- coding: utf-8 -*-
"""П4 a2 v2 — хвостовые срезы: библиография, призовые, колофоны, рубрикаторы,
обрывки следующих голов (титульная сверка с каталогом), OCR-мусор."""
import json, re, difflib
from collections import Counter

cat = json.load(open('state/catalog_f5_a1.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
A1 = {388,464,470,2024,2525,2739,3318,5244,5890,6966,3554,1186,
      1184,4767,5456,5468,5606,5645,5894,6334,6335,6546,7230,7231}

LAT2CYR = str.maketrans('ABCEHKMOPTXYaceopxy0°', 'АВСЕНКМОРТХУасеорху ОО'.replace(' ', ''))
def norm_map(s):
    """нормализованная строка + карта norm-idx -> исходный idx"""
    out, idx = [], []
    for i, ch in enumerate(s):
        c = ch.upper()
        c = {'0': 'О', '°': 'О', 'Ё': 'Е', 'Й': 'И', '4': 'Ч', '3': 'З'}.get(c, c)
        c = c.translate(str.maketrans('ABCEHKMOPTXY', 'АВСЕНКМОРТХУ'))
        if 'А' <= c <= 'Я' or c == 'З':
            out.append(c); idx.append(i)
    return ''.join(out), idx

def norm_plain(s):
    return norm_map(s)[0]

AWARD_NOUN = re.compile(r'(приз|преми|диплом|медал|награ|удостоен|присужд|отмечен|Гран-при|Гоан-при|ФИПРЕССИ|жюри|лучш)', re.I)
PRIZE_ANCHORS = [
 re.compile(r'(?:На|В)\s+[IVXХ\d]*\s*[^.]{0,90}?(?:кинофестивал|фестивал|киносмотр|смотре-конкурс|смотре|конкурс)'),
 re.compile(r'Фильму?\s+(?:удостоен|присужден|награжден|отмечен)'),
 re.compile(r'(?:Высшая|Первая|Вторая|Третья|Главная|Специальная|Золотая|Серебряная|Бронзовая|Большая|Почетная|Поощрительная)\s+(?:премия|приз|награда|медаль)', re.I),
 re.compile(r'(?:Главный|Специальный|Первый|Второй|Третий|Большой|Золотой|Серебряный|Бронзовый|Почетный|Поощрительный)\s+(?:приз|диплом)', re.I),
 re.compile(r'Приз(?:ы)?[\s,]'), re.compile(r'Диплом(?:ы)?[\s,]'),
 re.compile(r'Преми[яи]\s'), re.compile(r'(?:Государственная|Ленинская)\s+преми'),
 re.compile(r'Гран-при|Гоан-при'), re.compile(r'Признан\w*\s+лучш', re.I),
]
SENT_BOUND = re.compile(r'[.!?…»)]\s+$|^\s*$')
PRIZE_EXT = re.compile(r'^(?:[-—–]\s*|На\s|В\s+[IVXХ\d]|Приз|Диплом|Преми|Гран-при|Гоан-при|Государственная\s|Ленинская\s|Специальн|Главн|Перв|Втор|Треть|Высш|Золот|Серебрян|Бронзов|Почетн|Поощрительн|Фильму?\s+(?:удостоен|присужден|награжден|отмечен)|Признан)', re.I)
COLOPHON = [re.compile(p) for p in (
 r'Сведения о наличии неточностей', r'Белые Столбы,?\s*Госфильмофонд',
 r'Заказ\s*[№Л«»\s]', r'Подп\.\s*в\s*печ', r'Форм\.\s*бум', r'Тираж\s+\d')]
RUBRIC_WORD = re.compile(r'(ФИЛЬМЫ|КИНОЖУРНАЛ|МУЛЬТИПЛИКАЦИОН|ИГРОВЫЕ|ПРИЛОЖЕНИ|УКАЗАТЕЛ|ХРОНИКАЛЬН|КИНОКАРТИН|КАТАЛОГ)')
HARD_JUNK = set('<>■❖^~|\\/@#$%&=+{}[]®©°†‡•*')
STUB = re.compile(r'(Фильм не сохранился|Содержание не установлено|Авторы и содержание не установлены)')

def strip_junk(rem, aggressive=False):
    cut = ''
    while True:
        m = re.search(r'(\s)([^\s]+)$', ' ' + rem)
        if not m: break
        tok = m.group(2)
        hard = any(ch in HARD_JUNK for ch in tok)
        noletters = not re.search(r'[А-ЯЁа-яёA-Za-z0-9]', tok)
        latfrag = (not re.search(r'[А-ЯЁа-яё]', tok)) and len(tok) <= 4 and not tok.rstrip('.').isdigit() and not tok[:1].isdigit()
        tiny = aggressive and len(tok) <= 2 and cut and not tok.endswith(('.', '!', '?', '»', ')'))
        if hard or noletters or (latfrag and (cut or aggressive)) or tiny:
            rem = rem[:len(rem)-len(tok)].rstrip()
            cut = tok + ((' ' + cut) if cut else '')
        else:
            break
    return rem, cut

def head_overlap(rem, i):
    """обрывок головы следующей статьи: fuzzy-сверка суффикса rem с префиксом титула cat[i+1]/[i+2]."""
    tailz = rem[-140:]
    if not (any(ch in HARD_JUNK for ch in tailz[-70:])
            or not re.search(r'[.!?…»)]\s*$', rem)
            or re.search(r'[А-ЯЁ]{3,}\s*$', rem)):
        return None
    nz, idxs = norm_map(tailz)
    if len(nz) < 6: return None
    best = None
    for j in (1, 2):
        if i + j >= len(cat): break
        tt = cat[i+j]['title']
        if not tt or len(tt) < 4: continue
        nt = norm_plain(tt)
        if len(nt) < 5: continue
        for L in range(min(len(nz), len(nt), 60), 4, -1):
            suf = nz[-L:]
            pref = nt[:L]
            sm = difflib.SequenceMatcher(None, suf, pref)
            if sm.quick_ratio() < 0.75: continue
            r = sm.ratio()
            need = 0.8 if L >= 8 else 0.93
            if r >= need:
                st = len(nz) - L
                orig = idxs[st] + (len(rem) - len(tailz))
                if best is None or orig < best[0]:
                    best = (orig, cat[i+j]['title'], L, round(r, 2))
                break
    return best

res, points, doubts, log, obs = {}, [], [], [], []
for i, r in enumerate(cat):
    if i in strays or i in A1: continue
    t = r.get('annotation')
    if not t: continue
    classes = []
    tail_start = len(t)
    # 1) колофон
    col = None
    for pat in COLOPHON:
        m = pat.search(t)
        if m and m.start() > 40:
            col = m.start() if col is None else min(col, m.start())
    if col is not None:
        # начало предложения колофона
        k = max(t.rfind('. ', 0, col), t.rfind('» ', 0, col))
        start = k + 2 if k > 40 else col
        tail_start = start; classes.append('колофон')
    # 2) библиография
    bidx = None
    for mark in ('Библиография', 'БИБЛИОГРАФИЯ', 'библиография'):
        j = t.find(mark)
        if j != -1: bidx = j if bidx is None else min(bidx, j)
    if bidx is None:
        m = re.search(r'Библиограф\w{0,2}$', t.rstrip())
        if m: bidx = m.start()
    if bidx is not None and bidx < tail_start:
        pre = t[:bidx].strip()
        if len(pre) < 15:
            points.append((i, 'bib_early', t[:200])); continue
        tail_start = bidx
        if 'колофон' not in classes or bidx < tail_start: classes = [c for c in classes if c != 'колофон'] + (['колофон'] if col is not None and col > bidx else []) + ['библиография']
    # 3) призовой блок
    zone = t[:tail_start]
    best = None
    for pat in PRIZE_ANCHORS:
        for m in pat.finditer(zone):
            j = m.start()
            if j < 40: continue
            if not SENT_BOUND.search(zone[max(0,j-8):j]): continue
            if not AWARD_NOUN.search(zone[j:j+180]): continue
            if best is None or j < best: best = j
    if best is not None:
        block = zone[best:]
        gaps_ok = all(AWARD_NOUN.search(block[k:k+320]) for k in range(0, max(1, len(block)-160), 300))
        if not gaps_ok:
            doubts.append((i, 'prize_gap', zone[max(0,best-80):best+120]))
        else:
            # расширение назад по призовым предложениям
            cur = best
            for _ in range(12):
                k = max(zone.rfind('. ', 0, cur), zone.rfind('» ', 0, cur), zone.rfind(') ', 0, cur))
                if k <= 40: break
                sent = zone[k+2:cur]
                if len(sent) > 400: break
                if PRIZE_EXT.match(sent.strip()) and AWARD_NOUN.search(sent):
                    cur = k + 2
                else:
                    break
            tail_start = cur; classes.insert(0, 'призовой')
    # 4) остаток: мусор, рубрикатор, обрывок головы (титульная сверка)
    rem = t[:tail_start].rstrip()
    junk_total, caps_cut, headfrag = '', '', None
    def rubric_take(rm):
        toks = rm.split(); k = len(toks); caps = 0
        while k > 0:
            tok = toks[k-1]
            core = re.sub(r'[«»()\d.,:;\-—–№!?]', '', tok)
            if not core: k -= 1; continue
            if re.fullmatch(r'[А-ЯЁ]{3,}', core) or re.fullmatch(r'\d{4}', tok.strip('.,')):
                caps += 1; k -= 1; continue
            break
        if caps < 2: return rm, ''
        run = ' '.join(toks[k:])
        if len(run) < 10 or not RUBRIC_WORD.search(run): return rm, ''
        pos = rm.rfind(run)
        return rm[:pos].rstrip(), run
    for _ in range(4):
        changed = False
        rem2, jc = strip_junk(rem)
        if jc: junk_total = jc + ((' ' + junk_total) if junk_total else ''); rem = rem2; changed = True
        rem2, rc = rubric_take(rem)
        if rc:
            caps_cut = rc + ((' ' + caps_cut) if caps_cut else '')
            rem = rem2; changed = True
        if not changed: break
    ho = head_overlap(rem, i)
    if ho:
        orig_idx, ttl, ln, ratio = ho
        frag = rem[orig_idx:]
        rem3 = rem[:orig_idx].rstrip()
        rem3, jc2 = strip_junk(rem3, aggressive=True)
        if jc2: junk_total = jc2 + ((' ' + junk_total) if junk_total else '')
        headfrag = (frag, ttl, ln, ratio)
        rem = rem3
        rem2, jc3 = strip_junk(rem)
        if jc3: junk_total = jc3 + ' ' + junk_total; rem = rem2
    if junk_total: classes.append('мусор')
    if caps_cut: classes.append('рубрикатор')
    if headfrag: classes.append('обрывок-головы')
    if len(rem) >= len(t): continue
    if len(rem.strip()) < 15 or (len(rem.strip()) < 40 and not STUB.search(rem)):
        points.append((i, 'короткий-остаток [' + '+'.join(classes) + ']', t[:220])); continue
    tail = t[len(rem):]
    entry = {'lead': None, 'tail': tail, 'class': '+'.join(classes)}
    if headfrag: entry['head_match'] = {'next_title': headfrag[1], 'olen': headfrag[2], 'ratio': headfrag[3]}
    res[str(i)] = entry
    endch = rem.strip()[-1]
    flag = '' if re.search(r'[.!?…»)]$', rem.strip()) else 'НЕТ-ТЧК'
    if rem.strip().endswith('-'): obs.append((i, 'остаток-обрыв-дефис', rem.strip()[-60:]))
    log.append((i, '+'.join(classes), flag, rem.strip()[-70:], tail[:90]))

json.dump({'cut': res, 'restore': {}, 'none': {}, 'confirm': {}, 'notfound': {}},
          open('work/a2_res_draft2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = open('work/a2_review2.txt', 'w', encoding='utf-8')
cc = Counter(v['class'] for v in res.values())
print('=== КЛАССЫ ===', file=out)
for k, v in cc.most_common(): print(f'{v:5d}  {k}', file=out)
print(f'\nИТОГО срезов: {len(res)}; точечных: {len(points)}; сомнительных: {len(doubts)}; обрыв-дефис: {len(obs)}', file=out)
print('\n=== ТОЧЕЧНЫЕ ===', file=out)
for i, k, ctx in points: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== СОМНИТЕЛЬНЫЕ ===', file=out)
for i, k, ctx in doubts: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== ОБРЫВ-ДЕФИС (наблюдения) ===', file=out)
for i, k, ctx in obs: print(f'cat{i}: …{ctx!r}', file=out)
print('\n=== ВСЕ ОБРЫВКИ-ГОЛОВ ===', file=out)
for i, k, fl, remend, ts in log:
    if 'обрывок-головы' in k:
        hm = res[str(i)].get('head_match', {})
        print(f'cat{i} [{k}]{fl} match={hm.get("next_title","")!r} r={hm.get("ratio")}: …{remend} ||| {ts!r}', file=out)
print('\n=== ВСЕ РУБРИКАТОРЫ/КОЛОФОНЫ ===', file=out)
for i, k, fl, remend, ts in log:
    if ('рубрикатор' in k or 'колофон' in k):
        print(f'cat{i} [{k}]{fl}: …{remend} ||| {ts!r}', file=out)
print('\n=== ВСЕ ПРИЗОВЫЕ ===', file=out)
for i, k, fl, remend, ts in log:
    if 'призовой' in k: print(f'cat{i} [{k}]{fl}: …{remend} ||| {ts}', file=out)
print('\n=== ВСЕ ЧИСТО-МУСОРНЫЕ ===', file=out)
for i, k, fl, remend, ts in log:
    if k == 'мусор': print(f'cat{i}{fl}: …{remend} ||| {ts!r}', file=out)
import random
random.seed(3)
bibs = [x for x in log if 'библиография' in x[1]]
print(f'\n=== БИБЛИОГРАФИЧЕСКИЕ: всего {len(bibs)}, выборка 50 ===', file=out)
for i, k, fl, remend, ts in random.sample(bibs, min(50, len(bibs))):
    print(f'cat{i} [{k}]{fl}: …{remend} ||| {ts}', file=out)
nop = [x for x in log if x[2] == 'НЕТ-ТЧК' and 'библиография' in x[1] and x[1] != 'библиография']
out.close()
print('cuts:', len(res), 'points:', len(points), 'doubts:', len(doubts))
