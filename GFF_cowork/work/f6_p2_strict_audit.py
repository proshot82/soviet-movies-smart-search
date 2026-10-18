# строгий аудит срезов (lead/tail/mid) резолюции: ни одна печатная строка, не являющаяся титрами/библиографией/призом/мусором/головой
# по КОНСЕРВАТИВНОМУ классификатору, не должна быть удалена из аннотации
import sys, json, re
sys.path.insert(0, 'work')
import f6_p2_lib as L
cat = json.load(open('state/catalog_f6_p1.json', encoding='utf-8'))
res = json.load(open('scripts/f6_p2_resolution.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p2_ann_scan.json', encoding='utf-8'))}
art = json.load(open('work/f6_p2_articles.json', encoding='utf-8'))
CREDK = re.compile(r'^(?:[^А-ЯЁа-яёA-Za-z0-9]{0,6})(Авт\.? ?сцен|Ав[тг][.,] ?сц|Сцен[.,]|Реж[.,]|Реж\.-пост|Пост\.|Опер[.,]|Опер\.-пост|Худ[.,]|Худ\.-пост|Композ|Звукоопер|Монтаж[.,]|Ассист|Костюм|Грим[.,]|Ред\.|Дир\. картины|Дир\. фильма|Комб\. съемк|Роли (дублир|озвуч|исполн)|В ролях|В роли|В главных ролях|Дублир|Фильм дублирован|Фильм озвучен|(Русский )?[Тт]екст чита|Перевод чита|Консульт|Воен\. консульт|Гл\. (опер|худ|ред|консульт|реж)|2-й (реж|опер)|Мультипл|Кукловод|Куклы |Балетмейстер|Дирижер|Хормейстер|Государственн(ый|ая) (симфонический|академический|заслуженный|оркестр|хор|ансамбль|русский|эстрадный|камерный|духовой|народный|Большой|республиканск)|Симфонический оркестр|Оркестр|Ансамбль|Хор |Хор,|Вокальн|Эстрадн|Инструментальн|Исполнител|Исполняет|Исполняют|Исполняется|Исп\. |Песн[июя] (исполня|поет|поют)|Над фильмом|Над выпуском|Съемочная группа|Киногруппа|Студия благодарит|В съемках? (фильма |картины )?(принимал|участв|снимал|использов)|В фильме (снимал|участв|приним)|Дикторы?|Ведущ|Солист|Партии (исполня|поют)|Автор[ы]? (сцен|текст)|Авт\. текст|Пом\. реж|Сореж|Лит\. (обраб|консульт)|Запись музыки|Муз\. (ред|сопров)|Музыка |Мелодии |Текст[ыа]? песен|Стихи |В фильме (звуч|использован[аы]? (музык|фрагмент|произведени|симфони|песн|романс|увертюр))|Инженер по|Пиротехник|Каскадер|Трюки|Дрессировщик|Худ\. руководитель|Художественный руководитель|Творческая мастерская|Лебедей вырастили|Обработка пленки|Дубл\.|Дублируют|Дублировали|Танцы исполня|Авт\. (стихотворения|муз)|Блок дир|От автора|Реж\. дубл|Реж\. озвуч|Тех\. (ассист|консульт)|Научн(ый|\.) консульт|Адм\. группа|Администр|Ассистенты|Звукооформ|Постановщик (танц|трюк)|Пост\. танц|Куклы (и декор|изготов|выполн)|Куклы-|Хореограф|В работе (над фильмом )?принимал|В работе над фильмом (также )?участв|Фото[- ]|Фотографии|Аниматор|Оператор[ы]? )', re.I)
PRZK = re.compile(r'(премия|преми[иеюй]|приз|диплом|фестивал|награ|удостоен|медал|конкурс|смотр|лауреат|упоминани|отмечен|Оскар|Золот|Серебрян|Бронзов|грамот|Гран-при|жюри|«Советский экран»|лучш(ий|ая|ее|им|ей) (фильм|роль|актер|актрис|режисс|опер|музык|исполн|сцен))', re.I)
def strict_kind(t, hs, j):
    s = t.strip()
    if not s or re.match(r'^\s*\d{1,4}\s*$', s) or re.match(r'^\d+ Заказ', s) or len(s) < 3 or re.match(r'^[^А-ЯЁа-яё0-9]+$', s) or re.match(r'^[\d\s\-.]+Заказ', s): return 'junk'
    ns = re.sub(r'[^а-яё]', '', s.lower())
    if ns.startswith('библиограф') or re.match(r'^\s*Б\s?и\s?б\s?л\s?и?\s?о?\s?г', s) or re.match(r'^\s*Библи', s): return 'bib'
    if j in hs: return 'head'
    if re.match(r'^\s*(\d-я|[IVX]+) (серия|сер\.)\s*[.—-]?\s*$', s): return 'junk'
    if CREDK.match(s): return 'cred'
    if re.match(r'^[^А-ЯЁа-яё]{0,4}[А-ЯЁ]', s) and L.PRIZE.match(s) and PRZK.search(s): return 'prize'
    # титры-продолжение: ключевые слова титров + инициалы + точки с запятой (как pass B credline), без глаголов-сказуемых прозы
    k = len(re.findall(r'(?:^|[;,.:] ?)(?:ред|дир\. картины|монтаж|композ|консульт|звукоопер|опер|худ|реж|ассист|грим|костюм|дирижер|адм|муз\. ред|дубл)\b', s, re.I))
    ini = len(re.findall(r'[А-ЯЁXBHKMTCAEOP]\.\s?-?[А-ЯЁXBHKMTCAEOP]?[а-яё]{2,}', s))
    if k >= 1 and ini >= 1 and s.count(';') >= 1 and len(s) < 400 and not re.search(r'\b(он|она|они|его|ее|их|который|которая|которые|что|как)\b', s.lower()): return 'cred'
    if re.match(r'^[^А-ЯЁа-яё]{0,4}[А-ЯЁ][а-яё\-]+ (оркестр|ансамбль|хор|капелла)\b', s) and len(s) < 140 and not L.VERB.search(s): return 'cred'
    return 'prose'
