# -*- coding: utf-8 -*-
"""Ф6-П3в: печатный скан «титры внутри аннотации» (все записи, кроме киножурналов/альманахов k4 и концертных жанров).
Строки печати, покрытые аннотацией, но лежащие в блоке титров: (а) до/на строке «В ролях…» (последняя строка списка ролей статьи) —
всё, что печатно предшествует списку ролей, титры по расположению; (б) после списка ролей — строки класса kind()=='cred'
(в т.ч. продолжение списка ролей со строчной) или титровой формулы CR2. Выход: work/f6_p3v_scan.json (cat → строки к срезу)."""
import json, re, sys
sys.path.insert(0, 'work')
import f6_p2_lib as L
src = open('work/f6_p3a_tail_scan.py', encoding='utf-8').read()
ns = {'re': re, 'L': L}; exec(src[src.index('CONCERT ='):src.index('res = []')], ns); nmap = ns['nmap']; CONCERT = ns['CONCERT']
cat = json.load(open('state/catalog_final_v2.json', encoding='utf-8'))
gap = {x['cat']: x for x in json.load(open('work/f6_ref_gap_scan_v2.json', encoding='utf-8'))}
K4 = re.compile(r'Фитиль|Ералаш|киносборник|Киносборник|альманах|Альманах|киножурнал|Киножурнал|Кино-крокодил|Кинокрокодил|Сборник|сборник', re.I)
CAST = re.compile(r'^[^А-ЯЁа-яё]{0,4}(В ролях|В роли|В главных ролях|Роли (исполн|дублир|озвуч))')
CR2 = re.compile(r'^[^А-ЯЁа-яё]{0,3}(Текст .{0,40}чита|Рассказ от автора вед|В роли .{0,40}снимал|Роли (озвуч|дублир)|Исполнител[ьи] |Съемки производились|Руководител[ьи] |Режиссер дубляжа|Фильм дублирован|Слова песен|Русский текст чита|Стихи .{0,40}чита|Над фильмом (также )?работали|Съемочная группа (выражает|благодарит|приносит)|Съемочный коллектив|Киногруппа благодарит|В фильме (использован[аы]? (музыка|мелоди|песни|стихи|фрагмент|кадры|материалы)|снимал[ао]сь|снимались|принимал[аи]? участие|принимают участие|участвуют|участвовали|звучит музыка|звучат песни|заняты|исполнены песни|танцуют|дают интервью)|В съемках? (фильма |картины )?(принимал|принимают|участв|снимал|использов)|В (массовых|воздушных|подводных) съемках|Использован[аы]? (музыка|мелоди|песни|стихи|фрагмент|кадры|материалы)|Роли исполняли|Роли исполняют|Исполнители (танцев|народной|песен|ролей|главных)|В роли [А-ЯЁ][а-яё]+ — |Оркестр .{0,80}под управлением|Песни исполня|Песню исполняет|Вокальные партии|Хореографический ансамбль|Хореография|Гонщики-спортсмены|Автор и исполнитель песен|Автор (текста|стихов|музыки) песн|Авт\. музыки|Интервью давали|Музыка в исполнении|Главные роли дублируют|Дублировали|Дикторы? |Ведущ(ий|ая|ие) [А-ЯЁ]|Комментатор |Консультант|Художественн(ый|ое) руководств|Худ\. руководитель|Творческая мастерская|Высшие курсы|Лаборатория киностудии|Работы скульптора|Кадры из фильма|Фильм озвучен|Фильм дублирован|Реж\. (озвуч|дубл)|Звукорежиссер|Балетмейстер|Продюсер|Поют |Поет |Играет на|Аккордеонист|Музыканты:|Аттракцион «|Артисты «|Учащиеся |Спортивный комментатор|Помощь в съемках|Народную музыку|Коллектив [А-ЯЁ]|Рассказывают об|Живопись [А-ЯЁ]|Музыка [А-ЯЁ]\. [А-ЯЁ]|Оригинальная музыка|Звучат песни:|Историю .{0,60}рассказывает|На дутаре|Композ\.|Аранжировка|Народную музыку|(Музыку|Песни|Мелодии) .{0,40}(собрал|записал|обработал)|Музыкальн(ое|ая) (оформлени|обработк)|Запись музыки)', re.I)
SRC = re.compile(r'^[^А-ЯЁа-яё]{0,3}(В (фильме|картине) использован[ыа]? (сюжет|мотив|сказк|материал[ы]? (пьес|роман|повест|рассказ|сказ))|По (мотивам|одноименн|роману|повести|пьесе|рассказ|сказк)|Экранизац|В основу)')
def probes(tn):
    if len(tn) <= 14: return [tn] if len(tn) >= 6 else []
    n = max(3, min(7, len(tn) // 20)); step = (len(tn) - 14) / (n - 1) if n > 1 else 0
    return [tn[int(j * step):int(j * step) + 14] for j in range(n)]
PROSESTART = re.compile(r'^[^А-ЯЁа-яё]{0,3}(О |Об |Обо |Фильм |Фильм-|Картина |По |Экраниз|В основу|На основе|Рассказ|История|Повесть|Сказка|Комедия|Драма|Приключени|Действие|Судьба|Жизнь|Годы|Наши дни|\d{4} год|В \d{4} г|Конец |Начало |Лето |Осень |Зима |Весна )')
HEADC = re.compile(r'(\d{4}\s?г|ВЭ\s|РУ\s|ВРЭ|\d+(?:,\d)?\s?м[,.]|\d+\s?ч[.,]|ш\.-э|ш\.-ф|цв[.,]|им\. [А-ЯЁ]\.|киностуди|фильмов|студи[яи])')
CASTL = re.compile(r'^[^А-ЯЁа-яё]{0,3}(?:[А-ЯЁ]?[а-яё\-\s]{1,30}\),\s(?:(?:[А-ЯЁ]\.\s?){1,2}[А-ЯЁ][а-яё\-]+|[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё\-]+)\s\(|[а-яё\-]{1,20},\s(?:[А-ЯЁ]\.\s?){1,2}[А-ЯЁ][а-яё\-]+(?:\s\(|,)|(?:[А-ЯЁ]\.\s?){1,2}[А-ЯЁ][а-яё\-]+\s\([^)]{1,80}\)[,;.]|[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё\-]+\s\([^)]{1,80}\)[,;.]|(?:(?:[А-ЯЁ]\.\s?){1,2}[А-ЯЁ][а-яё\-]+,\s){2,})')
CRF = re.compile(r'^[^А-ЯЁа-яё]{0,3}(Авт\. |Ав[тг]\. |Реж\.|Сцен\.|Опер\.|Худ\.|Композ|Звукоопер|Монтаж\.|Дир\. картины|В ролях|Роли исполн|Гл\. ред|Ред\. )')
def credit_strict(t):
    s = t.strip()
    if not s or (PROSESTART.match(s) and not CR2.match(s)): return False
    return bool(CR2.match(s) or CASTL.match(s) or CRF.match(s))
def credit_like(t):
    s = t.strip()
    if not s: return False
    if PROSESTART.match(s) and not CR2.match(s): return False
    if L.kind(s, False) == 'cred' or CR2.match(s): return True
    return False
out = {}
for i, r in enumerate(cat):
    a = r['annotation']
    if not a or K4.search(r['title']) or K4.search(r['genre'] or '') or CONCERT.search(r['genre'] or ''): continue
    g = gap.get(i)
    if not g or 'h2' not in g: continue
    v = r['source'].split('_')[0]; Ls = L.lines(v); A, amap = nmap(a)
    h2, E = g['h2'], g['E']
    # блок титров: h2+1 … пока строки титроподобны / продолжение головы / мусор
    kc = h2; k = h2 + 1
    while k < E:
        t = Ls[k][1]
        if not t.strip() or re.match(r'^[^А-ЯЁа-яё]*$', t): k += 1; continue
        if credit_strict(t) or CAST.match(t) or (credit_like(t) and not L.VERB.search(t)) or (k <= h2 + 3 and HEADC.search(t) and not L.VERB.search(t) and not PROSESTART.match(t)): kc = k; k += 1; continue
        break
    P = None
    for k in range(kc + 1, E):
        t = Ls[k][1]
        if t.strip() and not re.match(r'^[^А-ЯЁа-яё]*$', t): P = k; break
    if P is None: continue
    cut = []
    # (а) начало аннотации внутри блока титров
    a16 = A[:16]
    ks = None
    for k in range(h2 + 1, kc + 1):
        nk = nmap(Ls[k][1])[0]
        if len(nk) >= 6 and A.startswith(nk[:16]): ks = k; break
    if ks is None:
        for k in range(h2, E):
            if a16 and a16 in nmap(Ls[k][1])[0]: ks = k; break
    pP = A.find(nmap(Ls[P][1])[0][:16]) if len(nmap(Ls[P][1])[0]) >= 12 else -1
    if ks is not None and ks <= kc and ks != h2:
        nk = nmap(Ls[ks][1])[0]
        if not A.startswith(nk[:16]) and a16 in nk and nk.find(a16) > 0:   # аннотация начинается с середины строки ks
            if pP > 0: cut.append(('midline', ks, P, 'аннотация начинается с середины строки @%d блока титров; префикс до прозы @%d: «%s»' % (ks, P, a[:amap[pP]][:120] if pP < len(amap) else a[:120])))
            ks = None
    if ks is not None and ks <= kc and ks != h2 and pP > 0:
        cut.append(('prefix', ks, P, 'начало аннотации — в блоке титров (@%d…@%d), проза начинается с @%d' % (ks, kc, P)))
    elif ks is not None and ks <= kc and ks != h2 and pP <= 0:
        cut.append(('prefix?', ks, P, 'начало аннотации в блоке титров, но начало прозы @%d в аннотации не найдено — вручную' % P))
    # (б) титроподобные строки после начала прозы, покрытые аннотацией
    for k in range(P, E):
        t = Ls[k][1]
        if SRC.match(t) or not t.strip(): continue
        tn = nmap(t)[0]; pr = probes(tn)
        if not pr: continue
        hit = sum(1 for p in pr if p in A)
        if hit * 2 < len(pr): continue
        if credit_strict(t): cut.append(('line', k, k, 'титры внутри/после прозы: ' + t[:80]))
    if cut: out[i] = {'id': r['id'], 'title': r['title'], 'genre': r['genre'], 'vol': v, 'kc': kc, 'P': P, 'cut': cut, 'texts': {k: Ls[k][1][:200] for _, k, _, _ in cut}, 'ann_start': a[:100]}
json.dump(out, open('work/f6_p3v_scan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
from collections import Counter
print('записей', len(out), '; позиций', sum(len(x['cut']) for x in out.values()), Counter(w[0] for x in out.values() for w in x['cut']))
for i, x in sorted(out.items()):
    print(f"cat{i} id{x['id']} {x['vol']} «{x['title'][:30]}» ({x['genre']}) kc={x['kc']} P={x['P']} | ANN: {x['ann_start'][:70]}")
    for kind, k, k2, w in x['cut']: print(f"    {kind} @{k}: {w[:110]}")
