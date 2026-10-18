# -*- coding: utf-8 -*-
"""Ф5-П2 v4: структурный нормализатор studio (цикл: серии/формат/метраж/юнит/кляксы)."""
import re
from collections import Counter

OLD_VOLS = {'v1_1918-1935','v2_1936-1957','v3_1958-1963'}
LEAD_ORDINAL_NAME = re.compile(r'^\d+-[яйе]\s+[А-ЯЁа-яё]')
GOOD_LOW = re.compile(r'^(редакция|киностудия|совместное|производство|худ\.|акц\.|т-во|ателье|киноконтора|киноколлектив|артель|коллектив|кинокружок|кинокурсы|кинокомбинат|киносекция|объединение|студия|любительский|метр)', re.I)

SUPPLEMENT = {('Нарком','восна'):'Наркомвоена',('Гос','кинцром'):'Госкинпром',('Сев','запкиио'):'Севзапкино',
 ('Сев','запкшю'):'Севзапкино',('кине','студия'):'киностудия',('киво','студия'):'киностудия',
 ('кинс','студия'):'киностудия',('Ташкент','ска'):'Ташкентская',('Аэербайджан','фильм'):'Азербайджанфильм',
 ('Лён','фильм'):'Ленфильм',('Грузин','фильм'):'Грузия-фильм',('Прометеус','фильм'):'Прометеус-фильм',
 ('Тельсия','фильм'):'Тельсия-фильм',('Омега','фильм'):'Омега-фильм',('Интер-альянс','фильм'):'Интер-альянс-фильм',
 ('Потсдам','Бабельсберг'):'Потсдам-Бабельсберг',('Союзтех','фильм'):'Союзтехфильм',('Культур','фильм'):'Культурфильм',
 ('Восток','фильм'):'Востокфильм',('Мостех','фильм'):'Мостехфильм',('Киевнауч','фильм'):'Киевнаучфильм',
 ('Суоми','фильм'):'Суоми-фильм',('Всеукррев','кома'):'Всеукрревкома',
 ('Болгар','фильм'):'Болгар-фильм',('Кино','рабмол'):'Кино-рабмол'}
DOCX_FLAG_PAIRS = {('Болгар','фильм'),('Кино','рабмол')}
WHITELIST_TOK = {'В/О','A/О','А/О','а/о','и','ш.-ф.','ш.-э.'}

def prefix_fixes(s):
    s = s.replace('>>','»').replace('“','«').replace('”','»')
    s = re.sub(r'\bI9(\d\d)\b', r'19\1', s)
    s = re.sub(r'\b1J(\d\d)\b', r'19\1', s)
    s = re.sub(r'\b(19\d)\s(\d)\b', r'\1\2', s)
    s = re.sub(r'\b4\s?9(\d\d)(?=\s*г\b)', r'19\1', s)
    s = re.sub(r'\b1\s(\d\d)(?=\s*г\b)', r'19\1', s)
    s = re.sub(r'[*¡](\d{3})\b', r'1\1', s)
    s = re.sub(r'\b(19\d)\$', r'\g<1>5', s)
    s = re.sub(r"(\d)[’']\s*(?=г\b)", r'\1 ', s)
    s = re.sub(r'<(?=[А-ЯЁ])', '«', s)
    s = re.sub(r'"(\S)', r'«\1', s)
    s = re.sub(r'(\S)"', r'\1»', s)
    return s

JUNKCH = set('<>&/=_@^\\|$§!;£’\'`~%+*?')
def is_junk_token(t):
    if t in WHITELIST_TOK: return False
    if LEAD_ORDINAL_NAME.match(t+' а'): return False
    cyr = len(re.findall(r'[А-Яа-яЁё]', t))
    lat = len(re.findall(r'[A-Za-z]', t))
    sym = sum(1 for c in t if c in JUNKCH)
    par = t.startswith('(') or t.endswith(')')
    if cyr == 0 and (lat or sym or par or t.isdigit() is False and re.fullmatch(r'[\d).,(]+', t or 'x') ): return bool(t.strip('.,'))
    if cyr == 0: return True
    if (sym or lat) and cyr <= 3: return True
    return False

