# -*- coding: utf-8 -*-
"""Ф6-П3: призовые предложения в конце аннотаций (наградная форма, П4 §1.2) — кандидаты на TAIL-срез с проверкой по печати."""
import json, re, sys
sys.path.insert(0, 'work')
import f6_p2_lib as L
cat = json.load(open('state/catalog_f6_p2e.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p3_tail_scan.json', encoding='utf-8'))}
AW = re.compile(r'(удостоен|присужден|присуждается|награжден[аы]?\s+(медал|призом|дипломом|премией|орденом[^.]*фестивал)|Гран-при|Гран при|Грап-при|(Гп|Гл)авн(ый|ая|ой) (приз|преми)|Специальн(ый|ая|ого|ой) (приз|преми|диплом)|Почетн(ый|ого|ая) (диплом|грамот|приз)|приз (жюри|ФИПРЕССИ|СИДАЛК|Союза|ЦК|за |имени|«)|премия (жюри|за |имени|ФИПРЕССИ|«|—)|премии (за |имени|жюри)|диплом (жюри|за |I|II|III|первой|второй|третьей)|(Первая|Вторая|Третья|Большая|Высшая|Памятная|Поощрительная|Личная|Особая) (преми|награда)|(Первый|Второй|Третий|Большой|Главный|Особый) приз|«[^»]+» — (приз|преми|награда|большая|главн|высшая|первый|второй|специальн|диплом|вь/сшая)|(кинофестивал|фестивал|кинофоруме|неделе|смотре|конкурсе)[^.]{0,80}(приз|преми|диплом|награ|медал|жетон)|(приз|преми|диплом|награ|медал)[^.]{0,80}(кинофестивал|фестивал|кинофоруме|смотре)|лауреата? (Ленинской|Государственной|Сталинской)|Сталинской премии|Ленинской премии|Государственн(ой|ые) преми|звания лауреата|Золот(ая|ой|ые) (медаль|приз|ветвь|лев|глобус|гроздь|тюльпан|плато|дукат|ворота|орел|нимфа|медведь)|Серебрян(ая|ый) (медаль|приз|пластина|лев|голубь|жетон)|Бронзов(ая|ый) (медаль|приз)|Хрустальн(ый|ая) (глобус|приз)|признан лучшим|назван(а)? лучшим|лучшим фильмом|Приз Союза|приз Союза)', re.I)
def sents(a):
    # границы предложений: знак конца + пробел + заглавная/«/(/цифра; не рвать после инициала «Б.» и «г.»
    parts = []; start = 0
    for m in re.finditer(r'(?<=[.!?…»)])\s+(?=[А-ЯЁ«(\d])', a):
        pre = a[start:m.start()]
        if re.search(r'(?:^|[\s(«])[А-ЯЁ]\.$', pre) or re.search(r'\bг\.$', pre) or re.search(r'\bим\.$', pre): continue
        parts.append((start, m.start())); start = m.end()
    parts.append((start, len(a)))
    return parts
out = []
for i, r in enumerate(cat):
    a = r['annotation']
    if not a: continue
    ss = sents(a)
    flags = [bool(AW.search(a[s:e])) for s, e in ss]
    if not any(flags): continue
    # хвост: максимальная контигуальная группа AW-предложений до конца
    k = len(ss)
    while k > 0 and flags[k - 1]: k -= 1
    tail_start = ss[k][0] if k < len(ss) else None
    mids = [(a[s:e]) for (s, e), f in zip(ss[:k], flags[:k]) if f]
    out.append({'cat': i, 'vol': r['source'].split('_')[0], 'title': r['title'], 'n_sents': len(ss), 'tail_sents': len(ss) - k,
                'tail': a[tail_start:] if tail_start is not None else None, 'rest': a[:tail_start].rstrip() if tail_start is not None else a,
                'mid_award_sents': mids})
json.dump(out, open('work/f6_p3_prize_scan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out), 'records; with tail:', sum(1 for x in out if x['tail']), '; mid-only:', sum(1 for x in out if not x['tail']))
