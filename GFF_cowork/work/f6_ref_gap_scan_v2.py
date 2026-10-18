# -*- coding: utf-8 -*-
"""Ф6-П3а: печатный «скан пропусков» — строки статьи, не покрытые аннотацией каталога.
Для каждой записи: область статьи [h, E), где E — следующая *настоящая* голова (метраж в строке / прописной титул + титры
в следующих строках), а не просто головоподобная строка (ложные головы: «В РСФСР фильм не демонстрировался.» и т.п.).
Покрытие строки аннотацией — по пробам нормализованного текста (устойчиво к переносам/правкам П2г).
Классы непокрытых строк: PRE-* (до первой покрытой), GAP-* (между покрытыми), POST-* (после последней покрытой);
суффикс — kind(): PROSE / CRED / BIB / PRIZE / JUNK / HEAD(ложная голова) / DUP.
Выход: work/f6_ref_gap_scan_v2.json, work/f6_ref_gap_review_v2.txt."""
import sys, json, re
sys.path.insert(0, 'work')
import f6_p2_lib as L
from collections import Counter
src = open('work/f6_p3a_tail_scan.py', encoding='utf-8').read()
exec(src[src.index('CONCERT = '):src.index('res = []')])   # CONCERT, JUNKLINE, PUNCT_OK, nmap, verified_head, PRIZE2, is_junk, is_headlike
cat = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
ts = {x['cat']: x for x in json.load(open('work/f6_p3a_tail_scan.json', encoding='utf-8'))}
loc0 = json.load(open('work/f6_p2_ann_loc.json', encoding='utf-8'))
BC = 1628
loc = {str(i): loc0[str(i if i < BC else i - 1)] for i in range(7174) if i != BC and str(i if i < BC else i - 1) in loc0}
METR = re.compile(r'\d+\s?ч[.,„]|мтр\. неизв|\d+(?:,\d)?\s?м[,.]|\d+ л[,.]')
CREDNEXT = re.compile(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав[тг]|Авт|Реж|Сцен|Автор|Пост\.|Опер|В ролях|Худ\.|Композ)')
def strip_junk(s):
    """снять орнамент-мусор в начале головы: не-буквы и 1–2-буквенные обрывки перед прописным титулом («fl Л1 ^ БЕЖИН ЛУГ»)"""
    return re.sub(r'^(?:[^А-ЯЁа-яё]+|[А-ЯЁа-яё]{1,2}(?=[^А-ЯЁа-яё]))+', '', s.lstrip())
def caps_title(s):
    """прописной титул в начале строки (после снятия мусора): ≥4 прописных букв, слово ≥3 букв; после титула не идёт строчное слово
    без знака препинания («В РСФСР фильм…» — не титул)"""
    s2 = strip_junk(s)
    m = re.match(r'^((?:[А-ЯЁ]{2,}|[А-ЯЁ](?![а-яё]))(?:[\s\-—,!?:;«»()\'’.]+(?:[А-ЯЁ]{2,}|[А-ЯЁ](?![а-яё])|\d+))*[.!?»)]?)', s2)
    if not m: return False
    run = m.group(1); rest = s2[len(run):]
    letters = re.sub(r'[^А-ЯЁ]', '', run)
    if len(letters) < 4 or not re.search(r'[А-ЯЁ]{3,}', run): return False
    if re.match(r'\s*[а-яё]', rest) and not re.search(r'[.!?»)]$', run): return False
    return True
def true_head(vol, k, hs, Ls):
    """настоящая голова статьи: метраж в строке (или в следующей при прописном титуле), прописной титул + титры в следующих
    3 строках, голова киножурнала, указатель. Ложные головы («В РСФСР фильм не демонстрировался.») — нет."""
    t = Ls[k][1]; s = t.lstrip()
    if re.match(r'^(УКАЗАТЕЛЬ|АЛФАВИТНЫЙ|ПРИЛОЖЕНИЕ|СОДЕРЖАНИЕ|ОГЛАВЛЕНИЕ)', s): return True
    if re.search(r'(фитиль|ералаш|кино-крокодил)\s?№', s[:60], re.I) and not re.match(r'^[^А-ЯЁа-яё]{0,4}[А-ЯЁ][а-яё]', s): return True
    if re.match(r'^\d{1,4}\s?[аa]?\.\s*[А-ЯЁ«]', s) and (METR.search(t[:200]) or caps_title(s)): return True
    if METR.search(t[:200]) and (k in hs or caps_title(s)): return True
    if caps_title(s):
        if k + 1 < len(Ls) and METR.search(Ls[k + 1][1][:200]): return True
        for k2 in range(k + 1, min(k + 4, len(Ls))):
            if CREDNEXT.match(Ls[k2][1]): return True
    return False