def nm(s): return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е').translate(L._TR))
def verified_head(Ls, k, hs):
    if k not in hs: return False
    t = Ls[k][1]
    if re.search(r'\d+\s?ч[.,]|мтр\. неизв', t[:160]): return True
    return any(re.match(r'^(?:[^А-ЯЁа-яё]{0,6})(Ав|Реж|Сцен|Автор)', Ls[j][1]) for j in range(k + 1, min(k + 4, len(Ls))))
flags = []
for e in res['set']:
    if e['field'] != 'annotation' or e['after'] is None or e['class'] in ('restore', 'prefix'): continue
    c = e['cat']; x = scan.get(c); ar = art.get(str(c))
    h = x['h'] if x else (ar['h'] if ar else None)
    if h is None: continue
    v = e['vol']; Ls = L.lines(v); hs = L.headset(v)
    end = (x['e'] if x else ar['e'])
    while end < len(Ls) and end < (x['e'] if x else ar['e']) + 40 and not verified_head(Ls, end, hs): end += 1
    bn, an = nm(e['before']), nm(e['after']); lost = []
    for k in range(h + 1, end):
        t = Ls[k][1]; kd = strict_kind(t, hs, k)
        if kd != 'prose': continue
        pn = nm(t)[:25]
        if len(pn) < 8: continue
        if pn in bn and pn not in an:
            st = t.strip()
            ini = len(re.findall(r'(?:^|[\s,;(])[А-ЯЁXBHKMTCAEOP]\.\s?-?[А-ЯЁ][а-яё\-]{2,}', st)); cl = len(L.CASTLIKE.findall(st))
            if cl >= 2 or (ini >= 3 and not L.VERB.search(st)) or ini >= 6: continue          # список ролей/имён (продолжение «В ролях»)
            if re.match(r'^[^А-ЯЁа-яё]{0,3}(В (картине|фильме|создании|съемках|работе|постановке)|Полеты выполняли|Фильм подготовлен|Актеры|Роли|ВЭ|РУ|Программа|Исполнители|Номера|Участвуют|Снимались|Дубл|Читает|Поет|Поют)', st): continue
            if len(re.findall(r'\d{4}', st)) >= 2 and st.count('«') >= 2: continue      # продолжение библиографии
            if re.match(r'^[^А-ЯЁа-яё]{0,3}«[^»]+»,? ?\d{4}', st) or re.match(r'^[^А-ЯЁа-яё]{0,3}\d{1,2}\. ?[IVX]+ \d{4}', st): continue
            if re.match(r'^[^А-ЯЁа-яё]{0,3}[а-яё]', st) and (ini >= 1 and not L.VERB.search(st)): continue   # обрывок списка со строчной
            lost.append((k, t[:90]))
    if lost: flags.append({'cat': c, 'class': e['class'], 'concert': bool(x and x['concert']), 'genre': cat[c]['genre'], 'lost': lost, 'note': e['note'][:80]})
print('flagged:', len(flags))
for f in flags:
    print(f"cat{f['cat']} [{f['class']}] concert={f['concert']} genre={f['genre']!r}")
    for k, t in f['lost'][:4]: print(f'     @{k} {t}')
json.dump(flags, open('work/f6_p2_strict_audit.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