def strip_lead_cycle(s, tags):
    UNIT = re.compile(r"^[-;>.,’'¿£(]*[а-яё]{1,3}[»«<*./A-Za-z0-9?£’'ьэi]*[.,]?\s*(?=[А-ЯЁа-яё«\d(])")
    METR = re.compile(r'^[^А-Яа-яЁё«]*\d[\d\s.,]*(?:[A-Za-z]{1,2}[\s.,]*)*')
    SER  = re.compile(r'^\(?\d*\s*-?\s*я?\s*(серия|часть|сер\.|ч\.|чч\.)\)[,\s]*')
    FMT  = re.compile(r'^(?:ш\.-[фэ]\.|шф|каше|стереовариант|обычн\.|плоек,?\s*вариант|плоскостной|пано-?\s?рамн\.?|широкоэкран\.?|широкоэкр\.?|цв\.?|тт|без надп\.\)|с эпил\.)\s*[—\-]?\s*[\d.,]*\s*м?\s*[,)\s]*', re.I)
    for _ in range(12):
        s0 = s
        if LEAD_ORDINAL_NAME.match(s): break
        m = SER.match(s)
        if m: s = s[m.end():]; tags.append('срез:серия'); continue
        m = FMT.match(s)
        if m and m.end() < len(s): s = s[m.end():]; tags.append('срез:формат'); continue
        m = METR.match(s)
        if m and 0 < m.end() < len(s) and re.search(r'\d', s[:m.end()]):
            s = s[m.end():]; tags.append('срез:метраж')
            mu = UNIT.match(s)
            if mu: s = s[mu.end():]
            continue
        if not (s[:1].isupper() or s[:1]=='«' or GOOD_LOW.match(s)):
            toks = s.split(' ', 1)
            if len(toks)==2 and (is_junk_token(toks[0]) or len(re.sub(r'[^А-Яа-яЁё]','',toks[0]))<=2):
                if toks[0]=='и': tags.append('FLAG:лид-и')
                s = toks[1]; tags.append('срез:клякса-лид'); continue
        else:
            toks = s.split(' ', 1)
            if len(toks)==2 and is_junk_token(toks[0]):
                s = toks[1]; tags.append('срез:клякса-лид'); continue
        if s == s0: break
    return s

MIDFMT = re.compile(r'\(?(стереовариант|плоскостной|обычн\.|ш\.-[фэ]\.|каше)\)?[,\s]*[\d.,]*\s*м?[,\s]+')
def strip_mid_junk(s, tags):
    s2 = MIDFMT.sub('', s)
    if s2 != s: tags.append('срез:формат'); s = s2
    toks = s.split(' ')
    out = [t for t in toks
           if not (is_junk_token(t) and not GOOD_LOW.match(t) and not re.fullmatch(r'[\d.,]+', t))]
    if len(out) != len(toks): tags.append('срез:клякса')
    return ' '.join(out)

def tail_strip(s, year, tags, flags):
    s = re.sub(r'\s*[,.]?\s*(ВЭ|ВРЭ|РУ)[\s\d.,IVXХЛН«]*(неизв\.?)?\s*$', '', s)
    s = re.sub(r'(?:^|,)\s*ч/б\s*(?=,|$)', '', s)
    s = re.sub(r',\s*[\d.,]+\s*[лмк][а-яё]{0,2}\s*$', '', s)
    m = re.search(r"[,.\s]*\(?(19\d\d)\s*[-–—]\s*(19\d\d)\s*гг?['.„»]{0,3}\s*\)?\s*$", s)
    if m and len(s[:m.start()].strip()) >= 4:
        tags.append('срез:год-диапазон'); flags.append(f'год-диапазон:{m.group(1)}-{m.group(2)}')
        s = s[:m.start()]
    m = re.search(r"[,.\s]*\(?\s*(19\d\d)\s*[-,.]?\s*[гiIт1]?[\s'.,;„»*ъ\-]{0,4}\)?\s*$", s)
    if m and len(s[:m.start()].strip()) >= 4:
        y = int(m.group(1)); tags.append('срез:год')
        if year is not None and y != year: flags.append(f'год-кандидат:{y}')
        s = s[:m.start()]
    prev=None
    while prev!=s:
        prev=s
        m = re.search(r'[\s.,]*(?:[*…]+|,\s*[1Iz]|[\-–—]|,\s*>)\s*$', s)
        if m and len(s[:m.start()].strip())>=4 and not re.search(r',\s*[МЛ]$', s[:m.start()].strip()+s[m.start():m.start()+3]): s=s[:m.start()]
    s = s.strip(' ,')
    if re.search(r',\s*[МЛ]$', s): s += '.'
    elif s.endswith('.') and not re.search(r'[А-ЯЁ]\.$|ф-ка\.$', s): s = s[:-1]
    return s.rstrip('.') + '.' if re.search(r'(?<![А-ЯЁ])\.\.$', s) else s

