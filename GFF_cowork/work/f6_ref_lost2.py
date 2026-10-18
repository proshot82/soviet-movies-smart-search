# -*- coding: utf-8 -*-
"""Регрессия аннотаций (уточнение): предложения старого каталога, отсутствующие в новой аннотации той же записи и не имеющие
близкого (ratio ≥ 0.75) предложения в новой; проверка наличия в печати (work/vN_lines.json); классификация."""
import json, re, sys, difflib
sys.path.insert(0, 'work')
import f6_p2_lib as L
from collections import Counter
old = json.load(open('reference/catalog_old_from_db.json', encoding='utf-8'))
newl = json.load(open('state/catalog_final_v1.json', encoding='utf-8'))
new = {r['id']: r for r in newl}
d = json.load(open('work/f6_ref_compare.json', encoding='utf-8'))
MANUAL = {699: 709, 1665: 1682, 4269: 4334, 4548: 4619, 5059: 5154, 5596: 5740, 6596: 6860}
pairs = {p['i']: p['id'] for p in d['pairs']}; pairs.update(MANUAL)
def na(s): return re.sub(r'[^а-яa-z0-9]', '', (s or '').lower().replace('ё', 'е'))
def nm(s): return L.norm_m(s or '')
NONPROSE = re.compile(r'^\W*(Библиограф|Б\s?и\s?б|Авт\.|Реж\.|Реж |Опер\.|Худ\.|Композ|Звукоопер|Монтаж|Ассист|Дир\. картины|Ред\.|В ролях|В роли|Роли (дубл|озвуч|исполн)|Фильм дублирован|Фильм озвучен|Текст читает|Гл\. ред|Над фильмом|Съемочная группа|Симфонический|Государственн(ый|ая) (симф|академ|оркестр|хор|ансамбл)|Оркестр|Хор |Ансамбл|Дирижер|Солист|Исп\. |ВЭ |РУ |На [IVX\d]+ |На Всесоюзн|На Международн|Фильму? (удостоен|присужден|награжд)|Картин[аеы] (удостоен|присужден)|Приз|Премия|Диплом|Гран-при|Специальн(ый|ая) (приз|преми)|Главн(ый|ая) (приз|преми)|В \d{4} г\.? (фильм|картин)|«[^»]+» — (приз|преми)|\d+ ч\.|\d{3,4} м[,.]|Гос\. |Русский народный|Эстрадн|Вокальн|Куклы|Кукловод|Мультипл|[А-ЯЁ]\. [А-ЯЁ][а-яё]+ \(|Зак\. №|\d+ Заказ|[IVX]+ \d{4} г|\d{1,2}\.[IVX]+|«[^»]+», [А-Я][а-я]+\.,|№ \d)', re.I)
def sents(a): return [s.strip() for s in re.split(r'(?<=[.!?…])\s+(?=[А-ЯЁ«(\d])', a or '') if len(na(s)) >= 25]
out = []
for i, jid in pairs.items():
    ao, an = old[i]['annotation'], new[jid]['annotation']
    if not ao: continue
    ann = na(an); ns = [na(s) for s in sents(an)]
    for s in sents(ao):
        k = na(s)
        probe = k[5:35] if len(k) >= 40 else k[:30]
        if probe in ann: continue
        best = max((difflib.SequenceMatcher(None, k, t).ratio() for t in ns if abs(len(t) - len(k)) < max(40, len(k))), default=0)
        if best >= 0.75: continue
        # в новой аннотации целиком (окно) — на случай иной разбивки на предложения
        if len(k) >= 30 and difflib.SequenceMatcher(None, k, ann[max(0, ann.find(k[:10]) - 5):ann.find(k[:10]) + len(k) + 5]).ratio() >= 0.75 and ann.find(k[:10]) >= 0: continue
        kind = 'nonprose' if NONPROSE.match(s) else 'prose'
        out.append({'i': i, 'id': jid, 'kind': kind, 'sent': s[:220], 'best': round(best, 2), 'title': new[jid]['title'][:45], 'vol': new[jid]['source'].split('_')[0]})
print('кандидаты потерь:', len(out), Counter(x['kind'] for x in out), '; записей:', len({x['id'] for x in out if x['kind'] == 'prose'}))
json.dump(out, open('work/f6_ref_lost2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
pr = [x for x in out if x['kind'] == 'prose']
print(Counter(x['vol'] for x in pr))
