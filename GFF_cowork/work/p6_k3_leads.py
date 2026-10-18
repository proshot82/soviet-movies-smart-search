# -*- coding: utf-8 -*-
"""k3: лид-остатки П4 (списки ролей с инициалов, оркестры/ансамбли, дубляж) — поиск границы прозы. v3"""
import json, re, sys
cat = json.load(open('state/catalog_f5_k2.json', encoding='utf-8'))
al = json.load(open('state/alignment_v17.json', encoding='utf-8'))
S = {a['cat_pos'] for a in al if a.get('xlsx_row') is None}
I = r'[А-ЯЁA-Z3]'
INIT = rf'{I}[\.\-]?\s?'
INITP = rf'{I}[\.\-]\s?'            # инициал с точкой/дефисом (OCR «К-»)
SURN = r"[А-ЯЁA-Z][а-яёa-z\-']+(?:-\s?[А-ЯЁ]?[а-яё]+)?"
FIRST = r"[А-ЯЁ][а-яё]+"
ITEM_A = re.compile(rf"^(?:дубл\.\s*)?(?:{INITP}){{1,3}}(?:и\s(?:{INITP}){{1,2}})?{SURN}(?:\s[а-яё]+)?$")   # «И. Фамилия», «О. и И. Тамировы», «Г. Светла ни»
ITEM_A2 = re.compile(rf"^(?:дубл\.\s*)?{I}\s{SURN}$")                                                   # «Н Горлов» (точка утрачена OCR)
ITEM_B = re.compile(rf"^(?:дубл\.\s*)?(?:{FIRST}\s)?{SURN}$")                                            # «Хельмут Шрайбер», «Истомин»
def is_list(c):
    c = c.strip().rstrip('./;,').strip()
    c = re.sub(r'\([^)]*\)', '', c)          # роли в скобках
    c = re.sub(r'\bи\s+др(?:\.|угие)\s*$', '', c)
    items = [x.strip().strip('.,') for x in re.split(r'[,;]', c) if x.strip()]
    if not items: return False
    a = sum(1 for x in items if ITEM_A.match(x) or ITEM_A2.match(x))
    b = sum(1 for x in items if ITEM_B.match(x))
    if len(items) == 1: return a == 1
    return (a + b) >= max(2, int(0.8 * len(items))) and (a >= max(1, len(items) // 2) or ((a + b) == len(items) and len(items) >= 3))
pat_cast = re.compile(r'^(?:[А-ЯЁ]\.\s?){1,2}[А-ЯЁ][а-яё\-]+(?:\s\([^)]{1,60}\))?,\s(?:[А-ЯЁ]\.\s?){1,2}[А-ЯЁ][а-яё\-]+')
pat_orch = re.compile(r'^(?:[А-ЯЁ][а-яё\-]+\s){0,5}(оркестр|ансамбль|хор|капелла)\b', re.I)
STRONG = re.compile(r'(дирижер|дириж\.|дубл\.|дублирован|дубляж|озвучива|худ\. рук|руководител|руководств|соло на|песню исполня|песни исполня|исполнит[.,] песен|исполнители [а-я]+ песен|текст читае?ю?т|текст перевел|от автора —|балетмейстер|постановщик танц|солист[ыа]?\s*(?:балета\s*)?:|солист [А-ЯЁ]\.|под управлением|под упр\.|худож\. рук|цветоустановщи|худ\.-фотограф|инженеры|звукоопер|опер\.|ассист|монтаж\.|композ\.|авт\. текст|авт\. сцен|реж\.|худ\.-|костюм\.|грим\.|декор\.|\bред\.|дир\. картины|комб\. съемки|мастер по свету|мастер-светотехник|консульт|роли озвучива|роли дублир|в ролях|каскадер|клоуны:|трюки выполня|снимались|снимаются|принимал[иа]? участие|приняли участие|принимают участие|участвовали|участвует|благодарит|благодарность|работали:|использован[аы]? музыка|использован вальс|работы скульптора|кадры из|запись музыки|музыка в исполнении|играет ансамбль|хормейстер|балет [А-Я][а-я]+ского|квартет|над выпуском работали|да[ею]т интервью|на стихи [А-ЯЁ]|романс на стихи|^артисты\b|^(?:народный\s)?театр\b|в фильм включены|в массовых сценах|балалаечник|гармонист|\bхуд\.|муз\. ред|адм\. группа|гл\. консульт)', re.I)
ENS = re.compile(r'(оркестр|ансамбл|\bхор\b|капелл|квартет|труппа|коллектив)', re.I)
VERB = re.compile(r'\b(мечта|решает|решил|приезжа|отправля|живет|работает|узна|приглашают|выступлени|становится|получил|любит)', re.I)
NOSPLIT = {'Дж','Вл','Св','Ст','Ал','Ев','им','г','гг','ул','т','тт','пос','с','д','кн','ок'}
def chunks(text):
    """список (фрагмент, смещение начала) — rest берётся по смещению, чтобы OCR-мусор между фразами уходил в лид"""
    out = []; start = 0
    for m in re.finditer(r'[.!?…]\s+(?:[*/]\s*)?(?=[А-ЯЁ0-9«„"(A-Z])', text):
        before = text[start:m.start()]
        tok = re.search(r'([А-ЯЁA-Za-zа-яё3]+)$', before)
        tok = tok.group(1) if tok else ''
        if re.fullmatch(r'[А-ЯЁA-Z3]', tok) or tok in NOSPLIT:
            continue
        out.append((text[start:m.end()].rstrip(), start)); start = m.end()
    out.append((text[start:], start))
    return [c for c in out if c[0].strip()]
def titular(ch, k):
    c = ch.strip()
    if is_list(c): return 'list'
    if STRONG.search(c): return 'strong'
    if ENS.search(c) and (k == 0 or len(c) < 70) and not VERB.search(c): return 'ens'
    if re.match(rf'^(?:{INIT}){{0,2}}{SURN}(?:\s*\([^)]*\))?[,;]$', c) and len(c) < 40: return 'name'
    if re.match(r'^(?:[А-ЯЁ][а-яё]+\s){0,3}(ССР|СССР|УССР|РСФСР)[.,;]?$', c): return 'tail'
    return None
NOCUT = {4396, 5048, 1344, 4014}
OVERRIDE = {4057: 'В поисках украденных денег'}   # явная граница прозы (OCR-мусор «/» в лиде)   # сюжет/концертное содержание — не трогать
SPECIAL = {3774, 3873, 4951, 5246}  # restore по печати (k3 §restore)
out = {}
review = []
for i, r in enumerate(cat):
    if i in S or not r['annotation'] or i in NOCUT or i in SPECIAL: continue
    a = r['annotation']
    if not (pat_cast.match(a) or pat_orch.match(a)): continue
    if i in OVERRIDE:
        rest = a[a.index(OVERRIDE[i]):]; lead = a[:len(a) - len(rest)]
        out[i] = {'lead': lead, 'rest': rest, 'ok': True, 'rules': ['override']}
        review.append((i, 'OK', 'override', lead[-60:], '||', rest[:80])); continue
    ch = chunks(a)
    k = 0; rules = []
    while k < len(ch):
        t = titular(ch[k][0], k)
        if not t: break
        rules.append(t); k += 1
    if k == 0 or k >= len(ch):
        review.append((i, 'NOCUT' if k == 0 else 'ALL-TITULAR', a[:160])); continue
    rest = a[ch[k][1]:]
    lead = a[:ch[k][1]]
    assert a == lead + rest and rest == rest.lstrip()
    ok = len(rest) >= 40 and re.match(r'^[А-ЯЁ0-9«„"(…]', rest)
    out[i] = {'lead': lead, 'rest': rest, 'ok': bool(ok), 'rules': rules}
    review.append((i, 'OK' if ok else 'SHORT', '+'.join(rules), lead[-60:].replace('\n', ' '), '||', rest[:80].replace('\n', ' ')))
json.dump({str(k): v for k, v in out.items()}, open('work/p6_k3_leads_draft.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if len(sys.argv) > 1 and sys.argv[1] == 'all':
    for x in review: print(*x, sep=' | ')
else:
    for x in review:
        if x[1] != 'OK' or int(x[0]) in {5473,6755,6834,6631,5379,5611,7188,6273,6856,4704,3830,3940,6802,7117,6930,7192,3434,4057,4478,4477,4980,6030,6087,6143,4669,5070,6516,4938,5640}:
            print(*x, sep=' | ')
print('candidates', len(out), 'ok', sum(1 for v in out.values() if v['ok']))