def build_tables(values):
    tf, bg = Counter(), Counter()
    for v in values:
        if re.search(r'[А-ЯЁа-яё][-*] [А-ЯЁа-яё]', v): continue
        toks = re.findall(r'[А-ЯЁа-яё][А-ЯЁа-яё\-]+', v)
        tf.update(toks); bg.update(zip(toks, toks[1:]))
    return tf, bg

def rejoin(s, tf, bg, tags, flags):
    def repl(m):
        a,b = m.group(1), m.group(2)
        if (a,b) in SUPPLEMENT:
            if (a,b) in DOCX_FLAG_PAIRS: flags.append('docx:слитность')
            tags.append(f'перенос+словарь:{a}→{SUPPLEMENT[(a,b)]}'); return SUPPLEMENT[(a,b)]
        cj,ch = a+b, a+'-'+b
        fj,fh,fs = tf.get(cj,0), tf.get(ch,0), bg.get((a,b),0)
        best = max(fj,fh,fs)
        if best>=2:
            if fj==best: tags.append(f'перенос:→{cj}'); return cj
            if fh==best: tags.append(f'перенос:→{ch}'); return ch
            tags.append(f'перенос:→{a} {b}'); return a+' '+b
        tags.append(f'перенос:НЕРАЗРЕШЁН {a}'); return m.group(0)
    prev=None
    while prev!=s:
        prev=s
        s = re.sub(r'([А-ЯЁа-яё][А-ЯЁа-яё\-]*)[-*] ([А-ЯЁа-яё][А-ЯЁа-яё\-]*)', repl, s, count=1)
    # пробельные разрывы: joined аттестован >=5, биграмма не аттестована, одна часть <=4
    toks = s.split(' ')
    out=[]; i=0
    while i < len(toks):
        if i+1 < len(toks):
            a,b = toks[i], toks[i+1]
            if re.fullmatch(r'[А-Яа-яЁё]+', a or '!') and re.fullmatch(r'[а-яё]+', b or '!'):
                if (bg.get((a,b),0)<=3 and tf.get(a+b,0)>=10) or (bg.get((a,b),0)==0 and tf.get(a+b,0)>=5 and (len(a)<=4 or len(b)<=4)):
                    out.append(a+b); tags.append(f'разрыв:→{a+b}'); i+=2; continue
        out.append(toks[i]); i+=1
    return ' '.join(out)

def fix_quotes_era(s, source, tags):
    if ('»' in s) != ('«' in s):
        if source in OLD_VOLS:
            s2 = s.replace('«','').replace('»','').strip(' ,.')
            if s2: s=s2; tags.append('лапка:снята(стар.том)')
        else:
            if '»' in s:
                m = re.match(r'^([А-ЯЁ][А-Яа-яЁё\- .]*?)\s*»', s)
                if m: s='«'+s; tags.append('лапка:восстановлена «')
                else: tags.append('лапка:НЕСТАНДАРТ')
            else:
                m = re.search(r'«\s*([А-ЯЁ][А-Яа-яЁё\- .]*)$', s)
                if m: s=s+'»'; tags.append('лапка:восстановлена »')
                else: tags.append('лапка:НЕСТАНДАРТ')
    return s

def normalize(s, year, source, tf, bg):
    tags, flags = [], []
    s = re.sub(r'\s+',' ', s).strip()
    s = prefix_fixes(s)
    s = strip_lead_cycle(s, tags)
    s = tail_strip(s, year, tags, flags)
    s = re.sub(r'\b([А-ЯЁ]|Дж)- (?=[А-ЯЁ])', r'\1. ', s)
    s = strip_mid_junk(s, tags)
    s = tail_strip(s, year, tags, flags)
    s = rejoin(s, tf, bg, tags, flags)
    s = fix_quotes_era(s, source, tags)
    s = re.sub(r'\s+',' ', s).replace('« ','«').replace(' »','»').replace(' ,',',').strip(' ,')
    for t in list(tags):
        if t=='FLAG:лид-и': flags.append('docx:лид-и(возможна утрата копродукции)'); tags.remove(t)
    return (s if s else None), tags, flags
