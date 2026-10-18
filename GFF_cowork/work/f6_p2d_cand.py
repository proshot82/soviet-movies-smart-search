# -*- coding: utf-8 -*-
"""Ф6-П2д (б): список кандидатов на буквенные OCR-ошибки внутри кириллических слов аннотаций (НИЧЕГО не применяет).
Вход: state/catalog_f6_p2e.json (после П2е). Выход: veto/П2е_кандидаты_остаток_OCR_буквы.xlsx, work/f6_p2d_cand.json.
Исходная версия по каталогу П2д — veto/П2д_кандидаты_OCR_буквы.xlsx (auto-строки применены в П2е).
Кандидат = слово вне словаря pymorphy3 (строчное, ≥4 букв; или с прописной в начале предложения), для которого есть
словарная форма на расстоянии одной правки (замена/вставка/удаление/перестановка), разрыв на два словарных слова
или две замены по OCR-парам. Метка auto: ровно один кандидат, искажённая форма встречается в корпусе 1 раз, и (правка — OCR-пара и кандидат встречается в корпусе ≥1 раз,
или кандидат встречается ≥3 раз, или разрыв склеенных слов с однобуквенным предлогом/союзом/глагольной формой/местоимением)."""
import json, re, collections, itertools, sys
import pymorphy3, openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
morph = pymorphy3.MorphAnalyzer()
cat = json.load(open('state/catalog_f6_p2e.json', encoding='utf-8'))
ALPH = 'абвгдежзийклмнопрстуфхцчшщъыьэюя'
OCR = {('п', 'н'), ('н', 'и'), ('и', 'п'), ('л', 'п'), ('л', 'д'), ('о', 'е'), ('о', 'а'), ('с', 'е'), ('з', 'в'), ('т', 'г'), ('ц', 'и'), ('ч', 'и'),
       ('й', 'и'), ('ш', 'щ'), ('б', 'в'), ('б', 'о'), ('ь', 'ъ'), ('ь', 'ы'), ('к', 'х'), ('з', 'э'), ('с', 'о'), ('р', 'п'), ('у', 'х'), ('м', 'ы'),
       ('т', 'ч'), ('ц', 'п'), ('щ', 'ц'), ('ю', 'о'), ('я', 'л'), ('в', 'з'), ('г', 'р'), ('д', 'л'), ('т', 'п'), ('о', 'с'), ('е', 'с')}
OCR |= {(b, a) for a, b in OCR}
ONE = set('виаскуояж')
PREFIX = set('кино теле радио фото авто аэро полит труд сан губ бело красно пере электро гидро агит гос парт проф спец зам нар сов хоз зоо мото вело авиа микро макро ультра супер контр анти лже само все полу обще много мало глав сель рай обл гор зав физ хим био гео мед тех энерго металло машино лесо рыбо хлебо нефте газо угле торф стекло железо водо тепло свето звуко цвето мульт лит муз худ ком дет юн пион ново старо старо мелко крупно высоко низко быстро тихо скоро долго кратко средне равно разно одно дву двух трех четырех пяти много едино обще плоско широко узко дально ближне глубоко вне около пред после сверх меж между под над при про пре раз рас без бес воз вос из ис низ нис через чрез чере кара кызыл ак кок сары'.split())
SUFFIX = set('ство ства ству ством ние ния нию нием ния ость ости остью ка ки ку кой ок ков ец ца цы ник ника ники тель теля тели чик щик ист иста исты изм изма ся сь'.split())
FUNC = set('свое свои свою своей своих ему она они оно этот эта это эту тут там уже еще ещё все всё меня тебя себя него нее ее его их нас вас'.split())
def verbish(w):
    return any(p.tag.POS in ('VERB', 'INFN', 'GRND', 'PRTS') and p.score >= 0.2 for p in morph.parse(w))
def split_ok(c):
    a, b = c.split(' ')
    if (len(a) == 1 and a in ONE) or (len(b) == 1 and b in ONE): return True
    if a in FUNC or b in FUNC: return True
    if len(a) >= 4 and len(b) >= 4 and (verbish(a) or verbish(b)): return True
    return False
KN = {}
def known(w):
    if w not in KN: KN[w] = morph.word_is_known(w)
    return KN[w]
def is_namey(w):
    return any(any(x in p.tag for x in ('Name', 'Surn', 'Patr', 'Geox')) for p in morph.parse(w))
freq = collections.Counter(); occ = collections.defaultdict(list)
for i, r in enumerate(cat):
    a = r['annotation']
    if not a: continue
    for m in re.finditer(r'[А-ЯЁа-яё]+', a):
        w = m.group(0); freq[w] += 1; occ[w].append((i, m.start(), m.end()))
