# -*- coding: utf-8 -*-
"""Ф6-П3а регрессия аннотаций (финал): предложения старого каталога (reference/catalog_old_from_db.json), отсутствующие в аннотации
той же записи финального каталога v2 (probe/ratio ≥ 0.75), локализуются в печати тома:
  in_article  — строка внутри области статьи записи (work/f6_ref_gap_scan_v2.json: h2..E) → класс строки kind (prose = потенциальная потеря);
  elsewhere   — найдена в печати вне статьи (контаминация старого каталога соседними статьями);
  not_found   — в печати не найдена (OCR-вариант/иной источник старого каталога).
Выход: work/f6_ref_lost3.json + сводка."""
import json, re, sys, difflib
sys.path.insert(0, 'work')
import f6_p2_lib as L
from collections import Counter
src = open('work/f6_p3a_tail_scan.py', encoding='utf-8').read()
ns = {'re': re, 'L': L}; exec(src[src.index('JUNKLINE ='):src.index('res = []')], ns); nmap = ns['nmap']; PRIZE2 = ns['PRIZE2']
old = json.load(open('reference/catalog_old_from_db.json', encoding='utf-8'))
newl = json.load(open('state/catalog_final_v2.json', encoding='utf-8')); new = {r['id']: r for r in newl}
d = json.load(open('work/f6_ref_compare_v2.json', encoding='utf-8'))
MANUAL = {1665: 1683, 4269: 4335, 4548: 4620, 5059: 5155, 5596: 5741, 6596: 6861}
pairs = {p['i']: p['id'] for p in d['pairs']}; pairs.update(MANUAL)
gap = {x['cat']: x for x in json.load(open('work/f6_ref_gap_scan_v2.json', encoding='utf-8'))}
def na(s): return re.sub(r'[^а-яa-z0-9]', '', (s or '').lower().replace('ё', 'е'))
def sents(a): return [s.strip() for s in re.split(r'(?<=[.!?…])\s+(?=[А-ЯЁ«(\d])', a or '') if len(na(s)) >= 25]
VN = {}
def vol_norm(v):
    if v not in VN: VN[v] = [nmap(t)[0] for n, t, p in L.lines(v)]
    return VN[v]
