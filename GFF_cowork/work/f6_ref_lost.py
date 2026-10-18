# -*- coding: utf-8 -*-
"""Регрессия аннотаций: предложения старого каталога, которых нет в новой аннотации той же записи; классификация по маркерам."""
import json, re, sys
sys.path.insert(0, 'work')
from collections import Counter
old = json.load(open('reference/catalog_old_from_db.json', encoding='utf-8'))
new = {r['id']: r for r in json.load(open('state/catalog_final_v1.json', encoding='utf-8'))}
d = json.load(open('work/f6_ref_compare.json', encoding='utf-8'))
MANUAL = {699: 709, 1665: 1682, 4269: 4334, 4548: 4619, 5059: 5154, 5596: 5740, 6596: 6860}
pairs = {p['i']: p['id'] for p in d['pairs']}; pairs.update(MANUAL)
def na(s): return re.sub(r'[^а-яa-z0-9]', '', (s or '').lower().replace('ё', 'е'))
NONPROSE = re.compile(r'^\W*(Библиограф|Авт\.|Реж\.|Реж |Опер\.|Худ\.|Композ|Звукоопер|Монтаж|Ассист|Дир\. картины|Ред\.|В ролях|В роли|Роли (дубл|озвуч|исполн)|Фильм дублирован|Фильм озвучен|Текст читает|Гл\. ред|Над фильмом|Съемочная группа|Симфонический|Государственн(ый|ая) (симф|академ|оркестр|хор|ансамбл)|Оркестр|Хор |Ансамбл|Дирижер|Солист|Исп\. |ВЭ |РУ |На [IVX\d]+ |На Всесоюзн|На Международн|Фильму? (удостоен|присужден|награжд)|Картин[аеы] (удостоен|присужден)|Приз|Премия|Диплом|Гран-при|Специальн(ый|ая) (приз|преми)|Главн(ый|ая) (приз|преми)|В \d{4} г\.? (фильм|картин)|«[^»]+» — (приз|преми)|\d+ ч\.|\d{3,4} м[,.]|Гос\. |Ленинградск(ий|ая) (гос|академ)|Московск(ий|ая) (гос|академ)|Русский народный|Эстрадн|Вокальн|Куклы|Кукловод|Мультипл|[А-ЯЁ]\. [А-ЯЁ][а-яё]+ \(|Зак\. №|\d+ Заказ)', re.I)
lost = []
for i, jid in pairs.items():
    ao = old[i]['annotation']; an = new[jid]['annotation']
    if not ao: continue
    ann = na(an)
    sents = [s for s in re.split(r'(?<=[.!?…])\s+', ao) if len(na(s)) >= 25]
    for s in sents:
        k = na(s)
        probe = k[5:35] if len(k) >= 40 else k[:30]
        if probe in ann: continue
        kind = 'nonprose' if NONPROSE.match(s.strip()) else 'prose?'
        lost.append({'i': i, 'id': jid, 'kind': kind, 'sent': s.strip()[:200], 'old_title': old[i]['title'][:50], 'new_title': new[jid]['title'][:50]})
print('потерянных предложений (нет в новой аннотации):', len(lost), Counter(x['kind'] for x in lost))
json.dump(lost, open('work/f6_ref_lost.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
pr = [x for x in lost if x['kind'] == 'prose?']
print('записей с prose?:', len({x['id'] for x in pr}))
for x in pr[:400]:
    print(f"id {x['id']} «{x['new_title']}» | {x['sent'][:150]}")
