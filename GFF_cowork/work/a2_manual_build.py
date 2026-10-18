# -*- coding: utf-8 -*-
"""П4 a2 — ручные операции + слияние с авто-резолюцией -> scripts/a2_resolution.json"""
import json, re

cat = json.load(open('state/catalog_f5_a1.json', encoding='utf-8'))
auto = json.load(open('work/a2_res_auto4.json', encoding='utf-8'))['cut']

def T(i): return cat[i]['annotation']
cuts = {}

def tail_from(i, marker, cls, include_prejunk=True):
    t = T(i); j = t.find(marker)
    assert j > 40, f'cat{i}: маркер не найден/рано: {marker!r}'
    # захватить мусор перед маркером
    if include_prejunk:
        k = j
        while k > 0 and t[k-1] in ' <>■❖^~*©®°•-—–)(|/\\’‘”„': k -= 1
        if t[:k].rstrip().endswith(('.', '!', '?', '…', '»')): j = k
    cuts[str(i)] = {'lead': None, 'tail': t[j:], 'class': cls}

def lead_to(i, marker, cls):
    """lead = всё до маркера (маркер остаётся)."""
    t = T(i); j = t.find(marker)
    assert 0 < j < len(t) * 0.6, f'cat{i}: lead-маркер: {marker!r} @{j}'
    cuts[str(i)] = {'lead': t[:j], 'tail': None, 'class': cls}

def excise(i, pattern, cls):
    t = T(i)
    m = re.search(pattern, t)
    assert m, f'cat{i}: excise не найден'
    assert not re.search(pattern, t[m.end():]), f'cat{i}: excise неуникален'
    cuts[str(i)] = {'lead': None, 'tail': None, 'mid': [m.group(0)], 'class': cls}
    return m.group(0)

FOOT = None  # точные строки ниже
# ---- B: постраничные колонтитулы ----
lead_footers = {57: 'Экранизация одноименного рассказа', 523: 'Положив в основу сценария',
 563: 'Авторы не установлены', 780: 'Пропаганда советского автомобилизма',
 1123: 'Экранизация романа Л. Пасынкова', 1302: 'Эпизод из жизни учащихся',
 1607: 'О летчиках гражданской авиации', 1638: 'Об одном из ближайших сподвижников',
 1887: 'Экранизация одноименной пьесы А. Якобсопа', 2018: 'Спектакль «Волки и овцы»',
 2264: 'О торжестве справедливости', 2417: 'О трудной и славной судьбе коммуниста'}
for i, marker in lead_footers.items():
    lead_to(i, marker, 'колонтитул-лид (Заказ №)')
mid_footers = {426: '12 Заказ ^ 7 35', 744: '21 Заказ № ”35', 928: '26 Заказ И 735',
 1487: '11 Заказ № 7 78 Том II', 2069: '32 Заказ х. 77« Том II', 2096: '33 Заказ ЛЬ 778. Юм П',
 2338: '657 657 42 Заказ .V 778. Том И', 2488: '48 Заказ М» 77«. Том II'}
for i, sub in mid_footers.items():
    t = T(i)
    assert t.count(sub) == 1, f'cat{i}: колонтитул {sub!r} count={t.count(sub)}'
    cuts[str(i)] = {'lead': None, 'tail': None, 'mid': [sub], 'class': 'колонтитул-вставка (Заказ №)'}
# 2361: колонтитул + библиография до конца
tail_from(2361, '•43 Заказ Л» 7 78 Том П', 'колонтитул+библиография', include_prejunk=True)

# колонтитульные записи: добить их собственные хвосты (библиография/рубрикатор)
for i in list(lead_footers) + list(mid_footers):
    t = T(i)
    bj = None
    for mark in ('Библиография', 'БИБЛИОГРАФИЯ'):
        j2 = t.find(mark)
        if j2 != -1: bj = j2 if bj is None else min(bj, j2)
    if bj is not None and len(t[:bj].strip()) > 40:
        k = bj
        while k > 0 and t[k-1] in ' <>■❖^~*©®°•’‘”„': k -= 1
        cuts[str(i)]['tail'] = t[k:]
        cuts[str(i)]['class'] += '+библиография'
cuts['426']['tail'] = T(426)[T(426).find('МУЛЬТИПЛИКАЦИОННЫЕ ФИЛЬМЫ'):]
cuts['426']['class'] += '+рубрикатор'

