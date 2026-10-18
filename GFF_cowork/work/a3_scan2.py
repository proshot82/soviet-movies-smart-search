# -*- coding: utf-8 -*-
"""П4 a3 — LEAD-срезы: титровый блок от начала аннотации.
Предложения делятся с учётом инициалов; режем цепочку титровых предложений."""
import json, re
from collections import Counter

cat = json.load(open('state/catalog_f5_a2.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
strays = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
A1 = {388,464,470,2024,2525,2739,3318,5244,5890,6966,3554,1186,
      1184,4767,5456,5468,5606,5645,5894,6334,6335,6546,7230,7231}

ABBR = {'им', 'Им', 'гос', 'Гос', 'засл', 'арт', 'худ', 'рук', 'руков', 'дир', 'реж',
        'ст', 'мл', 'проф', 'акад', 'т', 'тт', 'кап', 'п', 'о', 'др', 'дубл', 'исп', 'г', 'с', 'обл', 'оз', 'р'}
def sentences(text):
    """Границы предложений с учётом инициалов и сокращений. Возвращает список (start, end)."""
    bounds = [0]
    for m in re.finditer(r'[.!?…]+[»)]?\s+', text):
        end = m.end()
        prev = text[:m.start()].rstrip()
        wm = re.search(r'([А-ЯЁа-яёA-Za-z]+)$', prev)
        w = wm.group(1) if wm else ''
        if len(w) == 1 and (w.isupper() or w.isdigit()):   # инициал (в т.ч. OCR-цифра 3=З)
            continue
        if not w and re.search(r'\d$', text[:m.start()].rstrip()):
            continue
        if len(w) == 2 and w[0].isupper() and w[1].islower():  # двухбуквенный инициал (Ан.)
            continue
        if w in ABBR:
            continue
        nxt = text[end:end+1]
        if nxt and not (nxt.isupper() or nxt in '«(0123456789'):
            continue
        bounds.append(end)
    bounds.append(len(text))
    return [(bounds[i], bounds[i+1]) for i in range(len(bounds)-1) if bounds[i+1] > bounds[i]]

ORK_START = re.compile(r'^(?:Государственн|Гос\.|Большой\s|Симфоническ|Эстрадн|Академическ|Заслуженн|Инструментальн|Камерн|Духов|Русск(?:ий|ая)\s+народн|Оркестр\s|Ансамбль\s|Хор\s|Капелла|Джаз|Вокальн|Струнн|Образцов)')
ORK_NOUN = re.compile(r'(оркестр|ансамбл|хор(?:\s|а|у|ом)|капелл|квартет|группа|квинтет)', re.I)
CREDIT_PATTERNS = [
 re.compile(r'^Фильм\s+дублирован'), re.compile(r'^Дублирован\s'),
 re.compile(r'^Реж(?:иссер)?\.?\s*дубл'),
 re.compile(r'^Роли\s+(?:озвучивали|дублировали|исполняют)'),
 re.compile(r'^Текст(?:\s+песен)?\s+(?:читает|читают|поет|исполняет)|^Текст\s+от\s+автора'),
 re.compile(r'^Песн[юиь][\s,]|^Вокальн\w+\s+парти|^Парти[ию]\s.{0,30}исполня|^Музыкальное\s+сопровождение|^Соло\s+на\s'),
 re.compile(r'^В\s+фильме\s+(?:снимал|снимаются|снята|использован|звучат|звучит|принимал|участв)'),
 re.compile(r'^В\s+съемках\s'), re.compile(r'^Съемки\s+(?:проводились|происходили|велись)'),
 re.compile(r'^Высшие\s+курсы\s+сценаристов'),
 re.compile(r'^(?:Первое|Второе|Третье|Четвертое)?\s*[Тт]ворческое\s+объединение'),
 re.compile(r'^Лаборатория\s+киностуди'),
 re.compile(r'^Танц\w+\s+(?:в\s+исполнении|исполня)|^Балетмейстер|^Дирижер\b|^Солист'),
 re.compile(r'^Стихи\s.{0,40}(?:читает|исполня|в\s+исполнении)'),
 re.compile(r'^(?:Худ|Муз)\.?\s*руководитель'), re.compile(r'^Запись\s+музыки'),
 re.compile(r'^Исп\.\s*песен'), re.compile(r'^Исполнител[ьи]\s+(?:песен|главных|вокальн)'),
 re.compile(r'^В\s+фильме\s+(?:исполнены|танцуют|поют|занят)'),
]
PLOT_VERB = re.compile(r'\b(мечта|реша|хоче|хотя|приезжа|прихо|узна|влюб|собира|отправ|попада|начина|станов|оказыва|живет|живут|работа|погиба|спаса|помога|встреча|уезжа)')
def is_credit(sent):
    s = sent.strip()
    if ORK_START.match(s) and ORK_NOUN.search(s[:120]):
        if PLOT_VERB.search(s) and not re.search(r'(дирижер|руководител|управлени|солист|исполня|запись)', s, re.I):
            return None
        return 'оркестр'
    for p in CREDIT_PATTERNS:
        if p.match(s):
            if p.pattern.startswith('^Фильм') or p.pattern.startswith('^Дублирован') or 'дубл' in p.pattern:
                return 'дубляж'
            if 'озвучивали' in p.pattern: return 'роли-озвучания'
            return 'произв.-справка'
    return None

PLOT_START = re.compile(r'^(По\s|Экранизация|О\s|Об\s|На\s+темы|В\s+основу|Состоит|История|Рассказ|Фильм\s+(?:посвящен|рассказывает|о\s)|Действие|Содержание|Авторы\s+и\s+содержание|Жил|Из\s|\d{4}|«)')
CONC = re.compile(r'(концерт|опера|балет|ревю|музыкальн|эстрадн|представление|бенефис|мюзикл)', re.I)

res, points, doubts, log, manual_conc = {}, [], [], [], []
for i, r in enumerate(cat):
    if i in strays or i in A1: continue
    t = r.get('annotation')
    if not t: continue
    sents = sentences(t)
    classes, cut_end = [], 0
    for (s0, s1) in sents:
        sent = t[s0:s1]
        k = is_credit(sent)
        if k:
            classes.append(k); cut_end = s1
        else:
            break
    if not classes: continue
    lead = t[:cut_end]
    rem = t[cut_end:].strip()
    genre = r.get('genre') or ''
    if CONC.search(genre):
        manual_conc.append((i, genre, lead[:150], rem[:80])); continue
    if len(rem) < 40 and not (len(rem) >= 15 and re.match(r'(По\s|Экранизация|Триптих|О\s|Об\s)', rem)):
        points.append((i, 'лид-всё [' + '+'.join(classes) + ']', t[:220])); continue
    if len(lead) > 1500:
        doubts.append((i, 'лид-длинный', lead[:200])); continue
    if not (rem[0].isupper() or rem[0].isdigit() or rem[0] in '«…('):
        doubts.append((i, 'остаток-не-проза', lead[-80:] + ' ||| ' + rem[:80])); continue
    res[str(i)] = {'lead': lead, 'tail': None, 'class': 'лид:' + '+'.join(classes)}
    log.append((i, '+'.join(classes), lead[:100], rem[:70]))

json.dump({'cut': res}, open('work/a3_res_auto2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = open('work/a3_review2.txt', 'w', encoding='utf-8')
cc = Counter(v['class'] for v in res.values())
print('=== КЛАССЫ ===', file=out)
for k, v in cc.most_common(30): print(f'{v:5d}  {k}', file=out)
print(f'\nИТОГО авто: {len(res)}; лид-всё: {len(points)}; сомнительных: {len(doubts)}; концертных-вручную: {len(manual_conc)}', file=out)
print('\n=== ЛИД-ВСЁ (аннотация целиком титры) ===', file=out)
for i, k, ctx in points: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== СОМНИТЕЛЬНЫЕ ===', file=out)
for i, k, ctx in doubts: print(f'cat{i} [{k}] {ctx!r}', file=out)
print('\n=== КОНЦЕРТНЫЕ ЖАНРЫ (ручной разбор) ===', file=out)
for i, g, lead, rem in manual_conc: print(f'cat{i} [{g}] LEAD: {lead!r} ||| ОСТ: {rem!r}', file=out)
print('\n=== ПРОИЗВ.-СПРАВКИ и РЕДКИЕ (все) ===', file=out)
for i, k, lead, rem in log:
    if 'произв' in k or '+' in k:
        print(f'cat{i} [{k}]: {lead!r} ||| {rem[:60]!r}', file=out)
import random
random.seed(11)
print('\n=== ВЫБОРКИ по классам (по 25) ===', file=out)
for klass in ('оркестр', 'дубляж', 'роли-озвучания'):
    sel = [x for x in log if x[1] == klass]
    print(f'--- {klass}: всего {len(sel)}', file=out)
    for i, k, lead, rem in random.sample(sel, min(25, len(sel))):
        print(f'cat{i}: {lead[:95]!r} ||| {rem[:60]!r}', file=out)
out.close()
print('auto:', len(res), 'lead-all:', len(points), 'doubts:', len(doubts), 'concert-manual:', len(manual_conc))
