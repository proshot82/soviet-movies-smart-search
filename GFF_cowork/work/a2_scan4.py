# -*- coding: utf-8 -*-
"""П4 a2 v3 — финальный детект хвостов. Авто-классы: библиография, призовой,
рубрикатор, обрывок-головы (титульная сверка + уточнение границы), мусор.
Колофоны/указатели/срединные вставки — только в ручной список."""
import json, re, difflib
from collections import Counter

cat = json.load(open('state/catalog_f5_a1.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
A1 = {388,464,470,2024,2525,2739,3318,5244,5890,6966,3554,1186,
      1184,4767,5456,5468,5606,5645,5894,6334,6335,6546,7230,7231}

def norm_map(s):
    out, idx = [], []
    for i, ch in enumerate(s):
        c = ch.upper()
        c = {'0': 'О', '°': 'О', 'Ё': 'Е', 'Й': 'И', '4': 'Ч', '3': 'З'}.get(c, c)
        c = c.translate(str.maketrans('ABCEHKMOPTXY', 'АВСЕНКМОРТХУ'))
        if 'А' <= c <= 'Я' or c == 'З':
            out.append(c); idx.append(i)
    return ''.join(out), idx
def norm_plain(s): return norm_map(s)[0]

AWARD_NOUN = re.compile(r'(приз|преми|диплом|медал|награ|удостоен|присужд|отмечен|Гран-при|Гоан-при|ФИПРЕССИ|жюри|лучш)', re.I)
PRIZE_ANCHORS = [
 re.compile(r'(?:На|В)\s+[IVXХ\d]*\s*[^.]{0,90}?(?:кинофестивал|фестивал|киносмотр|смотре-конкурс|смотре|конкурс)'),
 re.compile(r'(?:Фильму?|Картина|Лента)\s+(?:удостоен|присужден|награжден|отмечен)'),
 re.compile(r'(?:Высшая|Первая|Вторая|Третья|Главная|Специальная|Золотая|Серебряная|Бронзовая|Большая|Почетная|Поощрительная)\s+(?:премия|приз|награда|медаль)', re.I),
 re.compile(r'(?:Главный|Специальный|Первый|Второй|Третий|Большой|Золотой|Серебряный|Бронзовый|Почетный|Поощрительный)\s+(?:приз|диплом)', re.I),
 re.compile(r'Приз(?:ы)?[\s,]'), re.compile(r'Диплом(?:ы)?[\s,]'),
 re.compile(r'Преми[яи]\s'), re.compile(r'(?:Государственная|Ленинская)\s+преми'),
 re.compile(r'Гран-при|Гоан-при'), re.compile(r'Признан\w*\s+лучш', re.I),
]
SENT_BOUND = re.compile(r'[.!?…»)]\s+$|^\s*$')
PRIZE_EXT = re.compile(r'^(?:[-—–]\s*|На\s|В\s+[IVXХ\d]|Приз|Диплом|Преми|Гран-при|Гоан-при|Государственная\s|Ленинская\s|Специальн|Главн|Перв|Втор|Треть|Высш|Золот|Серебрян|Бронзов|Почетн|Поощрительн|(?:Фильму?|Картина|Лента)\s+(?:удостоен|присужден|награжден|отмечен)|Признан)', re.I)
COLOPHON = re.compile(r'(Сведения о наличии неточностей|Белые Столбы|\d\s+Заказ\s|Заказ\s*№|Подп\.\s*в\s*печ|Форм\.\s*бум|Тираж\s+\d)')
INDEX_PAT = re.compile(r'—\s*\d{3,4}(?:\D|$)')
RUBRIC_WORD = re.compile(r'(ФИЛЬМЫ|КИНОЖУРНАЛ|МУЛЬТИПЛИКАЦИОН|ИГРОВЫЕ|ПРИЛОЖЕНИ|УКАЗАТЕЛ|ХРОНИКАЛЬН|КИНОКАРТИН|КАТАЛОГ)')
HARD_JUNK = set('<>■❖^~|\\/@#$%&=+{}[]®©°†‡•*’‘”„')
STUB = re.compile(r'(Фильм не сохранился|Содержание не установлено|Авторы и содержание не установлены)')

def strip_junk(rem, aggressive=False):
    cut = ''
    while True:
        m = re.search(r'(\s)([^\s]+)$', ' ' + rem)
        if not m: break
        tok = m.group(2)
        # слово с прилипшим мусором: снять только мусорный хвост токена
        wm = re.match(r'^([А-ЯЁа-яё]{4,}[.!?…»)]?)([' + re.escape(''.join(HARD_JUNK)) + r']+)$', tok)
        if wm:
            rem = rem[:len(rem)-len(wm.group(2))]
            cut = wm.group(2) + ((' ' + cut) if cut else '')
            continue
        hard = any(ch in HARD_JUNK for ch in tok)
        cyr = len(re.findall(r'[А-ЯЁа-яё]', tok))
        noletters = not re.search(r'[А-ЯЁа-яёA-Za-z0-9]', tok)
        latfrag = (not re.search(r'[А-ЯЁа-яё]', tok)) and len(tok) <= 4 and not tok.rstrip('.').isdigit() and not tok[:1].isdigit()
        single = aggressive and len(tok) == 1
        digits = aggressive and cut and re.fullmatch(r'\d{1,5}', tok)
        if (hard and cyr <= 2) or noletters or (latfrag and (cut or aggressive)) or single or digits:
            rem = rem[:len(rem)-len(tok)].rstrip()
            cut = tok + ((' ' + cut) if cut else '')
        else:
            break
    return rem, cut

def head_overlap(rem, i):
    tailz = rem[-140:]
    if not (any(ch in HARD_JUNK for ch in tailz[-70:])
            or not re.search(r'[.!?…»)]\s*$', rem)
            or re.search(r'[А-ЯЁ]{3,}[\s.,!?»)-]*$', rem)):
        return None
    nz, idxs = norm_map(tailz)
    if len(nz) < 6: return None
    for j in (1, 2):
        if i + j >= len(cat): break
        tt = cat[i+j]['title']
        if not tt or len(tt) < 4: continue
        nt = norm_plain(tt)
        if len(nt) < 5: continue
        for L in range(min(len(nz), len(nt), 60), 4, -1):
            suf = nz[-L:]; pref = nt[:L]
            sm = difflib.SequenceMatcher(None, suf, pref)
            if sm.quick_ratio() < 0.75: continue
            r = sm.ratio()
            need = 0.8 if L >= 8 else 0.93
            if r >= need:
                st = len(nz) - L
                orig = idxs[st] + (len(rem) - len(tailz))
                # уточнение границы: последняя точка-конец предложения, после которой
                # остаток по-прежнему матчится с титулом
                zone_start = max(0, orig - 30)
                best_cut = None
                for pm in re.finditer(r'[.!?…]\s+|»\)?\s+|\)\s+', rem[zone_start:]):
                    cand = zone_start + pm.end()
                    rest = rem[cand:]
                    nrest = norm_plain(rest)
                    if len(nrest) < 5: continue
                    Lr = min(len(nrest), len(nt), 60)
                    rr = difflib.SequenceMatcher(None, nrest[:Lr], nt[:Lr]).ratio()
                    if rr >= (0.8 if Lr >= 8 else 0.93):
                        if best_cut is None or cand > best_cut: best_cut = cand
                if best_cut is not None:
                    orig = best_cut
                else:
                    # расширить до границы токена
                    sp = rem.rfind(' ', 0, orig)
                    boundary_ok = orig == 0 or rem[orig-1] in ' «'
                    if not boundary_ok and sp != -1: orig = sp + 1
                return (orig, cat[i+j]['title'], L, round(r, 2))
    return None

res, points, doubts, log, obs = {}, [], [], [], []
for i, r in enumerate(cat):
    if i in strays or i in A1: continue
    t = r.get('annotation')
    if not t: continue
    # ручные кандидаты: колофоны и указатели
    reason = None
    if COLOPHON.search(t): reason = 'колофон'
    elif len(INDEX_PAT.findall(t[-600:])) >= 4 and 'БИБЛИОГРАФ' not in t: reason = 'указатель'
    if reason:
        points.append((i, reason, None)); continue
    classes = []
    tail_start = len(t)
    # библиография
    bidx = None
    for mark in ('Библиография', 'БИБЛИОГРАФИЯ'):
        j = t.find(mark)
        if j != -1: bidx = j if bidx is None else min(bidx, j)
    if bidx is None:
        j = t.find('библиография')
        if j != -1 and (j > len(t)*0.4 or any(ch in HARD_JUNK for ch in t[max(0,j-4):j])):
            bidx = j
            while bidx > 0 and t[bidx-1] in HARD_JUNK: bidx -= 1
    if bidx is None:
        m = re.search(r'Библиограф\w{0,2}\s*$', t.rstrip())
        if m: bidx = m.start()
    if bidx is not None:
        pre = t[:bidx].strip()
        if len(pre) < 15:
            points.append((i, 'bib_early', None)); continue
        tail_start = bidx; classes.append('библиография')
    # призовой
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
            cur = best
            for _ in range(12):
                k = max(zone.rfind('. ', 0, cur-1), zone.rfind('» ', 0, cur-1),
                        zone.rfind(') ', 0, cur-1), zone.rfind('! ', 0, cur-1))
                if k <= 40: break
                sent = zone[k+2:cur].strip()
                if not sent or len(sent) > 400: break
                if PRIZE_EXT.match(sent) and AWARD_NOUN.search(sent):
                    cur = k + 2
                else:
                    break
            tail_start = cur; classes.insert(0, 'призовой')
    # мусор / рубрикатор / обрывок головы
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
        headfrag = (rem[orig_idx:], ttl, ln, ratio)
        rem = rem[:orig_idx].rstrip()
        rem2, jc2 = strip_junk(rem, aggressive=True)
        if jc2: junk_total = jc2 + ((' ' + junk_total) if junk_total else ''); rem = rem2
    if caps_cut or headfrag:
        rem2, jc3 = strip_junk(rem, aggressive=True)
        if jc3: junk_total = jc3 + ((' ' + junk_total) if junk_total else ''); rem = rem2
    if junk_total: classes.append('мусор')
    if caps_cut: classes.append('рубрикатор')
    if headfrag: classes.append('обрывок-головы')
    if len(rem) >= len(t): continue
    if len(rem.strip()) < 15 or (len(rem.strip()) < 40 and not STUB.search(rem) and not re.match(r'(По|Экранизация)\s', rem.strip())):
        points.append((i, 'короткий-остаток [' + '+'.join(classes) + ']', None)); continue
    tail = t[len(rem):]
    entry = {'lead': None, 'tail': tail, 'class': '+'.join(classes)}
    if headfrag: entry['head_match'] = {'next_title': headfrag[1], 'ratio': headfrag[3]}
    res[str(i)] = entry
    if rem.strip().endswith('-'): obs.append((i, rem.strip()[-60:]))
    log.append((i, '+'.join(classes), rem.strip()[-70:], tail[:90]))

json.dump({'cut': res}, open('work/a2_res_auto4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(points, open('work/a2_points4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = open('work/a2_review4.txt', 'w', encoding='utf-8')
cc = Counter(v['class'] for v in res.values())
print('=== КЛАССЫ ===', file=out)
for k, v in cc.most_common(): print(f'{v:5d}  {k}', file=out)
print(f'\nИТОГО авто: {len(res)}; ручных: {len(points)}; сомнительных: {len(doubts)}; дефис-обрывов: {len(obs)}', file=out)
print('\n=== РУЧНЫЕ ===', file=out)
for i, k, _ in points: print(f'cat{i} [{k}]', file=out)
print('\n=== СОМНИТЕЛЬНЫЕ ===', file=out)
for i, k, ctx in doubts: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== ОБРЫВКИ-ГОЛОВ (границы после уточнения) ===', file=out)
for i, k, remend, ts in log:
    if 'обрывок-головы' in k:
        print(f'cat{i}: …{remend} ||| {ts!r}', file=out)
print('\n=== РУБРИКАТОРЫ ===', file=out)
for i, k, remend, ts in log:
    if 'рубрикатор' in k: print(f'cat{i} [{k}]: …{remend} ||| {ts!r}', file=out)
out.close()
print('auto:', len(res), 'manual:', len(points), 'doubts:', len(doubts))