def cands(w):
    out = {}
    lw = w
    for k in range(len(lw)):                                   # замена
        for ch in ALPH:
            if ch == lw[k]: continue
            c = lw[:k] + ch + lw[k + 1:]
            if known(c): out.setdefault(c, ('замена', f'{lw[k]}→{ch}', (lw[k], ch) in OCR))
    for k in range(len(lw)):                                   # удаление
        c = lw[:k] + lw[k + 1:]
        if len(c) >= 3 and known(c): out.setdefault(c, ('удаление', f'−{lw[k]}', lw[k] in 'ьъй' or (k > 0 and lw[k] == lw[k - 1])))
    for k in range(len(lw) + 1):                               # вставка
        for ch in ALPH:
            c = lw[:k] + ch + lw[k:]
            if known(c): out.setdefault(c, ('вставка', f'+{ch}', ch in 'ьъ'))
    for k in range(len(lw) - 1):                               # перестановка
        c = lw[:k] + lw[k + 1] + lw[k] + lw[k + 2:]
        if c != lw and known(c): out.setdefault(c, ('перестановка', f'{lw[k]}{lw[k + 1]}→{lw[k + 1]}{lw[k]}', False))
    for k in range(1, len(lw)):                                # разрыв на два слова
        a, b = lw[:k], lw[k:]
        if not ((len(a) >= 2 or a in ONE) and (len(b) >= 2 or b in ONE)): continue
        if a in PREFIX or b in SUFFIX: continue
        if known(a) and known(b) and not is_namey(a) and not is_namey(b):
            out.setdefault(a + ' ' + b, ('разрыв', f'{a}|{b}', False))
    if not out and len(lw) >= 7:                               # две замены по OCR-парам
        pos = range(len(lw))
        for k1, k2 in itertools.combinations(pos, 2):
            for c1 in ALPH:
                if (lw[k1], c1) not in OCR: continue
                for c2 in ALPH:
                    if (lw[k2], c2) not in OCR: continue
                    c = list(lw); c[k1] = c1; c[k2] = c2; c = ''.join(c)
                    if known(c): out.setdefault(c, ('две замены', f'{lw[k1]}→{c1},{lw[k2]}→{c2}', True))
    return out
rows = []
for w, n in freq.items():
    if len(w) < 4: continue
    lower = w.islower(); capital = w[0].isupper() and w[1:].islower()
    if not (lower or capital): continue
    if known(w) or (capital and known(w.lower())): continue
    if '-' in w: continue
    if capital:
        # только в начале предложения и только если есть словарный не-именной кандидат (строчный); фамильные суффиксы исключены
        if re.search(r'(ов|ова|ову|овым|ове|ев|ева|еву|евым|ин|ина|ину|иным|ский|ская|ского|ской|скую|цкий|цкая|цкого|ых|их|енко|ук|юк|ян|яна|яну|дзе|швили|ич|ича|ичу|ой|ый|ая|ое|ые|ского|ских)$', w): continue
        i, s, e = occ[w][0]; a = cat[i]['annotation']
        if not (s == 0 or re.search(r'[.!?…»]\s$|\n$', a[:s])): continue
        cc = {k: v for k, v in cands(w.lower()).items() if not is_namey(k.split()[0])}
        if not cc: continue
        cc = {k[0].upper() + k[1:]: v for k, v in cc.items()}
    else:
        cc = cands(w)
    def prio(kv):
        c, (kind, ed, ocr) = kv
        if kind == 'разрыв':
            return 0 if split_ok(c) else 3
        if kind == 'замена' and ocr: return 0
        if kind in ('вставка', 'удаление', 'перестановка'): return 1 if ocr else 2
        if kind == 'замена': return 2
        return 4
    ranked = sorted(cc.items(), key=lambda kv: (prio(kv), -freq.get(kv[0], 0) - freq.get(kv[0].capitalize(), 0), kv[0]))
    # разрыв с однобуквенным предлогом/союзом вытесняет «удаление» той же буквы
    if ranked and ranked[0][1][0] == 'удаление':
        sp = [kv for kv in ranked if kv[1][0] == 'разрыв' and prio(kv) == 0]
        if sp: ranked = sp + [kv for kv in ranked if kv not in sp]
    top = ranked[0] if ranked else None
    ncand = len(ranked)
    cf = (freq.get(top[0], 0) + freq.get(top[0].capitalize(), 0)) if top else 0
    auto = bool(top) and ncand == 1 and n == 1 and top[1][0] != 'две замены' and not capital and (
        (top[1][0] == 'разрыв' and prio(top) == 0) or (top[1][2] and cf >= 1) or cf >= 3)
    for (i, s, e) in occ[w][:3]:
        a = cat[i]['annotation']
        rows.append({'cat': i, 'title': cat[i]['title'], 'source': cat[i]['source'], 'word': w, 'freq_word': n,
                     'context': a[max(0, s - 45):s] + '[' + w + ']' + a[e:e + 45],
                     'candidate': top[0] if top else '', 'edit': f'{top[1][0]} {top[1][1]}' if top else '', 'ocr_pair': top[1][2] if top else '',
                     'freq_candidate': cf, 'n_candidates': ncand, 'all_candidates': '; '.join(f'{k} ({v[0]} {v[1]})' for k, v in ranked[:6]),
                     'auto': 'да' if auto else ('нет' if top else '—'), 'kind': 'прописная (начало предложения)' if capital else 'строчная'})
