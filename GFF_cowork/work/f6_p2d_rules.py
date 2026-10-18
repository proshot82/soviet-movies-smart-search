# -*- coding: utf-8 -*-
"""Ф6-П2д: механическая чистка OCR-мусора в аннотациях. Классы:
T — хвост «голова следующей статьи» (пропущенный сканом П2); A — номер страницы/колонтитул внутри переноса;
C — мусорные символы * ^ | < > ’ ‘ ; D — латиница/цифра вместо инициала; E — латиница внутри слова;
B — внутристрочные переносы «Рябико- ву» (по печати: строка тома оканчивается на «w1-»; по словарю: слитно/через дефис).
Выход: work/f6_p2d_draft.json (before/after/ops по cat), work/f6_p2d_review.txt."""
import json, re, sys, collections
sys.path.insert(0, 'work')
import pymorphy3
morph = pymorphy3.MorphAnalyzer()
cat = json.load(open('state/catalog_f6_p2.json', encoding='utf-8'))
LINES = {}
def lines(v):
    if v not in LINES: LINES[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    return LINES[v]
KNOWN = {}
def known(w):
    if w not in KNOWN: KNOWN[w] = morph.parse(w)[0].is_known
    return KNOWN[w]
def tag(w): return morph.parse(w)[0].tag
GEN = r'(Драма|Комедия|Мелодрама|Приключ|Детектив|Экраниз|Киноповесть|Биографич|Истори[яи]|Всесоюзный сатирич|Муз\.|Сказка|Фантастич|Кинокомедия|Трагедия|Кинороман|Эпопея|Политич|Героико|Психологич|Лирич|Сатирич|Эксцентрич|Военн|Спортивн|Детск|Мультипл|Кукольн|Графич|Объемн|Фильм-|Киноальманах|Киноновелл|Кинопоэма|Кинопритча|Кинопамфлет|Ист\.|Хроник|Революц|Драматич|Романтич|Опера|Балет|Оперетта|Водевиль|Концерт|Обозрение|Агит|Документ|Киносказка|Кинобаллада|Притча|Комедийн|Фантаст|Научно|Приключен|Историко|Трагикомед|Кинофантазия|Памфлет|Публицист|Социальн|Семейн|Молодежн|Производствен|Кинодрама|Киноочерк|Очерк)'
T_RE = re.compile(r'(?<![а-яё])[А-ЯЁ][А-ЯЁ0-9]{1,}(?:[ ,\-«»№\d!?.’“”"]+(?:[А-ЯЁ][А-ЯЁ0-9]*|[а-яё]{1,3}))*[.\-]?\s*' + GEN + r'[.,]')
HEADTAIL = re.compile(r'\d+\s?ч[.,]|\d+ м\b|цв\.|ш\.-э|ш\.-ф|19\d\d\s?г|киностудия|Мосфильм|Ленфильм|редакция')
A_RE = re.compile(r'([А-ЯЁа-яё]+)- (\d{1,4})\*?( Сов\. худ\. фильмы вып\. \d)? ([а-яё]+)')
D_MAP = {'X': 'Х', 'B': 'В', 'H': 'Н', 'K': 'К', 'M': 'М', 'T': 'Т', 'C': 'С', 'A': 'А', 'E': 'Е', 'O': 'О', 'P': 'Р', '3': 'З', '0': 'О', 'Y': 'У'}
D_RE = re.compile(r'(?<![A-Za-zА-ЯЁа-яё0-9])([XBHKMTCAEOPY3])\.(\s?)(?=[А-ЯЁ][а-яё])')
LAT2CYR = {'a': 'а', 'e': 'е', 'o': 'о', 'p': 'р', 'c': 'с', 'x': 'х', 'y': 'у', 'k': 'к', 'B': 'В', 'H': 'Н', 'K': 'К', 'M': 'М', 'T': 'Т', 'C': 'С', 'A': 'А', 'E': 'Е', 'O': 'О', 'P': 'Р', 'X': 'Х'}
E_RE = re.compile(r'(?<=[а-яё])[a-zA-Z](?=[а-яё])|(?<=[а-яё])[a-zA-Z]\b|\b[a-zA-Z](?=[а-яё])')
B_RE = re.compile(r'([А-ЯЁа-яё]+)- ([А-ЯЁа-яё]+)')
CONJ = {'и', 'или', 'а', 'но', 'либо'}
PART = {'нибудь', 'либо', 'то', 'таки'}
ENDINGS = {'заде', 'оглы', 'кызы', 'бек', 'хан', 'бей', 'паша', 'мирза', 'ага', 'эль', 'аль'}
PREF = {'абу', 'ибн', 'аль', 'эль', 'сен', 'сан', 'санта', 'ван', 'дон', 'мак', 'ла', 'ле', 'де', 'кара', 'кызыл', 'ак', 'ак-'}
# индекс строк тома: последнее слово перед переносом на конце строки → [(j, следующее слово)]
_END = {}
def end_index(v):
    if v in _END: return _END[v]
    idx = collections.defaultdict(list); ls = lines(v)
    for j, (n, t, p) in enumerate(ls):
        s = t.rstrip()
        m = re.search(r'([А-ЯЁа-яё]+)-$', s)
        if not m: continue
        k = j + 1
        while k < len(ls) and (not ls[k][1].strip() or re.match(r'^\s*\d{1,4}\s*$', ls[k][1]) or re.match(r'^\d+ Заказ', ls[k][1]) or re.match(r'^\d+ Сов\. худ', ls[k][1]) or re.match(r'^[^А-ЯЁа-яё]+$', ls[k][1])): k += 1
        nxt = re.match(r'\s*([А-ЯЁа-яё]+)', ls[k][1]) if k < len(ls) else None
        idx[m.group(1)].append((j, nxt.group(1) if nxt else ''))
    _END[v] = idx; return idx
def line_end_hyph(v, w1, w2):
    """есть ли в томе строка, оканчивающаяся на «w1-», за которой следует строка, начинающаяся с w2"""
    for j, nx in end_index(v).get(w1, []):
        if nx == w2 or (nx and w2.startswith(nx)) or (nx and nx.startswith(w2)): return j
    return None
def is_name(w):
    t = tag(w); return any(x in t for x in ('Name', 'Surn', 'Patr', 'Geox')) or (not known(w) and w[0].isupper())
ENDS_RE = re.compile(r'^(заде|оглы|кызы|бек|бека|беку|беком|хан|хана|хану|ханом|бей|бея|бею|паша|паши|паше|пашой|мирза|мирзы|мирзе|ага|аги|аге|агой|бай|бая|баю|баем|бае|эль|аль)$')
def parses(w): return morph.parse(w)
def noun_agree(w1, w2):
    for p1 in parses(w1):
        if p1.tag.POS != 'NOUN': continue
        for p2 in parses(w2):
            if p2.tag.POS == 'NOUN' and p1.tag.case == p2.tag.case and p1.tag.number == p2.tag.number: return True
    return False
def pos(w): return parses(w)[0].tag.POS
def decide_B(v, w1, w2, ctx, cat_i=None):
    """→ (замена | None=вручную, пояснение) для «w1- w2»"""
    nh, hy = w1 + w2, w1 + '-' + w2
    if w2 in PART: return hy, 'частица'
    if w2 in CONJ: return None if w2 == 'но' and not known(nh) else (nh if w2 == 'но' else None), 'висячий дефис (кино- и …)' if w2 != 'но' else 'перенос «-но»'
    if w2 in ('ка', 'же', 'ли', 'бы'):
        if known(nh): return nh, 'перенос (слитно, словарь)'
        return None, 'частица/перенос — вручную'
    if len(w1) == 1 and w1.isupper() and w2[0].isupper(): return w1 + '. ' + w2, 'инициал «Я- Протазанов» → «Я. Протазанов»'
    if ENDS_RE.match(w2.lower()) and w1[0].isupper(): return hy, 'именной суффикс (-хан/-бек/-бай/-оглы…)'
    if w2[0].isupper():
        if w1.isupper() and len(w1) >= 3 and known(w2) and not is_name(w2): return w1 + '. ' + w2, 'граница предложения после аббревиатуры'
        if known(hy) and not known(nh): return hy, 'дефисное имя (словарь)'
        return None, 'обе части с прописной — вручную'
    if known(nh) and not known(hy): return nh, 'перенос (слитно, словарь)'
    if known(hy) and not known(nh): return hy, 'дефисное слово (словарь)'
    if known(nh) and known(hy): return hy, 'оба словарные — дефис'
    if known(w1) and known(w2) and len(w1) >= 2 and len(w2) >= 2:
        if noun_agree(w1, w2):
            if w1[0].isupper() and w2[0].islower() and (cat_i, w1 + '- ' + w2) not in KEEP_HYPH: return nh, 'перенос имени (первая часть с прописной)'
            return hy, 'сложное существительное (согласованные NOUN+NOUN) — дефис'
        p1, p2 = pos(w1), pos(w2)
        if p1 in ('ADJF', 'PRTF', 'ADJS', 'NPRO', 'NUMR') and p2 in ('NOUN',): return w1 + ' ' + w2, 'определение + существительное — пробел'
        if p1 in ('ADVB', 'VERB', 'INFN', 'GRND', 'CONJ', 'PREP', 'PRCL') and p2 in ('VERB', 'INFN', 'GRND', 'NOUN', 'ADJF', 'ADVB', 'NPRO'): return w1 + ' ' + w2, 'наречие/глагол + слово — пробел'
        if p1 == 'NOUN' and p2 in ('INFN', 'PRCL', 'ADVB', 'NPRO'): return w1 + ' — ' + w2, 'дефис вместо тире'
        return None, 'обе части словарные (%s+%s) — вручную' % (p1, p2)
    return nh, 'перенос (вне словаря, строчная вторая часть)'
T2_RE = re.compile(r'\s[\^<>❖■©®Ъ&|\\/@°Ш]{1,}[^А-ЯЁа-яё]{0,30}[А-ЯЁ0-9][А-ЯЁ0-9 ,\-«»№.!?°]{3,}')
def fix_T(a, ops):
    m2 = None
    for m in T2_RE.finditer(a):
        rest = a[m.start():]
        if len(rest) <= 260 and (HEADTAIL.search(rest) or '№' in rest or re.search(r'\s' + GEN, rest)): m2 = m
    if m2 is not None:
        pre = a[:m2.start()]
        k = max(pre.rfind('.'), pre.rfind('!'), pre.rfind('?'), pre.rfind('…'), pre.rfind('»'))
        if k < 0 or len(pre) - k > 12: k = m2.start() - 1
        new = a[:k + 1].rstrip(); ops.append(('T', a[k + 1:][:80], '')); return new
    for m in T_RE.finditer(a):
        rest = a[m.start():]
        if HEADTAIL.search(rest) or len(rest) < 120:
            # начало хвоста — после последнего знака конца предложения/кавычки перед совпадением
            pre = a[:m.start()]
            k = max(pre.rfind('.'), pre.rfind('!'), pre.rfind('?'), pre.rfind('…'), pre.rfind('»'))
            if k < 0 or len(pre) - k > 40: k = m.start() - 1
            new = a[:k + 1].rstrip()
            ops.append(('T', a[k + 1:][:80], '')); return new
    return a
BIBW = re.compile(r'\sБ\W{0,2}[иі]\W{0,2}б\W{0,2}л\W{0,2}[иі]?\W{0,2}[оо]?\W{0,2}г\W{0,2}р\W{0,2}а\W{0,2}ф\W{0,2}[иі]\W{0,2}[яйи]\s?[:.\-]?', re.I)
def fix_BIB(a, ops):
    m = BIBW.search(a)
    if m and len(a) - m.start() < 1200:
        ops.append(('BIB', a[m.start():m.start() + 60], '')); return a[:m.start()].rstrip()
    return a
def fix_A(a, ops):
    def rep(m):
        ops.append(('A', m.group(0), f'{m.group(1)}- {m.group(4)}'))
        return f'{m.group(1)}- {m.group(4)}'
    return A_RE.sub(rep, a)
def fix_C(a, ops):
    s = a
    # ’ : апостроф в иноязычных именах (О’Бриен, д’Арк) — оставить
    def rep_apos(m):
        pre, post = m.group(1), m.group(2)
        if pre in 'ОДдО' and post.isupper(): return m.group(0)
        if pre.isalpha() and post.isalpha():
            if known((m.string[max(0, m.start() - 20):m.start()].split()[-1] if m.string[max(0, m.start() - 20):m.start()].split() else '') + pre + post): pass
            return pre + '\x00' + post   # решить ниже по словам
        ops.append(('C’', m.group(0), pre + post))
        return pre + post if not (pre == ' ' or post == ' ') else (pre + post).replace('  ', ' ')
    s = re.sub(r'(.)[’‘`](.)', rep_apos, s)
    s = re.sub(r'^[’‘`]|[’‘`]$', lambda m: (ops.append(('C’', m.group(0), '')), '')[1], s)
    # разбор \x00: слитно, если склейка словарная, иначе пробел
    def rep_nul(m):
        w1, w2 = m.group(1), m.group(2)
        if known(w1 + w2) or (not known(w1) and not known(w2)): ops.append(('C’', f'{w1}’{w2}', w1 + w2)); return w1 + w2
        ops.append(('C’', f'{w1}’{w2}', w1 + ' ' + w2)); return w1 + ' ' + w2
    s = re.sub(r'([А-ЯЁа-яё]+)\x00([А-ЯЁа-яё]+)', rep_nul, s)
    s = s.replace('\x00', '')
    # ■ : OCR-артефакт тире/маркера: «—■»/«■—»/«•—■» → «—»; одиночный → убрать
    if '■' in s:
        s2 = re.sub(r'\s?[•·]?\s?—\s?■|■\s?—', ' —', s); s2 = re.sub(r'\s?■\s?', ' ', s2)
        ops.append(('C■', '■', '')); s = s2
    if '•' in s:
        ops.append(('C•', '•', '')); s = re.sub(r'—\s?•\s?', '— ', s); s = re.sub(r'\s?•\s?—', ' —', s); s = s.replace('•', '')
    # * : внутри слова — убрать (склеить); «w1* w2» → склеить, если w1 не словарное, а склейка словарная; иначе просто убрать
    def join_or_space(w1, w2):
        if known(w1 + w2) and (not known(w1) or not known(w2) or len(w1) <= 3 or len(w2) <= 3): return w1 + w2
        if known(w1) and known(w2): return w1 + ' ' + w2
        if known(w1 + w2): return w1 + w2
        return w1 + ' ' + w2
    def rep_star(m):
        w1, w2 = m.group(1), m.group(2); r = join_or_space(w1, w2); ops.append(('C*', m.group(0), r)); return r
    s = re.sub(r'([А-ЯЁа-яё]+)\* ?([а-яё]+)', rep_star, s)
    if '*' in s: ops.append(('C*', '*', '')); s = s.replace('*', '')
    # ^ : между строчной и прописной без пробелов → «. » если следующее слово — словарное не-имя, иначе пробел;
    #     «слово^ Прописная» → «слово. Прописная»; «слово^ строчная» → «слово строчная»; внутри слова — оставить (буквенный класс); прочее — убрать
    def rep_caret(m):
        pre, post = m.group(1), m.group(2)
        w2 = re.match(r'[А-ЯЁ][а-яё]+', s[m.end() - 1:] if False else post + '') 
        return None
    out = []; i = 0
    for m in re.finditer(r'\^', s):
        pass
    def caret_sub(s):
        res = []; last = 0
        for m in re.finditer(r'\^', s):
            b = s[max(0, m.start() - 1):m.start()]; f = s[m.end():m.end() + 1]
            nxt = re.match(r'\s?([А-ЯЁ][а-яё]+)', s[m.end():])
            if re.match(r'[а-яёА-ЯЁ]', b) and re.match(r'[а-яёА-ЯЁ]', f):   # внутри слова
                wm = re.search(r'([А-ЯЁа-яё]+)\^([А-ЯЁа-яё]+)$', s[:m.end()] + s[m.end():].split(' ')[0].split('.')[0].split(',')[0])
                if wm and (known(wm.group(1) + wm.group(2)) or (wm.group(1)[0].isupper() and known(wm.group(1) + wm.group(2)))):
                    ops.append(('C^', wm.group(0), wm.group(1) + wm.group(2))); res.append(s[last:m.start()]); last = m.end(); continue
                if wm and known(wm.group(1)) and known(wm.group(2)) and len(wm.group(1)) > 1 and len(wm.group(2)) > 1:
                    ops.append(('C^', wm.group(0), wm.group(1) + ' ' + wm.group(2))); res.append(s[last:m.start()] + ' '); last = m.end(); continue
                res.append(s[last:m.end()]); last = m.end(); continue
            if re.match(r'[а-яё]', b) and f == ' ':
                wm2 = re.search(r'([А-ЯЁа-яё]+)\^ ([а-яё]+)', s[max(0, m.start() - 40):m.end() + 40])
                if wm2 and not known(wm2.group(1)) and known(wm2.group(1) + wm2.group(2)):
                    # склейка «кула^ ков» → «кулаков»: убрать ^ и следующий пробел
                    ops.append(('C^', wm2.group(0), wm2.group(1) + wm2.group(2))); res.append(s[last:m.start()]); last = m.end() + 1; continue
            if re.match(r'[а-яё]', b) and nxt and known(nxt.group(1)) and not is_name(nxt.group(1)):
                rep = '. ' if f != ' ' else '.'
            elif re.match(r'[а-яё]', b) and re.match(r'[А-ЯЁ]', f):
                rep = ' '
            elif re.match(r'[а-яё]', b) and f == ' ':
                rep = ''
            elif re.match(r'[а-яё]', b) and re.match(r'[а-яё0-9]', f):
                rep = ' '
            else:
                rep = ''
            ops.append(('C^', s[max(0, m.start() - 12):m.end() + 12], rep))
            res.append(s[last:m.start()] + rep); last = m.end()
        res.append(s[last:]); return ''.join(res)
    s = caret_sub(s)
    # | : убрать (внутри слова — оставить буквенному классу)
    s = re.sub(r'(?<![А-ЯЁа-яё])\|(?![А-ЯЁа-яё])|(?<=\s)\|', lambda m: (ops.append(('C|', '|', '')), '')[1], s)
    # < > : парные кавычки если есть пара, иначе убрать
    def lt(m):
        seg = s[m.end():m.end() + 80]
        if re.match(r'\s?[А-ЯЁа-яё]', s[m.end():m.end() + 2]) and '»' in seg and '«' not in seg.split('»')[0]:
            ops.append(('C<', m.group(0), '«')); return '«'
        ops.append(('C<', m.group(0), '')); return ''
    s = re.sub(r'<', lt, s)
    def gt(m):
        seg = s[max(0, m.start() - 80):m.start()]
        if re.search(r'[А-ЯЁа-яё.!?°0-9]\s?$', seg) and '«' in seg and '»' not in seg.split('«')[-1]:
            ops.append(('C>', m.group(0), '»')); return '»'
        ops.append(('C>', m.group(0), '')); return ''
    s = re.sub(r'>', gt, s)
    s = re.sub(r'\s+»', '»', s); s = re.sub(r'«\s+', '«', s)
    return s
def fix_D(a, ops):
    def rep(m):
        ops.append(('D', m.group(0), D_MAP[m.group(1)] + '.' + (m.group(2) or ' ')))
        return D_MAP[m.group(1)] + '.' + (m.group(2) if m.group(2) else ' ')
    return D_RE.sub(rep, a)
def fix_E(a, ops):
    def rep(m):
        ch = m.group(0); r = LAT2CYR.get(ch)
        if r is None: return ch
        ops.append(('E', a[max(0, m.start() - 8):m.end() + 8], r)); return r
    return E_RE.sub(rep, a)
MANUAL_B = {}
try:
    from f6_p2d_manual import MANUAL_B, MANUAL_AFTER, MANUAL_REPL, KEEP_HYPH, LEAD_CUTS, TAIL_CUTS, PAGES, SERIES
except ImportError:
    MANUAL_AFTER = {}; MANUAL_REPL = {}; KEEP_HYPH = set(); LEAD_CUTS = {}; TAIL_CUTS = {}; PAGES = {}; SERIES = {}
def fix_B(v, a, ops, manual, cat_i=None):
    def rep(m):
        w1, w2 = m.group(1), m.group(2)
        key = (cat_i, m.group(0))
        if key in MANUAL_B: new, why = MANUAL_B[key], 'вручную'
        else: new, why = decide_B(v, w1, w2, a[max(0, m.start() - 30):m.end() + 30], cat_i)
        if new is None:
            manual.append(('B', m.group(0), why, a[max(0, m.start() - 40):m.end() + 40])); return m.group(0)
        ops.append(('B', m.group(0), new, why)); return new
    return B_RE.sub(rep, a)

def join_or_space_g(w1, w2):
    if known(w1 + w2) and (not known(w1) or not known(w2) or len(w1) <= 3 or len(w2) <= 3): return w1 + w2
    if known(w1) and known(w2): return w1 + ' ' + w2
    if known(w1) and not known(w2) and not known(w1 + w2): return w1 + ' ' + w2
    if known(w1 + w2): return w1 + w2
    if not known(w1) and not known(w2): return w1 + w2   # апостроф внутри искажённого слова — склеить (слово уйдёт в список кандидатов)
    return w1 + ' ' + w2
def fix_Q(a, ops):
    """кавычки/апострофы: „ → запятая или убрать; ASCII ' — оставить в д'Артаньян/О'Рори, внутри слова — склеить/пробел, иначе убрать;
    “ ” " — парные → « », непарные — мусор (убрать)"""
    s = a
    if '„' in s:
        s2 = re.sub(r'(?<=[А-ЯЁа-яё])„(?=\s[а-яё])', ',', s); s2 = re.sub(r'(?<=[А-ЯЁа-яё])„(?=[а-яё])', ', ', s2)
        if s2 != s: ops.append(('C„', '„', ',')); s = s2
        if '„' in s: ops.append(('C„', '„', '')); s = s.replace('„', '')
    if "'" in s:
        s = re.sub(r"(?<=[дДОO])'(?=[А-ЯЁ])", '\x01', s)
        def rep_in(m):
            w1, w2 = m.group(1), m.group(2); r = join_or_space_g(w1, w2); ops.append(("C'", m.group(0), r)); return r
        s = re.sub(r"([А-ЯЁа-яё]+)'([А-ЯЁа-яё]+)", rep_in, s)
        def rep_rest(m):
            prev = s[m.start() - 1] if m.start() > 0 else ' '; nxt = s[m.end()] if m.end() < len(s) else ' '
            r = ' ' if (prev in '.!?»:;,' and re.match(r'[А-ЯЁа-яё0-9«]', nxt)) else ''
            ops.append(("C'", s[max(0, m.start() - 10):m.end() + 10], r)); return r
        s = re.sub(r"'", rep_rest, s)
        s = s.replace('\x01', "'")
    if re.search(r'[“”"]', s):
        res = list(s); stack = []; junk = []
        for m in re.finditer(r'[“”"]', s):
            p = m.start(); prev = s[p - 1] if p > 0 else ' '; nxt = s[p + 1] if p + 1 < len(s) else ' '
            opening = (prev in ' («—-\n' ) and not nxt.isspace() and nxt not in '.,;:!?)»'
            closing = (not prev.isspace()) and prev not in '(«' and (nxt.isspace() or nxt in '.,;:!?)—»')
            if opening and not closing: stack.append(p)
            elif closing and not opening and stack:
                o = stack.pop(); res[o] = '«'; res[p] = '»'
            else: junk.append(p)
        junk += stack
        for p in junk:
            prev = s[p - 1] if p > 0 else ' '; nxt = s[p + 1] if p + 1 < len(s) else ' '
            res[p] = ' ' if (re.match(r'[А-ЯЁа-яё0-9]', prev) and re.match(r'[А-ЯЁа-яё0-9]', nxt)) else ''
        s2 = ''.join(res)
        if s2 != s:
            ops.append(('C"', ''.join(sorted(set(re.findall(r'[“”"]', s)))), f'пар→«»: {len(re.findall("«", s2)) - len(re.findall("«", s))}, мусор: {len(junk)}')); s = s2
    # одиночные мусорные символы между пробелами и знак «।» где угодно
    s2 = re.sub(r'(?<=\s)[।_\[\]{}\\#$£™¡¿](?=\s)', '', s); s2 = s2.replace('।', '')
    if s2 != s: ops.append(('C×', ''.join(sorted(set(re.findall(r'[।_\[\]{}\\#$£™¡¿]', s)))), '')); s = s2
    return s
DOT_RE = re.compile(r'(?<=\s)[.,;:](?![.,;:])(?=[а-яё«])|(?<=[.!?…»]\s)[.,;:](?![.,;:])(?=[А-ЯЁ])')
def fix_dot(a, ops):
    """одиночный знак препинания, приклеенный сканом к началу слова («он энер- .гично», «отправляется ,в СССР», «Палыч. .Он») — убрать"""
    def rep(m):
        ops.append(('C.', a[max(0, m.start() - 12):m.end() + 8], '')); return ''
    a = DOT_RE.sub(rep, a)
    def rep2(m):   # «Ганна .С помощью» → «Ганна. С помощью»; «И вот .Володя» → «И вот Володя»
        w = m.group(1); r = w + '. ' if w[0].isupper() else w + ' '
        ops.append(('C.', m.group(0), r.rstrip())); return r
    a = re.sub(r'([А-ЯЁа-яё]+)\s\.(?!\.)(?=[А-ЯЁ])', rep2, a)
    return a
def fix_P(a, ops, cat_i):
    """номер страницы, вставленный сканом внутрь прозы на границе страниц (без переноса) — убрать"""
    if cat_i not in PAGES: return a
    for tok in PAGES[cat_i]:
        pat = r'(?<=\s)' + re.escape(tok) + r'(?=\s)'
        assert len(re.findall(pat, a)) == 1, f'cat{cat_i}: PAGES «{tok}» ×{len(re.findall(pat, a))}'
        a = re.sub(pat + r'\s', '', a); ops.append(('P', tok, ''))
    return a
def fix_R(a, ops, cat_i):
    """реконструкция потерянной цифры «1-я серия» (в docx: «-я серия» / «серия —» при наличии далее «2-я серия»)"""
    if cat_i not in SERIES: return a
    for old, new in SERIES[cat_i]:
        assert a.count(old) == 1, f'cat{cat_i}: SERIES «{old}» ×{a.count(old)}'
        a = a.replace(old, new); ops.append(('R', old, new))
    return a
def norm_ws(a):
    a = re.sub(r'[ \t\r\f\v ]+', ' ', a)
    a = re.sub(r' ?\n ?', '\n', a)
    return a.strip()
draft = {}; review = []; manual_all = []
for i, r in enumerate(cat):
    a0 = r['annotation']
    if not a0: continue
    v = r['source'].split('_')[0]; ops = []; manual = []
    a = a0
    for item in MANUAL_REPL.get(i, []):
        old, new = item[0], item[1]; n = item[2] if len(item) > 2 else 1
        assert a.count(old) == n, f'cat{i}: MANUAL_REPL «{old}» ×{a.count(old)} (ожидалось {n})'
        a = a.replace(old, new); ops.append(('M', old, new) + ((f'×{n}',) if n > 1 else ()))
    if i in LEAD_CUTS:
        k = a.index(LEAD_CUTS[i]); assert k > 0 and a.count(LEAD_CUTS[i]) == 1; ops.append(('L', a[:k][:80] + '…', '')); a = a[k:]
    if i in TAIL_CUTS:
        k = a.index(TAIL_CUTS[i]); assert a.count(TAIL_CUTS[i]) == 1; ops.append(('T', a[k:][:80], '')); a = a[:k].rstrip()
    a = fix_T(a, ops); a = fix_BIB(a, ops); a = fix_A(a, ops); a = fix_P(a, ops, i); a = fix_C(a, ops); a = fix_Q(a, ops); a = fix_dot(a, ops); a = fix_D(a, ops); a = fix_E(a, ops); a = fix_B(v, a, ops, manual, i)
    if i in MANUAL_AFTER: ops.append(('M', a[:60], MANUAL_AFTER[i][:60])); a = MANUAL_AFTER[i]
    a = fix_R(a, ops, i)
    a = fix_T(a, ops)   # второй проход после снятия мусорных символов
    a = norm_ws(a)
    a2 = re.sub(r'\s([.,;:])$', r'\1', a)                                   # «слово .» в конце → «слово.»
    a2 = re.sub(r'(?<=[.!?…»)])\s[.,;:](?=\s)', '', a2)                     # одиночный знак после знака препинания — мусор
    a2 = re.sub(r'(?<=[А-ЯЁа-яё0-9)»])\s([.,;:])(?=\s)', r'\1', a2)         # «слово , слово» → «слово, слово»
    a2 = re.sub(r'(?<=\S)\s+([,.;:!?»)])(?=\s|$)', r'\1', a2)
    a2 = re.sub(r'«\s+(?=[А-ЯЁа-яё0-9])', '«', a2)
    a2 = re.sub(r'(?<=[А-ЯЁа-яё0-9.!?…])\s+»', '»', a2)
    a2 = re.sub(r'(\d) -я', r'\1-я', a2)
    a2 = norm_ws(a2)
    if a2 != a: ops.append(('WS', 'одиночные знаки препинания/пробелы', '')); a = a2
    m_tail = re.search(r'([.!?…»)])([^А-ЯЁа-яё]*)$', a)   # мусор после конечной пунктуации (только с явно мусорными символами)
    if m_tail and m_tail.group(2) and re.search(r'[\^<>■❖©®Ъ|\\/@°&*•A-Za-z]', m_tail.group(2)):
        ops.append(('J', m_tail.group(2), '')); a = a[:m_tail.end(1)]
    if manual: manual_all.append((i, manual))
    if a != a0:
        if not ops:
            assert re.sub(r'\s', '', a) == re.sub(r'\s', '', a0), f'cat{i}: изменение без операций'
            ops.append(('WS', 'пробелы', ''))
        draft[i] = {'before': a0, 'after': a, 'ops': ops}
json.dump(draft, open('work/f6_p2d_draft.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(manual_all, open('work/f6_p2d_manual.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
cnt = collections.Counter(o[0] for d in draft.values() for o in d['ops'])
print('записей с правками:', len(draft), '; операций:', dict(cnt), '; вручную:', sum(len(m) for _, m in manual_all))
with open('work/f6_p2d_review.txt', 'w', encoding='utf-8') as f:
    for cls in ('T', 'L', 'A', 'P', 'R', 'C’', "C'", 'C"', 'C„', 'C.', 'C×', 'C*', 'C^', 'C|', 'C<', 'C>', 'D', 'E', 'M', 'B'):
        f.write(f'\n\n######## {cls}\n')
        for i, d in draft.items():
            for o in d['ops']:
                if o[0] == cls: f.write(f'cat{i}: {o[1]!r} -> {o[2]!r}' + (f'  [{o[3]}]' if len(o) > 3 else '') + '\n')
    f.write('\n\n######## MANUAL\n')
    for i, ms in manual_all:
        for m in ms: f.write(f'cat{i}: {m[1]!r} [{m[2]}] {m[3]!r}\n')
