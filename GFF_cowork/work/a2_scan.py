# -*- coding: utf-8 -*-
"""П4 a2 — детект хвостовых срезов. Пишет work/a2_res_draft.json + work/a2_review.txt."""
import json, re, random

cat = json.load(open('state/catalog_f5_a1.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
A1 = {388,464,470,2024,2525,2739,3318,5244,5890,6966,3554,1186,
      1184,4767,5456,5468,5606,5645,5894,6334,6335,6546,7230,7231}

AWARD_NOUN = re.compile(r'(приз|преми|диплом|медал|награ|удостоен|присужд|отмечен|Гран-при|Гоан-при|ФИПРЕССИ|жюри)', re.I)
PRIZE_ANCHORS = [
 re.compile(r'(?:На|В)\s+[IVXХ\d]*\s*[^.]{0,90}?(?:кинофестивал|фестивал|киносмотр|смотре-конкурс|смотре|конкурс)'),
 re.compile(r'Фильму?\s+(?:удостоен|присужден|награжден|отмечен)'),
 re.compile(r'(?:Высшая|Первая|Вторая|Третья|Главная|Специальная|Золотая|Серебряная|Бронзовая|Большая|Почетная|Поощрительная)\s+(?:премия|приз|награда|медаль)', re.I),
 re.compile(r'(?:Главный|Специальный|Первый|Второй|Третий|Большой|Золотой|Серебряный|Бронзовый|Почетный|Поощрительный)\s+(?:приз|диплом)', re.I),
 re.compile(r'Приз(?:ы)?[\s,]'),
 re.compile(r'Диплом(?:ы)?[\s,]'),
 re.compile(r'Преми[яи]\s'),
 re.compile(r'(?:Государственная|Ленинская)\s+премия'),
 re.compile(r'Гран-при|Гоан-при'),
 re.compile(r'Лучший\s+фильм\s'),
]
SENT_BOUND = re.compile(r'[.!?…»)]\s+$|^\s*$')
RUBRIC_WORD = re.compile(r'(ФИЛЬМЫ|КИНОЖУРНАЛ|МУЛЬТИПЛИКАЦИОН|ИГРОВЫЕ|ПРИЛОЖЕНИ|УКАЗАТЕЛ|ХРОНИКАЛЬН|КИНОКАРТИН)')
HARD_JUNK = set('<>■❖^~|\\/@#$%&=+{}[]')

def strip_junk(rem):
    """Снять хвостовые мусорные токены (жёсткие символы; чисто-символьные)."""
    cut = ''
    changed = True
    while changed:
        changed = False
        m = re.search(r'\s([^\s]+)$', ' ' + rem)
        if not m: break
        tok = m.group(1)
        hard = any(ch in HARD_JUNK for ch in tok)
        noletters = not re.search(r'[А-ЯЁа-яёA-Za-z0-9]', tok)
        latfrag = (not re.search(r'[А-ЯЁа-яё]', tok)) and len(tok) <= 4 and not tok.rstrip('.').isdigit()
        cyr1 = len(re.findall(r'[А-ЯЁа-яё]', tok)) <= 2 and hard
        if hard or noletters or (latfrag and cut) or cyr1:
            rem = rem[:len(rem)-len(tok)].rstrip()
            cut = tok + (' ' + cut if cut else '')
            changed = True
    return rem, cut

PUNCT_TOK = re.compile(r'^[«»()\d.,:;\-—–№<>^~■❖\'"!?]+$')
CAPS_TOK = re.compile(r'^[«»()\d.,:;\-—–№<>^~■❖]*[А-ЯЁA-Z][А-ЯЁA-Z«»()\d.,:;\-—–№<>^~■❖]*$')
def _is_caps_tok(tok):
    letters = re.findall(r'[А-ЯЁа-яёA-Za-z]', tok)
    if not letters: return None  # пунктуация/цифры
    up = sum(1 for ch in letters if ch.isupper())
    return up / len(letters) >= 0.8 and len(letters) >= 2

def caps_run(rem):
    """Хвостовой капс-огрызок (рубрикатор/голова) — токенный проход с конца."""
    toks = rem.split()
    k = len(toks); caps_words = 0
    while k > 0:
        tok = toks[k-1]
        if PUNCT_TOK.match(tok) or re.match(r'^[IVXХ\d]+[.,]?$', tok):
            k -= 1; continue
        c = _is_caps_tok(tok)
        if c:
            caps_words += 1; k -= 1; continue
        break
    if caps_words < 2: return rem, '', None
    run = ' '.join(toks[k:])
    if len(run) < 10: return rem, '', None
    pos = rem.rfind(run)
    before = rem[:pos]
    if before.rstrip().endswith('«'): return rem, '', None
    kind = 'rubric' if RUBRIC_WORD.search(run) else 'head_fragment'
    return before.rstrip(), run.strip(), kind

res, points, doubts, log = {}, [], [], []
for i, r in enumerate(cat):
    if i in strays or i in A1: continue
    t = r.get('annotation')
    if not t: continue
    classes, tail_start = [], len(t)
    # 1) библиография
    bidx = None
    for mark in ('Библиография', 'БИБЛИОГРАФИЯ'):
        j = t.find(mark)
        if j != -1: bidx = j if bidx is None else min(bidx, j)
    if bidx is None:
        j = t.find('библиография')
        if j != -1: points.append((i, 'bib_lower', t[max(0,j-60):j+80])); 
    if bidx is not None:
        if len(t[:bidx].strip()) < 40:
            points.append((i, 'bib_early', t[:160])); continue
        tail_start = bidx; classes.append('библиография')
    # 2) призовой блок (в зоне до библиографии)
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
        block = zone[best:tail_start]
        if len(block) > 1500:
            doubts.append((i, 'prize_long', zone[max(0,best-80):best+100]))
        else:
            tail_start = best; classes.insert(0, 'призовой')
    # 3) хвостовой мусор и капс-огрызки на остатке
    rem = t[:tail_start].rstrip()
    junk_total, caps_cut, caps_kind = '', '', None
    for _ in range(4):
        rem, jc = strip_junk(rem)
        if jc: junk_total = jc + (' ' + junk_total if junk_total else '')
        rem2, cc, kind = caps_run(rem)
        if cc:
            rem = rem2; caps_cut = cc + (' ' + caps_cut if caps_cut else '')
            caps_kind = kind if caps_kind is None else caps_kind
        if not jc and not cc: break
    if junk_total: classes.append('мусор')
    if caps_cut: classes.append('рубрикатор' if caps_kind == 'rubric' else 'обрывок-головы')
    if len(rem) >= len(t): continue
    tail = t[len(rem):]
    # валидация остатка
    if len(rem.strip()) < 40:
        points.append((i, 'короткий-остаток', t[:200])); continue
    if not re.search(r'[.!?…»)]$|[а-яё]\.$', rem.strip()):
        doubts.append((i, 'обрыв-остатка? ' + '+'.join(classes), rem.strip()[-90:] + ' ||| ' + tail[:90]))
        continue
    res[str(i)] = {'lead': None, 'tail': tail, 'class': '+'.join(classes)}
    log.append((i, '+'.join(classes), rem.strip()[-70:], tail[:80]))

json.dump({'cut': res, 'restore': {}, 'none': {}, 'confirm': {}, 'notfound': {}},
          open('work/a2_res_draft.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

out = open('work/a2_review.txt', 'w', encoding='utf-8')
from collections import Counter
cc = Counter(v['class'] for v in res.values())
print('=== КЛАССЫ ===', file=out)
for k, v in cc.most_common(): print(f'{v:5d}  {k}', file=out)
print(f'\nИТОГО срезов: {len(res)}; точечных: {len(points)}; сомнительных: {len(doubts)}', file=out)
print('\n=== ТОЧЕЧНЫЕ ===', file=out)
for i, k, ctx in points: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== СОМНИТЕЛЬНЫЕ ===', file=out)
for i, k, ctx in doubts: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== ВСЕ ПРИЗОВЫЕ СРЕЗЫ (остаток-конец ||| срез-начало) ===', file=out)
for i, k, remend, ts in log:
    if 'призовой' in k: print(f'cat{i}: …{remend} ||| {ts}', file=out)
print('\n=== ВСЕ ОБРЫВКИ-ГОЛОВ/РУБРИКАТОРЫ/МУСОР (без библ. и призов) ===', file=out)
for i, k, remend, ts in log:
    if ('обрывок-головы' in k or 'рубрикатор' in k or 'мусор' in k) and 'библиография' not in k and 'призовой' not in k:
        print(f'cat{i} [{k}]: …{remend} ||| {ts!r}', file=out)
random.seed(3)
bibs = [x for x in log if 'библиография' in x[1]]
print('\n=== ВЫБОРКА БИБЛИОГРАФИЧЕСКИХ (60) ===', file=out)
for i, k, remend, ts in random.sample(bibs, min(60, len(bibs))):
    print(f'cat{i} [{k}]: …{remend} ||| {ts}', file=out)
out.close()
print('draft cuts:', len(res), 'points:', len(points), 'doubts:', len(doubts))