# склейка: два соседних строчных слова вне словаря, слитно — словарное слово (потерян дефис переноса: «красноар мейцев»)
for i, r in enumerate(cat):
    a = r['annotation']
    if not a: continue
    for m in re.finditer(r'(?<![А-ЯЁа-яё-])([а-яё]{2,}) ([а-яё]{2,})(?![А-ЯЁа-яё-])', a):
        w1, w2 = m.group(1), m.group(2)
        if known(w1) or known(w2) or not known(w1 + w2): continue
        rows.append({'cat': i, 'title': r['title'], 'source': r['source'], 'word': w1 + ' ' + w2, 'freq_word': 1,
                     'context': a[max(0, m.start() - 45):m.start()] + '[' + m.group(0) + ']' + a[m.end():m.end() + 45],
                     'candidate': w1 + w2, 'edit': 'склейка (потерян дефис переноса)', 'ocr_pair': True,
                     'freq_candidate': freq.get(w1 + w2, 0), 'n_candidates': 1, 'all_candidates': w1 + w2, 'auto': 'да', 'kind': 'склейка'})
rows.sort(key=lambda r: (r['auto'] != 'да', r['auto'] == '—', r['cat']))
json.dump(rows, open('work/f6_p2d_cand.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'кандидаты'
hdr = ['cat', 'title', 'source', 'слово (как в каталоге)', 'встреч. слова', 'контекст', 'кандидат', 'правка', 'OCR-пара', 'встреч. кандидата', 'число кандидатов', 'все кандидаты (до 6)', 'auto', 'тип', 'решение владельца']
ws.append(hdr)
for r in rows:
    ws.append([r['cat'], r['title'], r['source'], r['word'], r['freq_word'], r['context'], r['candidate'], r['edit'], 'да' if r['ocr_pair'] is True else ('нет' if r['ocr_pair'] is False else ''), r['freq_candidate'], r['n_candidates'], r['all_candidates'], r['auto'], r['kind'], ''])
for c in ws[1]: c.font = Font(bold=True); c.fill = PatternFill('solid', fgColor='DDDDDD')
widths = [6, 28, 12, 18, 7, 70, 18, 16, 8, 8, 8, 50, 6, 14, 16]
for k, w in enumerate(widths): ws.column_dimensions[openpyxl.utils.get_column_letter(k + 1)].width = w
ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
green = PatternFill('solid', fgColor='E2F0D9')
for row in ws.iter_rows(min_row=2):
    if row[12].value == 'да':
        for c in row: c.fill = green
s2 = wb.create_sheet('правило и сводка')
n_auto = sum(1 for r in rows if r['auto'] == 'да'); n_man = sum(1 for r in rows if r['auto'] == 'нет'); n_none = sum(1 for r in rows if r['auto'] == '—')
for line in [['Остаток кандидатов на буквенные OCR-ошибки внутри кириллических слов аннотаций после П2е (каталог state/catalog_f6_p2e.json). НИЧЕГО ИЗ ЭТОГО ФАЙЛА НЕ ПРИМЕНЕНО; auto-строки предыдущей версии применены пакетом П2е (veto/ВЕТО_Ф6_П2е.md), 20 из них исключены как ложные — правило auto здесь оставлено для справки, повторно auto НЕ применять без ручного просмотра.'],
             ['Кандидат: слово вне словаря pymorphy3 (строчное ≥4 букв, без дефиса; или с прописной в начале предложения), имеющее словарную форму на расстоянии одной правки, разрыв на два словарных слова или две замены по OCR-парам.'],
             ['auto = «да»: ровно один кандидат; искажённая форма встречается в корпусе 1 раз; и либо (правка — типичная OCR-пара: п↔н, и↔н, о↔е, с↔е, з↔в, т↔г, ц↔и… — и кандидат встречается в корпусе ≥1 раз), либо кандидат встречается ≥3 раз, либо разрыв склеенных слов (однобуквенный предлог/союз, глагольная форма или местоимение); слова с прописной и «две замены» — никогда auto.'],
             ['auto = «нет»: кандидат есть, но правило не выполнено (несколько кандидатов / редкая правка) — решение вручную. «—»: кандидата нет (слово вне словаря: редкое/иноязычное/сильно искажённое) — только к сведению.'],
             ['Предлагаемая процедура: владелец подтверждает правило auto (или правит список) → пакет Ф6-П2е применяет строки auto=да и вручную отмеченные; всё с вето-списком.'],
             [f'Строк: {len(rows)}; auto=да: {n_auto}; auto=нет: {n_man}; без кандидата: {n_none}.']]:
    s2.append(line)
s2.column_dimensions['A'].width = 160
wb.save('veto/П2е_кандидаты_остаток_OCR_буквы.xlsx')
print(f'строк {len(rows)}; auto {n_auto}; manual {n_man}; none {n_none}')
