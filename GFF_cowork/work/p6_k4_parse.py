# -*- coding: utf-8 -*-
"""k4: Фитиль-сюжеты — разбор статей киножурналов по извлечениям томов (v2).
Текст восстановления = [заметка перед интро] + интро («Состоит из N сюжетов.») + для каждого сюжета «Название.» + проза.
Титры/студии сюжетов/ремарки в скобках не включаются. Сомнительные — в отчёт, не в резолюцию."""
import json, re, sys, collections
import sys as _sys
CAT_PATH = _sys.argv[1] if len(_sys.argv) > 1 and _sys.argv[1].endswith('.json') else 'state/catalog_f5_k3.json'
cat = json.load(open(CAT_PATH, encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
S = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
_L = {}
def L(v):
    if v not in _L: _L[v] = json.load(open(f'work/{v}_lines.json', encoding='utf-8'))
    return _L[v]
def norm(s): return s.replace('Ns', '№').replace('N°', '№').replace('Na', '№').replace('N ', '№ ').upper().replace('Ё', 'Е')
NUMW = {'двух': 2, 'трех': 3, 'трёх': 3, 'четырех': 4, 'четырёх': 4, 'пяти': 5, 'шести': 6, 'семи': 7, 'восьми': 8, 'девяти': 9, 'десяти': 10, 'одного': 1}
MARK = r'(?:[Аа]вт\.|[Аа]вт-|[Аа]вт\.?\s?сцен|[Аа]вторы?\s+(?:сцен|текст|сюжет)|[Рр]еж\.|[Оо]пер\.|[Хх]уд\.|[Кк]омпоз\.|[Рр]ед\.|[Зз]вукоопер|В ролях|В роли|[Рр]оли исполняют|[Сс]тихи [А-ЯЁ]\.|[Тт]екст [А-ЯЁ]\.|[Тт]екст читает|[Мм]онтаж\.|[Дд]ир\. картины|[Ии]сполн\.|[Мм]ультипл\.|[Кк]онсульт\.|[Аа]ссист\.|[Дд]ирижер [А-ЯЁ]\.|[Гг]л\. ред|[Дд]убл\.|[Мм]уз\. ред|^(?:Режиссер|Оператор|Художник|Композитор|Постановка|Производство)\s)'
CRED = re.compile(MARK)
CRED_START = re.compile(r'^' + MARK)
CRED_STRICT = re.compile(r'(Авт\.\s?сцен|Авт\.-опер|Авт\.\s?текст|реж\.-опер|реж\.-пост|звукоопер|дир\. картины|худ\.-пост|В ролях|В роли|Библиограф)', re.I)
def clean(t): return re.sub(r'^[^А-ЯЁа-яёA-Za-z«“"(0-9]+', '', t.strip())
def is_head(LL, j):
    t = LL[j][1]
    if not re.search(r'[А-ЯЁ®][^а-яёa-z]{4,}?[.,]\s', t[:55]): return False
    win = ' '.join(LL[x][1] for x in range(j, min(j + 3, len(LL))))
    return bool(re.search(r'\b19\d\d\s*г[.,]', win))
_heads = {}
def all_heads(v, kind):
    """все головы статей серии в томе: [idx, num|None] в порядке документа; повреждённые номера выводятся по соседям"""
    key = (v, kind)
    if key in _heads: return _heads[key]
    LL = L(v); lim = len(LL); res = []
    kw = r'сатирическ' if kind == 'Фитиль' else r'юмористич'
    for idx, txt, k in LL:
        if idx >= lim: break
        head = txt[:60]
        if not re.search(r'[№N]', head): continue
        if re.search(r'[«“"]\s*Фитил|Фитиля»|Фитиль»|Фитиля”|Фитиля"', head): continue
        win = ' '.join(LL[x][1] for x in range(idx, min(idx + 3, len(LL))))
        if not re.search(kw, win) or not re.search(r'\b19\d\d\s*г', win): continue
        pre = re.split(r'[№N]', txt, maxsplit=1)[0]
        if not (re.search(r'(?:ФИТИЛЬ|ЕРАЛАШ|ИТИЛЬ|АЛАШ)\s*$', norm(pre).strip()) or re.search(r'[А-ЯЁ®][А-ЯЁ®]+[^а-яё]{0,14}$', pre[-20:]) or (len(pre) <= 25 and not re.search(r'[а-яё]', pre))): continue
        if re.match(r'^\s*[«“"]', txt) or re.search(r'19\d\d,\s*[№N]', head): continue
        m = re.search(r'[№N][°s]?\s*(\d{1,3})(?!\d)', head)
        res.append([idx, int(m.group(1)) if m else None])
    # вывод номеров по соседям: только когда оба соседа согласованы между собой (next == prev + 2)
    for q in range(len(res)):
        n = res[q][1]
        prev_ = res[q - 1][1] if q > 0 else None
        next_ = res[q + 1][1] if q + 1 < len(res) else None
        if prev_ is not None and next_ is not None and next_ == prev_ + 2 and n != prev_ + 1:
            res[q][1] = prev_ + 1
    # крайние позиции: по двум согласованным соседям с одной стороны
    for q in range(len(res)):
        n = res[q][1]
        if q + 2 < len(res) and res[q + 1][1] is not None and res[q + 2][1] == res[q + 1][1] + 1 and (n is None or n != res[q + 1][1] - 1) and (q == 0 or res[q - 1][1] is None or res[q - 1][1] != n):
            if n is None or abs(n - (res[q + 1][1] - 1)) > 1: res[q][1] = res[q + 1][1] - 1
        if q >= 2 and res[q - 1][1] is not None and res[q - 2][1] == res[q - 1][1] - 1 and (n is None or n != res[q - 1][1] + 1) and (q + 1 >= len(res) or res[q + 1][1] is None or res[q + 1][1] != n):
            if n is None or abs(n - (res[q - 1][1] + 1)) > 1: res[q][1] = res[q - 1][1] + 1
    _heads[key] = res
    return res
def find_head(v, kind, num):
    return [idx for idx, n in all_heads(v, kind) if n == num]
TITLE_OVERRIDE = {3379: (3, '120%.'), 3538: (0, '«01».')}   # OCR «<12 0 %*» / «<0 1»» — реконструкция по прозе сюжетов («план на 120%», «набирает номер 01»)
HEAD_OVERRIDE = {6868: ('v14', 3173)}   # титул «Фитиль № 281» ошибочен (Ф6): стаб = статья № 282 v14 @3173; № 281 (@3159) = cat6867
ACCEPT = {3387: 'печатное интро «трех сюжетов», в статье два блока (v3 @7494–7498, далее библиография) — принято как есть',
          4716: 'печатное интро «трех сюжетов», в статье два блока (первый — документальный в двух частях) — принято как есть',
          5519: 'стаб содержал только студию первого сюжета («Ленкинохроника» = @3121); статья № 185 идентифицирована головой @3117',
          6910: 'стаб = обрывок титров («Над выпуском работали…»); статья № 56 идентифицирована головой v15 @390',
          3538: 'заголовок первого сюжета «<0 1»» (OCR) → «01» по прозе сюжета («набирает номер 01»)',
          'shorter': 'стаб содержал титры/студии сюжетов — восстановленный текст без титров короче стаба (все сюжеты на месте)',
          6868: 'стаб = первый сюжет статьи № 282 («Добро под ногами…», v14 @3176); титул записи «Фитиль № 281» ошибочен — Ф6'}   # OCR «<12 0 %*» — реконструкция по прозе сюжета («выполняет план на 120%»)
def parse(v, h, kind='Фитиль', stub_first=None):
    LL = L(v)
    hy = h
    for j in range(h, min(h + 4, len(LL))):
        if re.search(r'\b19\d\d\s*г', LL[j][1]): hy = j; break
    series = [i for i, n in all_heads(v, kind) if i > h]
    e_series = series[0] if series else None
    e = None
    for j in range(hy + 1, min(h + 90, len(LL))):
        t = LL[j][1]
        if re.match(r'^\s*Библиограф', t, re.I): e = j; break
        if is_head(LL, j): e = j; break
    if e is None or (e_series is not None and e_series < e): e = e_series
    if e is None: return None, 'нет конца статьи'
    i = None; intro = None
    for j in range(h, e):
        m = re.search(r'(?:Киножурнал\s+)?[Сс]остоит из\s+(\S+)\s+(?:игровых\s+|мультипликационных\s+|коротких\s+)?(?:сюжет|новелл)\w*[.:]?', LL[j][1])
        if m: i = j; intro = m.group(0); nword = m.group(1); break
    if i is None: return None, 'нет интро «Состоит из…»'
    # потерянная голова следующей статьи внутри диапазона: строка с годом «19xx г.» после интро
    for j in range(i + 1, e):
        if re.search(r'\b19\d\d\s*г[.,]', LL[j][1]) and not CRED.search(LL[j][1]):
            e = j; break
    n = NUMW.get(nword.lower().replace('ё', 'е'))
    intro = re.sub(r'\s*:\s*$', '.', intro.strip())
    if not intro.endswith('.'): intro += '.'
    if n is None: return None, f'число сюжетов не распознано: «{intro}»'
    # заметка перед интро (короткая фраза без титров на предыдущей строке; напр. «Спецвыпуск для взрослых.»)
    note = None
    if i - 1 > h:
        pt = clean(LL[i - 1][1])
        prev_line = LL[i - 2][1].strip() if i - 2 > h else ''
        if pt and len(pt) < 60 and len(re.findall(r'[А-Яа-яЁё]', pt)) >= 4 and not CRED.search(pt) and re.match(r'^[А-ЯЁ]', pt) and not re.search(r'\b19\d\d', pt) \
           and not re.match(r'^[А-ЯЁ]\.\s?[А-ЯЁ]', pt) and not re.search(r'(;|,|\.)$', prev_line[-1:]) is None and not re.search(r'(звукоопер\.|;|,)$', prev_line):
            note = pt if pt.endswith('.') else pt + '.'
    lines = []
    for j in range(i + 1, e):
        t = clean(LL[j][1])
        if len(re.findall(r'[А-Яа-яЁё]', t)) < 3: continue
        if re.match(r'^\d*\s*Сов\.\s*худ\.\s*фильмы', t) or re.match(r'^Советские художественные фильмы', t): continue   # колонтитул
        t = re.sub(r'\s*[*<>■¦^]+\s*$', '', t)
        lines.append((j, t))
    sujets = []; cur = None; prev_open = False
    for k, (j, t) in enumerate(lines):
        is_cred = bool(CRED.search(t))
        mq = re.match(r'^(«[^»]{1,80}»|“[^”"]{1,80}[”"])\.\s+(.*)$', t)
        if is_cred:
            if CRED_START.match(t) or re.match(r'^[а-яё]', t) or re.match(r'^[А-ЯЁ3]\.\s?[А-ЯЁ][а-яё]', t) or prev_open:
                prev_open = bool(re.search(r'(;|,|\bреж\.|\bопер\.|\bхуд\.|сцен\.|[Аа]вт\.|\bи)$', t))
                if cur is not None: cur['lines'].append(j)
                continue
            pre = re.split(r'(?:\s|;)(?=' + MARK + ')', t, maxsplit=1)[0]
            prev_open = bool(re.search(r'(;|,|\bреж\.|\bопер\.|\bхуд\.|сцен\.|[Аа]вт\.|\bи)$', t))
            if pre.strip() and pre.strip() != t.strip() and len(pre) < 120:
                mqt = re.match(r'^(«[^»]{1,80}»|“[^”"]{1,80}[”"])', pre.strip())
                first = mqt.group(1) if mqt else re.split(r'(?<=[.!?…])\s+(?=[«“А-ЯЁ0-9(])', pre.strip(), maxsplit=1)[0].strip().rstrip(';')
                if not sujets and stub_first and first.endswith(('!', '?')):
                    # первый сюжет с «!»/«?» внутри названия: продлить заголовок по стабу, если продолжение — не студия
                    cands = [pre.strip()[:m.end()].strip() for m in re.finditer(r'[.!?…]+(?=\s|$)', pre.strip())]
                    for cnd in sorted(cands, key=len, reverse=True):
                        extra = cnd[len(first):]
                        if len(cnd) > len(first) and not re.search(r'(студи|ЦСДФ|фильм|кинохроник|«|“|им\. )', extra) \
                           and re.sub(r'\W', '', stub_first.lower()).startswith(re.sub(r'\W', '', cnd.lower())):
                            first = cnd; break
                if not first.endswith(('.', '!', '?', '…')): first += '.'
                cur = {'title': first, 'prose': [], 'lines': [j]}
                sujets.append(cur)
            elif cur is not None:
                cur['lines'].append(j)
            continue
        prev_open = False
        if mq:
            cur = {'title': mq.group(1) + '.', 'prose': [mq.group(2).strip()], 'lines': [j]}
            sujets.append(cur); continue
        # строка-заголовок без титров: короткая, без точки в конце, следующая строка — титры
        nxt = lines[k + 1][1] if k + 1 < len(lines) else ''
        if len(t) < 70 and not t.endswith(('.', '!', '?', '…')) and CRED_START.match(nxt):
            cur = {'title': t + '.', 'prose': [], 'lines': [j]}
            sujets.append(cur); continue
        if len(t) < 80 and t.endswith('.') and CRED_START.match(nxt) and len(re.findall(r'[.!?…](?:\s|$)', t)) <= 2:
            # «Название. Студия.» отдельной строкой, титры на следующей
            mqt = re.match(r'^(«[^»]{1,80}»|“[^”"]{1,80}[”"])', t)
            first = mqt.group(1) + '.' if mqt else re.split(r'(?<=[.!?…])\s+(?=[«“А-ЯЁ0-9(])', t, maxsplit=1)[0].strip()
            cur = {'title': first, 'prose': [], 'lines': [j]}
            sujets.append(cur); continue
        if cur is None:
            return None, f'проза без заголовка сюжета @{j}: «{t[:60]}»'
        cur['prose'].append(t); cur['lines'].append(j)
    return {'intro': intro, 'note': note, 'n': n, 'sujets': sujets, 'head': h, 'end': e, 'intro_line': i}, None
def join_prose(ps):
    out = ''
    for p in ps:
        if out and out.endswith('-') and re.match(r'^[а-яё]', p): out = out[:-1] + p
        elif out: out += ' ' + p
        else: out = p
    out = re.sub(r'(?<=[а-яё])\*', '', out)   # OCR-звёздочки внутри слов
    KEEP_L = {'куда', 'кто', 'что', 'как', 'где', 'когда', 'откуда', 'почему', 'зачем', 'по', 'кое', 'все', 'всё', 'чуть', 'из', 'за', 'кем', 'чем', 'какой', 'какая', 'какие', 'какое', 'сколько', 'едва', 'давным', 'мало', 'нет', 'да'}
    KEEP_R = {'нибудь', 'либо', 'то', 'ка', 'таки', 'де', 'за', 'под', 'над', 'нибуд', 'нибудь'}
    def fix(m):
        l, r = m.group(1), m.group(2)
        if l.lower() in KEEP_L or r.lower() in KEEP_R: return l + '-' + r
        return l + r
    return re.sub(r'([а-яёА-ЯЁ]+)- ([а-яё]+)', fix, out)
def assemble(p):
    parts = ([p['note']] if p['note'] else []) + [p['intro']]
    for s in p['sujets']:
        parts.append(s['title'])
        if s['prose']: parts.append(join_prose(s['prose']))
    return re.sub(r'\s+', ' ', ' '.join(parts)).strip()
def bad_title(t):
    if re.fullmatch(r'[\d\s%«»“”".!?…,]+', t): return False   # числовые названия («120%», «01», «100%»)
    letters = len(re.findall(r'[А-Яа-яЁё]', t))
    return letters < 2 or letters < 0.5 * len(re.sub(r'[\s.«»“”"!?…,()\-]', '', t))
def run():
    out = {}; report = []
    for c, r in enumerate(cat):
        if c in S or not r['annotation']: continue
        m = re.match(r'^(Фитиль|Ералаш)\s*№\s?(\d+)$', r['title'])
        if c == 6867: m = re.match(r'^(Фитиль) № (\d+)$', 'Фитиль № 281')   # титул разрушен OCR (Ф6); статья «Фитиль № 281» v14 @3159, стаб идентичен
        if not m: continue
        has_cred = bool(re.search(r'(Авт\.|Авт-|\bреж\.|Реж\.|\bопер\.|Опер\.|звукоопер|В ролях|дир\. картины|\bред\. [А-ЯЁ]\.|композ\.)', r['annotation']))
        if len(r['annotation']) >= 160 and not has_cred: continue
        v = r['source'].split('_')[0]; num = int(m.group(2)); kind = m.group(1)
        hits = find_head(v, kind, num)
        if c in HEAD_OVERRIDE: hits = [HEAD_OVERRIDE[c][1]]
        if not hits and num > 300 and v == 'v4': hits = find_head(v, kind, num // 10)   # cat3703 «Фитиль № 341» — OCR-титул, печатно № 34
        fallback = None
        if not hits:
            # запасной ход: голова по первому заголовку сюжета из стаба (между соседними головами серии)
            st0 = re.sub(r'^.*?[Сс]остоит из [^.:]+[.:]\s*', '', r['annotation']).strip()
            key = ' '.join(re.findall(r'[а-яёa-z0-9]+', st0.lower())[:2])
            LL = L(v)
            hs = all_heads(v, kind)
            lo = max([i for i, n in hs if n is not None and n < num], default=0)
            hi = min([i for i, n in hs if n is not None and n > num], default=len(LL))
            for idx, txt, k in LL:
                if idx <= lo or idx >= hi: continue
                if key and ' '.join(re.findall(r'[а-яёa-z0-9]+', txt.lower())[:2]) == key:
                    for back in range(idx - 1, max(idx - 9, 0), -1):
                        if re.search(r'\b19\d\d\s*г', LL[back][1]) and re.search(r'сатирическ|юмористич', ' '.join(LL[x][1] for x in range(max(back - 2, 0), back + 1))):
                            hh = back
                            while hh > 0 and not re.search(r'[№N]', LL[hh][1][:60]) and back - hh < 3: hh -= 1
                            fallback = hh; break
                    if fallback is not None: break
            if fallback is None:
                report.append((c, r['title'], v, 'голова не найдена')); continue
            hits = [fallback]
        h = hits[0]
        stub_first = re.sub(r'^.*?[Сс]остоит из [^.:]+[.:]\s*', '', r['annotation']).strip()
        p, err = parse(v, h, kind, stub_first)
        if p and c in TITLE_OVERRIDE: p['sujets'][TITLE_OVERRIDE[c][0]]['title'] = TITLE_OVERRIDE[c][1]
        if err:
            report.append((c, r['title'], v, f'@{h}: {err}')); continue
        probs = []
        if len(p['sujets']) != p['n']: probs.append(f"сюжетов {len(p['sujets'])} ≠ {p['n']}")
        for s in p['sujets']:
            if bad_title(s['title']): probs.append(f"нечитаемый заголовок «{s['title']}»")
        txt = assemble(p)
        if CRED_STRICT.search(txt): probs.append('маркер титров в тексте')
        stub = r['annotation']
        st = re.sub(r'^.*?[Сс]остоит из [^.:]+[.:]\s*', '', stub).strip()
        st = re.sub(r'^[^«“"А-ЯЁA-Z0-9]+', '', st)
        def w2(x): return ' '.join(re.findall(r'[а-яёa-z0-9]+', x.lower())[:2])
        st_first = w2(re.split(r'[.;]', st)[0]) if st else ''
        p_first = w2(p['sujets'][0]['title']) if p['sujets'] else ''
        ident = bool(st_first) and st_first == p_first
        if not ident: probs.append(f"идентичность: стаб «{st_first[:30]}» ≠ печать «{p_first[:30]}»")
        if len(txt) < len(stub): probs.append('текст короче стаба')
        if len(hits) > 1: probs.append(f'несколько голов: {hits}')
        if fallback is not None: probs.append(f'голова по стабу @{fallback}')
        rec = {'cat': c, 'title': r['title'], 'vol': v, 'head': h, 'end': p['end'], 'intro_line': p['intro_line'], 'n': p['n'], 'note': p['note'],
               'sujets': [{'title': s['title'], 'lines': s['lines'], 'prose_len': sum(len(x) for x in s['prose'])} for s in p['sujets']],
               'text': txt, 'stub': stub, 'probs': probs}
        out[str(c)] = rec
        if probs and c in ACCEPT:
            rec['accept'] = ACCEPT[c]; rec['probs_accepted'] = probs; rec['probs'] = []
        elif probs == ['текст короче стаба'] and len(p['sujets']) == p['n']:
            rec['accept'] = ACCEPT['shorter']; rec['probs_accepted'] = probs; rec['probs'] = []
        if rec['probs']: report.append((c, r['title'], v, f"@{h}: " + '; '.join(rec['probs'])))
    OUT = _sys.argv[2] if len(_sys.argv) > 2 else 'work/p6_k4_parsed.json'
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    clean_ = [k for k, v in out.items() if not v['probs']]
    print('parsed', len(out), 'clean', len(clean_), 'flagged', len(out) - len(clean_), 'unparsed', len(report) - (len(out) - len(clean_)))
    for x in report: print('REPORT', *x, sep=' | ')
if __name__ == '__main__': run()