BIBCONT = re.compile(r'(«[^»]{2,60}»,?\s*(\d{4}|[А-Я][а-я]+[,.])|\d{1,2}\.[IVXХ1УП]+[.\s]*\d{4}|\d{4},\s*№|№\s?\d|\d{4}\s?г[.,]?\s*[;,]|\b(М|Л|Киев|Минск|Тбилиси|Рига|Таллин|Вильнюс|Ташкент|Алма-Ата|Баку|Ереван|Кишинев|Фрунзе|Душанбе|Ашхабад)\.,)')
PRIZECONT = re.compile(r'^[^А-ЯЁа-яё]{0,4}(По итогам|Гпавн|Главн|Приз|Преми|Диплом|Лучш|За лучш|Специальн|Почетн|Серебрян|Золот|Бронзов|Большой|Больш|Первая|Вторая|Третья|Первый|Второй|Третий|Кубок|Медаль|Лауреат|Государственн(ая|ые|ой) преми|Ленинск|Всесоюзн|Международн|В \d{4} г|На [IVX\d]|Отмечен|Удостоен|Награжд|Признан|Актрис|Актер|Режиссер|Оператор|Художник|Композитор|Исполнител|Фильму|Картине|Гран)', re.I)
HEADCONT = re.compile(r'(\d{4}\s?г|ВЭ\s|РУ\s|ВРЭ|\d+(?:,\d)?\s?м[,.]|\d+\s?ч[.,]|ш\.-э|ш\.-ф|цв[.,]|им\. [А-ЯЁ]\.|киностуди|фильмов|студи[яи]|Госкино|Совкино|ВУФКУ|Межрабпом|Госкинпром|Белгоскино|Востоккино|Узбекгоскино|Ленфильм|Мосфильм|фильм»|\(СССР\)|Болгари|ГДР|Чехословак|Польш|Венгри|Румыни|Финлянди|Монголи|Индии|Япони|Итали|Франци|США|Куб[аы]|Вьетнам|Югослави|Швеци|Норвеги)')
def probes(tn):
    if len(tn) <= 14: return [tn] if len(tn) >= 6 else []
    n = max(3, min(7, len(tn) // 20))
    step = (len(tn) - 14) / (n - 1) if n > 1 else 0
    return [tn[int(j * step):int(j * step) + 14] for j in range(n)]
res = []
for i, r in enumerate(cat):
    a = r['annotation']
    if not a: continue
    x = ts.get(i)
    if not x or x.get('h') is None: res.append({'cat': i, 'class': 'UNLOCATED'}); continue
    vol = r['source'].split('_')[0]; Ls = L.lines(vol); hs = L.headset(vol)
    concert = bool(CONCERT.search(r['genre'] or ''))
    h, e = x['h'], x['e']
    hi = min(len(Ls), e + 60)
    A_n = nmap(a)[0]
    def coverage(k):
        tn = nmap(Ls[k][1])[0]
        pr = probes(tn)
        if not pr: return 'junk'
        hit = sum(1 for p in pr if p in A_n)
        return 'cov' if hit * 2 >= len(pr) else ('part' if hit else 'no')
    cov = {k: coverage(k) for k in range(h, hi)}
    # k1: строка начала аннотации (ann_line из П2; иначе первая покрытая строка)
    xl = loc.get(str(i)) or {}
    k1 = xl.get('ann_line') if x.get('loc') == 'ann_line' and xl.get('ann_line') is not None else None
    if k1 is None or not (h <= k1 < hi):
        cands = [k for k in range(h, hi) if cov[k] == 'cov']
        if not cands: res.append({'cat': i, 'class': 'NOCOVER', 'h': h, 'e': e}); continue
        k1 = cands[0]
    # E: первая настоящая голова после k1; k2: последняя покрытая строка в [k1, E)
    E = k1 + 1
    while E < hi and not true_head(vol, E, hs, Ls) and not L.IDX.search(Ls[E][1]): E += 1
    covered = [k for k in range(k1, E) if cov[k] == 'cov'] or [k1]
    k2 = covered[-1]
    # h2: настоящая голова статьи — последняя настоящая голова ≤ k1 (в пределах 40 строк), иначе h
    h2 = h
    for k in range(k1, max(h - 1, k1 - 40) - 1, -1):
        if k >= 0 and true_head(vol, k, hs, Ls): h2 = k; break
    items = []
    # начало аннотации внутри строки k1: текст до начала — проза? (обрыв начала)
    ln1 = nmap(Ls[k1][1])[0]; a0 = A_n[:16]
    p0 = ln1.find(a0) if len(a0) >= 8 else 0
    if p0 > 0:
        raw_before = Ls[k1][1][:nmap(Ls[k1][1])[1][p0]]
        kb = L.kind(raw_before, concert)
        if kb == 'prose' and not is_headlike(raw_before) and len(re.sub(r'[^А-ЯЁа-яё]', '', raw_before)) >= 12:
            items.append({'k': k1, 'pos': 'PRE', 'kind': 'midline', 'text': raw_before[-300:], 'cov': 'mid'})
    state = None
    for k in range(h2 + 1, E):
        if k == k1: state = None; continue
        if cov[k] in ('cov', 'junk'): state = None if cov[k] == 'cov' else state; continue
        t = Ls[k][1]
        if is_junk(t): continue
        pos = 'PRE' if k < k1 else ('GAP' if k < k2 else 'POST')
        kd = L.kind(t, concert)
        if kd == 'prose' and PRIZE2.match(t): kd = 'prize'
        if kd == 'prose' and pos == 'PRE' and HEADCONT.search(t) and not L.VERB.search(t) and k <= h2 + 3: kd = 'headc'
        if kd == 'prose' and re.match(r'^[^А-ЯЁа-яё]{0,3}([А-ЯЁ]{2,}(?:-[А-ЯЁ]{2,})?\s[А-ЯЁ]\.|ТО ЖЕ|То же)', t): kd = 'bib'
        if kd == 'prose' and state == 'bib' and BIBCONT.search(t): kd = 'bibc'
        if kd == 'prose' and state == 'prize' and (PRIZECONT.match(t) or BIBCONT.search(t)): kd = 'prizec'
        if kd == 'prose' and (re.search(r'—\s*\d{2,4}\s*$', t) or re.match(r'^\d{4} год\b|^Игровые фильмы|^\s*\d{4}\s+год', t)): kd = 'index'
        if kd == 'prose' and (is_headlike(t) or true_head(vol, k, hs, Ls)): kd = 'head'
        if kd == 'prose' and cov[k] == 'part': kd = 'part'
        if kd in ('bib', 'bibc'): state = 'bib'
        elif kd in ('prize', 'prizec'): state = 'prize'
        elif kd == 'prose': state = None
        items.append({'k': k, 'pos': pos, 'kind': kd, 'text': t[:300], 'cov': cov[k]})
    res.append({'cat': i, 'id': r['id'], 'vol': vol, 'title': r['title'], 'year': r['year'], 'h': h, 'h2': h2, 'e': e, 'E': E, 'k1': k1, 'k2': k2, 'items': items,
                'class': '+'.join(sorted({f"{it['pos']}-{it['kind'].upper()}" for it in items})) or 'FULL'})
cnt = Counter()
for x in res:
    for c in x['class'].split('+'): cnt[c] += 1
print(len(res), dict(cnt.most_common()))
json.dump(res, open('work/f6_ref_gap_scan_v2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
with open('work/f6_ref_gap_review_v2.txt', 'w', encoding='utf-8') as f:
    for x in res:
        its = [it for it in x.get('items', []) if it['kind'] in ('prose', 'head', 'part', 'midline')]
        if not its and x['class'] not in ('UNLOCATED', 'NOCOVER'): continue
        f.write(f"cat{x['cat']} id{x.get('id')} {x.get('vol')} «{x.get('title')}» {x.get('year')} | {x['class']} h={x.get('h')} e={x.get('e')} E={x.get('E')} k1={x.get('k1')} k2={x.get('k2')}\n")
        for it in its: f.write(f"   @{it['k']} {it['pos']}-{it['kind']} [{it['cov']}] {it['text'][:200]}\n")