# ---- C: хвостовые указатели тома (+призовые перед ними) ----
tail_from(3431, 'ПРИЛОЖЕНИЕ ХРОНОЛОГИЧЕСКИЙ УКАЗАТЕЛЬ', 'приложение тома (указатели+колофон, 53КБ)')
tail_from(4044, 'Диплом жюри XX Международного кинофестиваля', 'призовой+указатель тома+колофон')
tail_from(4330, 'Диплом жюри IV Всесоюзного кинофестиваля', 'призовой+указатель тома+колофон')
tail_from(4594, 'УКАЗАТЕЛЬ ФИЛЬМОВ ПО КИНОСТУДИЯМ', 'указатель тома+колофон')
tail_from(4893, 'АЛФАВИТНЫЙ УКАЗАТЕЛЬ ФИЛЬМОВ', 'указатель тома+колофон')
tail_from(5202, 'На XX Международном кинофестивале в Карловых Варах', 'призовой+указатель тома+колофон')
tail_from(5531, 'УКАЗАТЕЛЬ ФИЛЬМОВ ПО КИНОСТУДИЯМ', 'указатель тома+колофон')
tail_from(5872, 'УКАЗАТЕЛЬ ФИЛЬМОВ ПО КИНОСТУДИЯМ', 'указатель тома+колофон')
tail_from(6221, 'АЛФАВИТНЫЙ УКАЗАТЕЛЬ ФИЛЬМОВ', 'указатель тома+колофон')
tail_from(6549, 'АЛФАВИТНЫЙ УКАЗАТЕЛЬ ФИЛЬМОВ', 'указатель тома')
tail_from(6875, 'УКАЗАТЕЛЬ ФИЛЬМОВ ПО КИНОСТУДИЯМ', 'указатель тома+колофон')

# ---- D: призовые вручную (после prize_gap-разбора; 1265/2209/3268/3373 — сюжет, не трогать) ----
tail_from(2144, 'На VIII Международном кинофестивале в Каннах (1955) отмечена', 'призовой')
tail_from(2543, 'На Всесоюзном фестивале советских фильмов в Киеве (1959)', 'призовой+библиография(разорв. маркер)')
tail_from(2783, 'На III Всесоюзном фестивале советских фильмов в Минске', 'призовой')
tail_from(3191, 'На втором смотре-соревновании кинематографистов', 'призовой')
tail_from(3234, 'На Всесоюзном кинофестивале в Ленинграде (1964) премия', 'призовой')
tail_from(3622, 'На XVIII Международном кинофестивале фильмов для детей', 'призовой')
tail_from(4989, 'Премия I Международного кинофестиваля в Гданьске', 'призовой')
tail_from(5219, 'На X Всесоюзном кинофестивале (Рига, 1977 г.)', 'призовой')

# ---- E: точечные ----
tail_from(1846, 'Б и б л и о г р а ф и я:', 'библиография (разряженный маркер)')
tail_from(2640, 'Б и б л и о гр аф и я:', 'библиография (разряженный маркер)')
tail_from(2156, 'МУЛЬТИПЛИКАЦИОННЫЕ ФИЛЬМЫ', 'рубрикатор', include_prejunk=False)
tail_from(3264, '1963 г. ИГРОВЫЕ ФИЛЬМЫ', 'рубрикатор(+год)', include_prejunk=False)

print('=== РУЧНЫЕ CUT/EXCISE ===')
for k in sorted(cuts, key=int):
    v = cuts[k]; i = int(k); t = T(i)
    if v.get('mid'):
        print(f'cat{k} EXCISE {v["class"]}: {v["mid"][0]!r}')
    else:
        rem = t
        if v['lead']: rem = rem[len(v['lead']):]
        if v['tail']: rem = rem[:len(rem)-len(v['tail'])]
        rem = rem.strip()
        print(f'cat{k} [{v["class"]}] lead={len(v["lead"] or "")} tail={len(v["tail"] or "")} | ОСТ: {rem[:60]}…{rem[-60:]}')

# ---- restore cat81 из тома ----
import sys; sys.path.insert(0, 'scripts')
L = json.load(open('work/v1_lines.json', encoding='utf-8'))
line504 = L[504][1]
j = line504.find('О борьбе украинских крестьян')
assert j > 0
prose81 = re.sub(r'\s+', ' ', line504[j:]).strip()
print('\ncat81 RESTORE:', repr(prose81))

res = {'cut': dict(auto), 'restore': {'81': {'text': prose81, 'vol': 'v1', 'lines': [504],
        'note': 'проза статьи (часть строки @504 после списка ролей); прежняя аннотация — чистая библиография; призовая справка @505 и титры не включены'}},
       'none': {}, 'confirm': {}, 'notfound': {}}
for k, v in cuts.items():
    res['cut'][k] = v   # ручное перекрывает авто
json.dump(res, open('scripts/a2_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'\nИТОГО: cut {len(res["cut"])} (авто {len(auto)}, ручных {len(cuts)}, перекрыто {len(set(auto) & set(cuts))}), restore 1')