BIBL = re.compile(r'(«[^»]{2,60}»,?\s*(\d{4}|[А-Я][а-я]+[,.])|\d{1,2}\.[IVXХ1УП]+[.\s]*\d{4}|\d{4},\s*№|№\s?\d|\d{4}\s?г[.,]?\s*[;,]|Б и б л и о г р а ф|Библиограф|[А-ЯЁ]{2,}\s[А-ЯЁ][.-]\s)')
HEADL = re.compile(r'(\d+\s?ч[.,]|\d+(?:,\d)?\s?м[,.]|ВЭ\s|РУ\s|Всесоюзный сатирический|Детский юмористический|киножурнал|киностуди|студия кинохроники|Киностуди|Драма,|Мелодрама,|Комедия,|Приключ|Эпопея,|Фантастич)')
PRIZEL = re.compile(r'^[^А-ЯЁа-яё]{0,4}(По итогам|Гпавн|Главн|Приз|Преми|Диплом|Лучш|За лучш|Специальн|Почетн|Серебрян|Золот|Бронзов|Большой приз|Первая|Вторая|Третья|Первый|Второй|Третий|Кубок|Медаль|Лауреат|Государственн(ая|ые|ой) преми|Гэсударственн|Ленинск|Всесоюзн|Международн|В \d{4} г|На [IVX\d]|Отмечен|Удостоен|Награжд|Признан|Назван|Особый приз|Один из пяти)', re.I)
AW = re.compile(r'(удостоен|присужден|награжден|премия|премии|приз |призы|диплом|медал|лауреат|признан лучшим|назван лучшим)', re.I)
CREDX = re.compile(r'(Авт\. сцен|авт\. сцен|реж\.|опер\.|худ\.|композ\.|звукоопер|В ролях|дир\. картины|Текст (от автора )?чита|Над фильмом|Использован|В фильм включены|Автор и исполнитель|Автор текста|исполняет|исполняют|в исполнении|Интервью давали|принимали участие|Стихи .{0,30}в исполнении|Вокальные партии|Песни и романсы|Танго и фокстрот)')
def probe_in(a, t):
    A = nmap(a or '')[0]; tn = nmap(t)[0]
    if len(tn) < 20: return False
    pr = [tn[k:k + 14] for k in (0, len(tn) // 2, max(0, len(tn) - 14))]
    return sum(1 for x in pr if x in A) >= 2
out = []; cnt = Counter()
for i, jid in pairs.items():
    ao, an = old[i]['annotation'], new[jid]['annotation']
    if not ao: continue
    ann = na(an); ns_ = [na(s) for s in sents(an)]
    cat_i = jid - 1; vol = new[jid]['source'].split('_')[0]; g = gap.get(cat_i, {})
    for s in sents(ao):
        k = na(s); probe = k[5:35] if len(k) >= 40 else k[:30]
        if probe in ann: continue
        best = max((difflib.SequenceMatcher(None, k, t).ratio() for t in ns_ if abs(len(t) - len(k)) < max(40, len(k))), default=0)
        if best >= 0.75: continue
        p0 = ann.find(k[:10])
        if len(k) >= 30 and p0 >= 0 and difflib.SequenceMatcher(None, k, ann[max(0, p0 - 5):p0 + len(k) + 5]).ratio() >= 0.75: continue
        # локализация в печати
        kn = nmap(s)[0]; pr = kn[8:30] if len(kn) >= 38 else kn[:22]
        VL = vol_norm(vol); hits = [j for j, t in enumerate(VL) if pr and pr in t]
        if not hits and len(kn) >= 40:
            pr2 = kn[-26:-4]; hits = [j for j, t in enumerate(VL) if pr2 in t]
        if not hits: loc, kind = 'not_found', None
        elif 'h2' in g and any(g['h2'] <= j < g['E'] for j in hits):
            loc = 'in_article'; j = [j for j in hits if g['h2'] <= j < g['E']][0]
            t = L.lines(vol)[j][1]; kind = L.kind(t)
            if kind == 'prose' and PRIZE2.match(t): kind = 'prize'
            if kind == 'prose' and j < g['k1'] and re.match(r'^[^А-ЯЁа-яё]{0,3}[А-ЯЁ][^.]{0,40}\(', t): kind = 'cast'
            if kind == 'prose' and (BIBL.search(t) or BIBL.search(s)): kind = 'bib'
            if kind == 'prose' and HEADL.search(t): kind = 'head'
            if kind == 'prose' and (PRIZEL.match(t) or AW.search(t)): kind = 'prize'
            if kind == 'prose' and CREDX.search(t): kind = 'cred'
            if kind == 'prose':
                for jj in range(max(0, cat_i - 6), min(len(newl), cat_i + 7)):
                    if jj != cat_i and newl[jj]['source'].split('_')[0] == vol and probe_in(newl[jj]['annotation'], t): kind = 'neighbour'; break
        else: loc, kind = 'elsewhere', None
        cnt[(loc, kind)] += 1
        out.append({'i': i, 'id': jid, 'loc': loc, 'kind': kind, 'line': (hits[0] if hits else None), 'best': round(best, 2), 'sent': s[:200], 'title': new[jid]['title'][:40], 'vol': vol})
json.dump(out, open('work/f6_ref_lost3.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('кандидатов:', len(out), '; записей:', len({x['id'] for x in out}))
for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]): print('  ', k, v)
print('--- in_article/prose:')
for x in out:
    if x['loc'] == 'in_article' and x['kind'] == 'prose': print(f"  id{x['id']} {x['vol']} «{x['title']}» @{x['line']} best={x['best']} {x['sent'][:130]}")
