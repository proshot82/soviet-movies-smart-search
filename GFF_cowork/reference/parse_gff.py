#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер каталогов Госфильмофонда (DjVu / PDF с текстовым слоем) -> карточки фильмов.

Понимает ДВА макета каталога и определяет формат тома автоматически:

  * "старый" (напр. 1930-1957): нумерованные карточки  "1196. ЗАГЛАВИЕ. <жанр>, N ч., ..., 19XX г., ВЭ ..."
       - разделитель между фильмами = следующий номер (орнамента нет);
       - есть строка-тема ("О...") + сюжет, блок "Библиография:", пометка о сохранности.
  * "новый" (напр. 1966-1967): карточки  "ЗАГЛАВИЕ. <жанр>, N ч., ..., 19XX г., ВЭ ..."
       - номеров нет; разделитель между фильмами = орнамент  <► <► <►  (OCR шумит).

На выходе для каждого фильма:
  - .txt  (сюжет-ориентированный, для смыслового индекса AnythingLLM: "один фильм = один файл");
  - строка в .jsonl со всеми полями (для собственного движка / отладки; туда же кладётся Библиография).

ЗАВИСИМОСТИ
  pip install pymupdf
  DjVuLibre (утилита djvutxt):
      Windows : https://djvu.sourceforge.net/  (положить папку с djvutxt.exe в PATH)
      Linux   : sudo apt install djvulibre-bin
      macOS   : brew install djvulibre

ИСПОЛЬЗОВАНИЕ
  python parse_gff.py ВХОД [ВХОД ...] -o OUTDIR [--format txt|jsonl|both] [--djvutxt PATH]
  пример:
  python parse_gff.py "1930-1957.djvu" "1966-1967.djvu" -o records --format both
"""

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

# ----------------------------------------------------------------------------
# 1. Извлечение текста ПОСТРАНИЧНО
# ----------------------------------------------------------------------------

def extract_pages_djvu(path, djvutxt="djvutxt"):
    """Возвращает список текстов страниц. Использует djvutxt (один вызов) + разбивку по \\f."""
    try:
        out = subprocess.run([djvutxt, str(path)], capture_output=True, check=True).stdout
    except FileNotFoundError:
        sys.exit(f"[!] Не найдена утилита '{djvutxt}'. Установи DjVuLibre или укажи путь через --djvutxt.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"[!] djvutxt не смог прочитать {path}: {e}")
    text = out.decode("utf-8", "replace")
    pages = text.split("\f")
    # последний сегмент после финального \f часто пустой
    if pages and pages[-1].strip() == "":
        pages = pages[:-1]
    return pages


def extract_pages_pdf(path):
    """Возвращает список текстов страниц через PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("[!] Нет PyMuPDF. Установи: pip install pymupdf")
    doc = fitz.open(str(path))
    pages = [doc[i].get_text("text") for i in range(doc.page_count)]
    doc.close()
    return pages


def extract_pages(path, djvutxt="djvutxt"):
    ext = Path(path).suffix.lower()
    if ext == ".djvu":
        return extract_pages_djvu(path, djvutxt)
    if ext == ".pdf":
        return extract_pages_pdf(path)
    sys.exit(f"[!] Неподдерживаемое расширение: {ext} (нужен .djvu или .pdf)")


# ----------------------------------------------------------------------------
# 2. Вспомогательное: печатный номер страницы (фолио), очистка
# ----------------------------------------------------------------------------

_FOLIO_RE = re.compile(r"^\s*(\d{1,4})\s*$")

def printed_page_number(page_text):
    """Пытается вытащить печатный номер страницы (короткая строка только из цифр в конце/начале)."""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    for ln in (lines[-2:] + lines[:1]) if lines else []:
        m = _FOLIO_RE.match(ln)
        if m:
            return int(m.group(1))
    return None


def squeeze(s):
    return re.sub(r"\s+", " ", s).strip()


# ----------------------------------------------------------------------------
# 3. Маркеры формата и карточки (общие)
# ----------------------------------------------------------------------------

# Орнамент-разделитель нового формата: ключевые глифы (OCR даёт ►, ♦, ◄, <►, «► и т.п.)
ORNAMENT_RE = re.compile(r"[►◄♦❖✦]")
# Маркер продолжения многосерийного фильма (2-я серия и т.п.) — НЕ начало новой карточки.
SERIES_RE = re.compile(r"^\s*(?:\d\s*[-–]?\s*[ия]\s+сер|часть\s+(?:втор|трет|четв)|[IVX]+\s+сер)", re.I)

# Старт карточки старого формата: номер + ЗАГЛАВИЕ КАПСОМ в начале строки
NUM_TITLE_RE = re.compile(r"^\s*(\d{1,4})\.\s+([А-ЯЁ0-9«\"][^\n]*)")

# Метастрока (есть в обоих форматах): "..., N ч., ..., 19XX г." — индикатор начала карточки
META_SIG_RE = re.compile(r"""\d+\s*ч[ .,"'»”„].{0,90}?1[89]\d{2}\s*г\s*[.,"'»”„]""", re.S)

# Заголовок года-врезки в старом формате (часто в начале страницы)
YEAR_HEADER_RE = re.compile(r"^\s*(1[89]\d{2})\s*(?:год|г\.)?\s*$")


def _longest_monotone_backbone(nums):
    """Длина самой длинной (по числу элементов) строго возрастающей цепочки
    каталожных номеров с допуском на OCR-пропуски. Возвращает (len, span)."""
    if not nums:
        return 0, 0
    best_len, best_span = 0, 0
    n = len(nums)
    for i in range(n):
        chain = [nums[i]]
        last = nums[i]
        for j in range(i + 1, n):
            v = nums[j]
            if v > last and (v - last) <= 12:
                chain.append(v); last = v
            elif v > last and (v - last) <= 30 and len(chain) >= 5:
                chain.append(v); last = v
        if len(chain) > best_len:
            best_len, best_span = len(chain), chain[-1] - chain[0] + 1
    return best_len, best_span


def detect_format(full_text):
    """Определяет тип вёрстки тома.

    Ключевой инвариант: 'old' (нумерованный каталог) опознаётся ТОЛЬКО по наличию
    длинного монотонного ХРЕБТА каталожных номеров. И орнамент-поток (1966-1969),
    и бесхребтовый META_SIG-поток алфавитных каталогов 1996 г. (1970-1973) — это 'new'.
    Возвращает (fmt, n_orn, n_num, n_meta, backbone)."""
    n_orn = len(ORNAMENT_RE.findall(full_text))
    nums = [int(m.group(1)) for m in NUM_TITLE_RE.finditer(full_text)]
    n_num = len(nums)
    n_meta = len(list(META_SIG_RE.finditer(full_text)))
    backbone, _ = _longest_monotone_backbone(nums)
    # 'old' только если нумерованные карточки покрывают существенную долю фильмов
    is_old = backbone >= max(20, int(0.4 * n_meta))
    fmt = "old" if is_old else "new"
    return fmt, n_orn, n_num, n_meta, backbone


# ----------------------------------------------------------------------------
# 4. Сегментация на карточки
# ----------------------------------------------------------------------------

def segment_old(pages):
    """Старый формат: опорой служит МОНОТОННАЯ нумерация. Возвращает [(num, page_idx, block_text)]."""
    # собираем строки с привязкой к странице
    page_of_line = []
    lines = []
    for pi, ptext in enumerate(pages):
        for ln in ptext.splitlines():
            lines.append(ln)
            page_of_line.append(pi)

    # кандидаты-старты: строка вида "NNN. ЗАГЛАВИЕ" (в т.ч. «NNNа.», «NNN—NNN.», двойная точка «NNN..»)
    cand = []  # (line_idx, num, is_subletter)
    rx = re.compile(r"^[\s‚.,·*'\"]{0,5}(\d{1,4})(\s*[—–-]\s*\d{1,4}|\s*[а-яё]{1,2})?\.+\s+[А-ЯЁ0-9«\"]")
    for i, ln in enumerate(lines):
        m = rx.match(ln)
        if m:
            sub = bool(m.group(2) and re.search(r"[а-яё]", m.group(2)))
            cand.append((i, int(m.group(1)), sub))

    # фильтрация по монотонности: оставляем номера, продолжающие последовательность
    kept = []
    last = None
    for ci, (li, num, sub) in enumerate(cand):
        if last is None:
            kept.append((li, num, False)); last = num; continue
        # допускаем разрыв (OCR мог пропустить), но номер должен расти и не прыгать дико
        if 0 < (num - last) <= 60:
            kept.append((li, num, False)); last = num
        elif sub and num == last:
            # подбуквенная вставка («3422а.» после «3422.») — самостоятельная карточка, last не двигаем
            kept.append((li, num, False))
        elif num <= last:
            # повтор/откат — как правило, ложный номер (год, сноска) — пропускаем. НО если
            # СЛЕДУЮЩИЙ кандидат — строгий преемник (num+1/num+2), это начало консистентного
            # ряда на перепутанной тетради скана (A№16; V1: блоки 756–765 и 970–1001 идут в
            # потоке ПОСЛЕ старших номеров). Принимаем (с пометкой rescue — контент блока
            # будет проверен при сборке) и перезаводим хребет вниз; одиночный ложный номер
            # преемника не имеет и по-прежнему отбрасывается.
            if ci + 1 < len(cand) and cand[ci + 1][1] in (num + 1, num + 2):
                kept.append((li, num, True)); last = num
            continue
        else:
            # слишком большой прыжок — вероятно мусорный номер; пропускаем. НО строгий
            # преемник следом (num+1/num+2) = реальный ряд (продолжение A№16): без
            # восходящего rescue ложная пара внизу запирает хребет навсегда (прямой
            # скачок >60 отвергается, а нисходящий rescue вверх не работает).
            # Одиночный мусорный номер преемника не имеет и отбрасывается как раньше.
            if ci + 1 < len(cand) and cand[ci + 1][1] in (num + 1, num + 2):
                kept.append((li, num, True)); last = num
            continue

    records = []
    suspect_after = None   # номер последнего отфильтрованного фантома: его прямые преемники
                           # без маркеров — продолжение того же фантомного ряда (новеллы
                           # альманаха въезжают по штатному правилу после rescue-переустановки
                           # last вниз, поэтому одного флага via_rescue недостаточно)
    for k in range(len(kept)):
        li, num, via_rescue = kept[k]
        end = kept[k + 1][0] if k + 1 < len(kept) else len(lines)
        block = "\n".join(lines[li:end])
        has_markers = bool(META_SIG_RE.search(block) or re.search(r"В\s*ролях", block))
        # Подозрителен: rescue-кандидат (A№16) ЛИБО прямой преемник только что
        # отфильтрованного фантома. Подозрительный блок без метастроки и без «В ролях» —
        # не карточка, а нумерованный фрагмент ВНУТРИ карточки (новеллы альманаха
        # «1. … 2. …», осколки списка ролей). Запись не создаём; текст приклеиваем к
        # предыдущей карточке — альманах остаётся цельным, хвосты не теряются.
        # Штатные допуски ВНЕ фантомного контекста не фильтруются: у реальных карточек
        # метастрока бывает бита OCR (V3 «2 Я.» вместо «2 ч.», V1 несохранившиеся без
        # «В ролях»), их выбрасывать нельзя. Реальная карточка с маркерами немедленно
        # снимает подозрение.
        suspicious = via_rescue or (suspect_after is not None and num in (suspect_after + 1, suspect_after + 2))
        if suspicious and not has_markers:
            if records:
                pnum, ppage, pblock = records[-1]
                records[-1] = (pnum, ppage, pblock + "\n" + block)
            suspect_after = num
            continue
        suspect_after = None
        records.append((num, page_of_line[li], block))
    return records


def segment_new(pages):
    """Новый формат (без номеров): старт карточки = метастрока (она может занимать 2 строки,
    поэтому ищем её потоком) ИЛИ первая непустая строка после орнамента ►.
    Объединяем оба сигнала — так покрытие близко к реальному числу фильмов."""
    import bisect
    page_of_line, lines = [], []
    for pi, ptext in enumerate(pages):
        for ln in ptext.splitlines():
            lines.append(ln); page_of_line.append(pi)
    text = "\n".join(lines)
    offs, off = [], 0
    for ln in lines:
        offs.append(off); off += len(ln) + 1
    line_of = lambda pos: bisect.bisect_right(offs, pos) - 1

    # Сигнатура метража часто стоит на ВТОРОЙ строке перенесённой метастроки,
    # а заглавие+жанр — строкой выше. Если так — поднимаем границу карточки на строку с заглавием,
    # иначе заглавие теряется (приклеивается к предыдущей карточке).
    def _climb_wrap(R):
        # Заглавие перенесено на 2+ строки. Два случая: (а) посреди слова с дефисом/мягким
        # переносом («ПРОФЕС‐ / СИЮ»); (б) по границе слова без дефиса («ЖИЗНЬ И УДИВИТЕЛЬНЫЕ
        # ПРИКЛЮЧЕНИЯ / РОБИНЗОНА КРУЗО»). _pull_up берёт нижнюю строку — голова теряется.
        # Поднимаем границу, пока строка выше «титульная»: преимущественно CAPS-кириллица,
        # без собственной метастроки-года и без титров (реж./опер./«В ролях»). Так берём оба
        # вида переноса; строки сюжета (строчная проза) и титры границу не пробивают.
        def _title_line(s):
            s = s.strip()
            if not s:                                         return False
            if re.search(r"1[89]\d{2}\s*г", s):               return False   # своя метастрока
            if re.search(r"В\s*ролях|реж\.|опер\.|сцен\.|худ\.|композ", s):  return False  # титры
            letters = [c for c in s if c.isalpha()]
            if len(letters) < 2:                              return False
            up = sum(1 for c in letters if c.isupper())
            return up / len(letters) >= 0.7
        while R - 1 >= 0 and _title_line(lines[R - 1]):
            R -= 1
        return R

    def _pull_up(L):
        cur = lines[L].strip()
        before_reels = re.split(r"\d+\s*ч[ .,]", cur, maxsplit=1)[0]
        if re.search(r"[А-ЯЁ]{3,}", re.sub(r"^[^А-ЯЁ]+", "", before_reels)):
            return _climb_wrap(L)                      # заглавие на самой строке метража — карточка цельная
        # идём вверх (до 9 строк) через строки-продолжения метастроки (посерийный метраж/формат/
        # подзаголовки серий/мусор буквицы), пока не встретим строку с заглавным словом.
        # Окно расширено: у многосерийных фильмов метастрока тянется на 5-6 строк («1 сер. - 9 ч.,
        # …; 11 сер. - 7 ч., …, 19XX г.»), и META_SIG цепляется за ПОСЛЕДНИЙ «N ч. … год»,
        # из-за чего при окне в 3 строки строка-заглавие (БРАТЬЯ КАРАМАЗОВЫ, ВИЗИТ ВЕЖЛИВОСТИ,
        # ПРИВАЛОВСКИЕ МИЛЛИОНЫ, ИСТОКИ, СКАЗАНИЕ О РУСТАМЕ) терялась — её забирала прошлая карточка.
        for k in range(L - 1, max(-1, L - 10), -1):
            prev = lines[k].strip()
            if not prev:
                continue
            if re.search(r"[А-ЯЁ]{3,}", re.sub(r"^[^А-ЯЁ]+", "", prev)):
                pr_before = re.split(r"\d+\s*ч[ .,]", prev, maxsplit=1)[0]
                if (re.search(r"[А-ЯЁ]{3,}", re.sub(r"^[^А-ЯЁ]+", "", pr_before))
                        and re.search(r"1[89]\d{2}\s*г", prev)):
                    return L                          # это полная метастрока ДРУГОГО фильма — не трогаем
                return _climb_wrap(k)                 # строка-заглавие найдена
            # строка без CAPS-прогона — это продолжение метастроки/огрызок буквицы: лезем выше.
        return L
    sig_starts = {_pull_up(line_of(m.start())) for m in META_SIG_RE.finditer(text)}
    after_orn = set()
    for i, ln in enumerate(lines):
        if ORNAMENT_RE.search(ln):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                after_orn.add(j)

    starts = sorted(sig_starts | after_orn)
    merged = []
    for s in starts:
        if merged and s - merged[-1] <= 1:   # склеиваем дубли-границы
            continue
        merged.append(s)

    records = []
    for k, a in enumerate(merged):
        b = merged[k + 1] if k + 1 < len(merged) else len(lines)
        block = "\n".join(lines[a:b]).strip()
        if block and (re.search(r"В\s*ролях", block) or META_SIG_RE.search(block)):
            records.append((None, page_of_line[a], block))
    return records


def split_by_cast(records):
    """Добивка (в основном для нового формата): если в блоке осталось 2+ «В ролях»
    (вторая метастрока не распозналась целиком), режем по строке с метражом «N ч.»
    непосредственно перед каждым лишним «В ролях» — это начало метастроки второй карточки."""
    out = []
    for num, page, block in records:
        vr = [m.start() for m in re.finditer(r"В\s*ролях", block)]
        if len(vr) <= 1:
            out.append((num, page, block)); continue
        cuts = [0]
        for v in vr[1:]:
            region = block[cuts[-1]:v]
            cand = None
            for m in re.finditer(r"\n([^\n]*?\d+\s*ч[ .,])", region):
                line_head = re.split(r"\d+\s*ч[ .,]", m.group(1), maxsplit=1)[0]
                # режем только если на строке метража есть ЗАГЛАВИЕ (CAPS-слово) — это метастрока
                # 2-го фильма. Иначе это собственная метастрока альманаха, а «В ролях» — его новеллы.
                if re.search(r"[А-ЯЁ]{3,}", re.sub(r"^[^А-ЯЁ]+", "", line_head)):
                    cand = cuts[-1] + m.start() + 1     # ближайшая к «В ролях» метастрока с заглавием
            if cand and cand > cuts[-1] + 40:
                cuts.append(cand)
        cuts.append(len(block))
        for i in range(len(cuts) - 1):
            sub = block[cuts[i]:cuts[i + 1]].strip()
            if sub:
                out.append((num if i == 0 else None, page, sub))
    return out


def split_at_ornament(records):
    """Режет карточки, где OCR слил два фильма в одну строку без переноса, но между ними
    сохранился орнамент-разделитель (►◄♦, возможно с мусором между глифами). Применяется
    последним проходом. Альманахи не трогает: у них одна метастрока, и справа от их внутренних
    границ нет сигнатуры «N ч … 19XX г.»."""
    orn = re.compile(r"[►◄♦❖✦](?:[\s<>«»^]*[►◄♦❖✦])+")   # минимум два глифа подряд = разделитель
    out = []
    for num, page, block in records:
        parts, last = [], 0
        for m in orn.finditer(block):
            left, right = block[last:m.start()], block[m.end():]
            if len(left.strip()) > 80 and META_SIG_RE.search(right[:400]):
                parts.append(block[last:m.start()]); last = m.end()
        parts.append(block[last:])
        if len(parts) > 1:
            for i, pt in enumerate(parts):
                if pt.strip():
                    out.append((num if i == 0 else None, page, pt.strip()))
        else:
            out.append((num, page, block))
    return out


def merge_series_continuations(records):
    """Если карточка начинается с «2-я серия…»/«часть вторая…», это продолжение
    предыдущего фильма, ошибочно отрезанное сегментацией — приклеиваем назад."""
    out = []
    for num, page, block in records:
        if out and SERIES_RE.match(block[:40]):
            pn, pp, pb = out[-1]
            out[-1] = (pn, pp, pb + "\n" + block)
        else:
            out.append((num, page, block))
    return out


def rejoin_orphan_title_heads(records):
    """Старые сканы (тома 2, 4): голова длинного названия с каталожным номером, перенесённая
    через разрыв страницы, осталась в хвосте предыдущего блока («…3435. ДОБРО ПОЖАЛОВАТЬ, ИЛИ
    ПОСТОРОННИМ ВХОД ВО-»), а продолжение («СПРЕЩЕН. Кинокомедия…» / «РОВИЧЕМ …») стало карточкой
    без головы. Признак однозначный: блок кончается «NNNN. <CAPS-название>-» (дефис = перенос
    слова на границе страницы), следующий блок начинается с CAPS-продолжения. Переносим голову
    в начало следующего блока, склеивая перенесённое слово без пробела. Паттерн встречается лишь
    у таких переносов — у томов без них (V6-V15) проход не срабатывает (регрессий нет)."""
    ORPHAN = re.compile(r"(\d{3,4}\.\s+[А-ЯЁ][А-ЯЁ0-9 ,«»]{5,}?)[-\u00ad]\s*$")
    out = list(records)
    for i in range(len(out) - 1):
        num, page, block = out[i]
        m = ORPHAN.search(block)
        if not m:
            continue
        nnum, npage, nblock = out[i + 1]
        if not re.match(r"^\s*[А-ЯЁ]", nblock):       # продолжение должно начинаться со слова
            continue
        head = m.group(1).strip()
        out[i] = (num, page, block[:m.start(1)].rstrip())     # убрать голову из блока-владельца
        out[i + 1] = (nnum, npage, head + nblock.lstrip())    # перенос слова: склейка без пробела
    return out


def split_internal(records):
    """Спасает «склейки»: если в одном блоке несколько метастрок (…N ч., …, 19XX г.),
    значит две карточки слиплись (OCR съел номер/орнамент). Режем по началу строки
    со второй и далее метастрокой. Год/студия/сюжет у обеих половин извлекутся корректно."""
    out = []
    for num, page, block in records:
        positions = [m.start() for m in META_SIG_RE.finditer(block)]
        if len(positions) <= 1:
            out.append((num, page, block)); continue
        cuts = [0]
        for p in positions[1:]:
            ls = block.rfind("\n", 0, p)
            ls = 0 if ls < 0 else ls + 1
            cut = None
            if ls > cuts[-1] + 40 and not SERIES_RE.match(block[ls:ls + 40]):
                cut = ls                      # обычный случай: 2-я метастрока с начала своей строки
            else:
                # нет переноса ИЛИ строка начинается с «N-я сер.» (разбивка серий ВНУТРИ метастроки
                # одного фильма, ошибочно похожая на продолжение). Ищем НАЗАД границу нового фильма:
                # конец предложения, за которым идёт НЕ жанровое заглавие.
                window = block[cuts[-1]:p]
                for m in reversed(list(re.finditer(r"[.!?]\s+", window))):
                    after = re.sub(r"^[^А-ЯЁ]+", "", window[m.end():m.end() + 30])
                    w = re.match(r"[А-ЯЁ][А-Яа-яё-]*", after)
                    if w and not re.match(r"(?:" + GENRES + r")", w.group()):
                        cand = cuts[-1] + m.end()
                        if cand > cuts[-1] + 40 and not SERIES_RE.match(block[cand:cand + 40]):
                            cut = cand
                        break
            if cut is not None:
                cuts.append(cut)
        cuts.append(len(block))
        for i in range(len(cuts) - 1):
            sub = block[cuts[i]:cuts[i + 1]].strip()
            if sub:
                out.append((num if i == 0 else None, page, sub))
    return out


# ----------------------------------------------------------------------------
# 5. Разбор полей карточки (субтрактивный метод для аннотации)
# ----------------------------------------------------------------------------

GENRE_HINT = r"[А-ЯЁ][А-Яа-яё.-]*\.?"
# Жанровые слова каталога — нужны, чтобы найти конец заглавия, даже если OCR потерял точку.
GENRES = (r"Мелодрам|Кинодрам|Драм|Кинокомеди|Комеди|Киноочерк|Кинохроник|Киноновелл|Кинонов|"
          r"Киноповест|Кинороман|Кинопоэм|Киносказ|Кинопамфлет|Кинофельетон|Кинокартин|Экраниз|"
          r"Детектив|Детск|Приключ|Истор|Ист\.|Биограф|Эксперимент|Документ|Мультф|Сатир|"
          r"Музык|Муз\.|Агит|Видов|Научн|Спектакл|Концерт|Обозрен|Киноальманах|Альманах|Сказк|"
          r"Легенд|Фантаст|Эпопе|Киноэпопе|Новелл|Фильм-|Телеф|Киножурн|"
          r"Графич|Кукольн|Объ[её]мн|Рисован|Перекладк|Силуэтн|Пластилин|Мультиплик")
# Тома изданий 2001/2003 с декоративной буквицей, распознанной как отдельные символьные токены
# перед названием. Иной OCR-профиль, чем у ранних томов: к ним (и только к ним) применяется
# токен-срез ведущего мусора буквицы. Будущие поздние издания добавляются сюда.
_DROPCAP_JUNK_VOLUMES = {"v14_1984-1985", "v15_1986-1987"}

TITLE_BOUNDARY = re.compile(r"\s+[-‚.,*]?\s*(?:" + GENRES + r"|\d+\s*ч[ .,])"
                            r"|[-‚.,]\s*(?i:" + GENRES + r")(?=[а-яё])")
# Форматные пометки (НЕ жанр) — вырезаем из жанровой части: цвет, ширина экрана, звук.
FORMAT_QUAL = re.compile(
    r"\b(?:цв|ч/б|ч\.-?б|чёрно-?бел\w*|чернобел\w*|цветн\w*|широкоэкран\w*|широкоформатн\w*|"
    r"ш\.-?э|ш\.-?ф|ш/э|ш/ф|звук\w*|немой|двухсерийн\w*|односерийн\w*|короткометр\w*|полнометр\w*)\.?",
    re.I)
# Признаки анимации: техника в жанре или мультстудия -> жанр "мультфильм".
ANIM_TECH = re.compile(r"графич|кукольн|рисован|объ[её]мн|перекладк|силуэтн|пластилин|мультиплик|мультфильм", re.I)
ANIM_STUDIO = re.compile(r"мультфильм|мультиплик", re.I)

TITLE_OLD_RE = re.compile(r"^\s*(?:\d{1,4}\.\s*)?(.+?)\.\s+" + GENRE_HINT + r"[ ,]", re.S)
TITLE_NEW_RE = re.compile(r"^\s*(.+?)\.\s+" + GENRE_HINT + r"[ ,]", re.S)

ALT_TITLE_RE = re.compile(r"[(«]\s*([^)»]+?)\s*[)»]")
YEAR_RE      = re.compile(r"(1[89]\d{2})\s*г\.")
REELS_RE     = re.compile(r"(\d+)\s*ч[ .,]")
METRES_RE    = re.compile(r"(\d{2,4})\s*м[ .,]")
VE_RE        = re.compile(r"ВЭ\s*([0-9IVXivx][0-9IVXivx.\- ]*\d{4})")
STUDIO_RE    = re.compile(r",\s*([^,]*(?:фильм|студи|кино)[^,]*?)\s*(?:\([^)]*\)\s*)?,\s*1[89]\d{2}\s*г\.", re.I)

CAST_RE      = re.compile(r"В\s*ролях[:.\- ]+(.+?)(?=(?:Библиограф)|(?:Фильм[^.]*сохран)|\Z)", re.S)
CREDITS_RE   = re.compile(r"(Авт[. ]?\s*сцен.+?)(?=В\s*ролях|Библиограф|\Z)", re.S)
DIRECTOR_RE  = re.compile(r"реж[.\- ]*(?:-?пост\.?)?\s*([^;]+)", re.I)
BIBLIO_RE    = re.compile(r"Библиограф[^:]*:\s*(.+)\Z", re.S)
PRESERV_RE   = re.compile(r"(Фильм[^.]*(?:не\s+)?сохранил[^.]*\.)", re.I)
PAGEONLY_RE  = re.compile(r"^\s*\d{1,4}\s*$")
LOGLINE_RE   = re.compile(r"^\s*(?:О|Об|О\s+том|Про)\b")
# Зачин синопсиса (граница между списком актёров и сюжетом). Короткие зачины требуют строчную
# букву после себя, иначе «О »/«Про» ловят инициалы актёров («О. Эскола», «Про-копенко»).
SYNOPSIS_RE  = re.compile(
    r"(?:О|Об)\s+[а-яё]|О\s+том\b|Про\s+[а-яё]|Экранизаци|По\s+мотив|По\s+однои|По\s+повест|"
    r"По\s+роман|Фильм\s+(?!не\b|дубли|сня[тл]|восстановл|озвуч|выпущ|сохран|расцвеч|колориз)[а-яо]|"
    r"История\s+[а-яо]|Рассказ\s+[оп]|Действие\b|Геро[йия]\s+[а-яё]|"
    r"Героиня\b|Главн(?:ый|ая|ое|ые)\s+(?!преми|приз|наград|диплом|рол)[а-яё]|Сатир|Молод|Действ\b"
)


def tidy(text):
    """Чистит прозу: убирает библиографию, пометку о сохранности, строки-номера
    страниц и затесавшиеся остатки титров."""
    text = re.split(r"Библиограф", text)[0]
    text = PRESERV_RE.sub(" ", text)
    keep = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or PAGEONLY_RE.match(s):
            continue
        if re.match(r"^(опер|худ|композ|звукоопер|ассист|пом\.?\s*реж|дир\.?\s*групп|дириж|ред\.|звукомонтаж|монтаж)", s, re.I):
            continue
        keep.append(s)
    out = squeeze(" ".join(keep))
    out = re.sub(r"\s*[♦►◄❖✦][\s♦►◄❖✦*•^~<>«»+]*$", "", out)  # хвостовой орнамент-разделитель
    out = re.sub(r"(?:\s+(?:[♦►◄❖✦^«»<>+~*•]+|\d+-|[A-ZА-Я]))+\s*$", "", out)  # огрызки орнамента «4- О 4-»
    out = re.sub(r"\s+(?:[А-ЯЁ][А-ЯЁ-]{2,}\s+)+[А-ЯЁ][А-ЯЁ-]{2,}\s*$", "", out)  # хвостовой заголовок раздела (КАПС)
    return out.strip()


AWARD_MARK_RE = re.compile(
    r"присужд|вручен|удостоен|номинир"
    r"|Гран-при|«\s*Гран[ -]?при|«\s*Золот\w*\s+лев"
    r"|кинофестивал|\bМКФ\b|\bВКФ\b"
    r"|\(\s*(?:[А-Яа-яё.\- ]+,\s*)?19\d{2}\s*\)"
    r"|(?:призна|назван)\w*\s+(?:\S+\s+){0,3}?лучш"
    r"|получил\w*\s+(?:\S+\s+){0,3}?признани"
    r"|за\s+лучш\w*\s+(?:фильм|рол|исполнен|режисс|сценар|опера|музык|дебют|работ|комед|докум)"
    r"|(?:Почётн|Почетн)\w*\s+диплом|(?:Главн|Специальн|Больш|Перв|Втор|Трет)\w*\s+приз"
    r"|(?:Сталинск|Ленинск|Госуд\w*)\w*\s+преми"
    r"|«[^»]{2,40}»\s*[—–-]\s*\w*\s*(?:преми|приз|диплом)"
    r"|(?<![А-Яа-яё])(?:Дипломы?|Грамоты?|Призы?|Медал[ьи]|Значки?)\s+(?:[А-ЯЁ]|за\s+луч|получил|присужд|вручен)"
)


def _award_start(text, from_pos=0):
    """Индекс начала первой наградной секции в тексте (или len(text), если её нет)."""
    m = AWARD_MARK_RE.search(text, from_pos)
    return m.start() if m else len(text)


def _strip_awards(ann):
    """Отрезаем хвостовую наградную секцию (призы/дипломы/премии фестивалей, смотров, выставок).
    Режем от начала фрагмента самого раннего сильного наградного маркера. Устойчиво к OCR-дроблению."""
    if not ann:
        return ann
    m = AWARD_MARK_RE.search(ann)
    if not m:
        return ann
    p = m.start()
    # маркеры-открывашки (« или Заглавное наградное слово) сами начинают фрагмент — режем прямо от них
    if ann[p] == "«" or re.match(r"(?:Дипл|Грам|Приз|Меда|Знач|Глав|Спец|Больш|Перв|Втор|Трет|Почёт|Почет|Стал|Ленин|Госуд)", ann[p:p + 6]):
        cut = p
    else:
        # иначе — ближайшая слева граница абзаца/предложения (после строчной/цифры/»/)/2+ заглавных; «|»; «►»)
        bnds = [0]
        for b in re.finditer(r"(?:[a-zа-яё0-9)»]|[А-ЯЁ]{2,})[.!?…]+\s+|[|►▶❖<]+\s*", ann[:p + 1]):
            bnds.append(b.end())
        cut = max(bnds)
    return re.sub(r"[\s.,;:—–·*\-|►<]+$", "", ann[:cut]).strip()


# Выходные данные (колофон) типографии — приклеиваются к последней карточке тома. Только СИЛЬНЫЕ
# маркеры имприта: «Заказ №», «Цена», «Изд. №» исключены — они встречаются колонтитулом в середине
# длинного сюжета (разрыв страницы) и резали бы реальный текст.
COLOPHON_RE = re.compile(
    r"Сдано\s+в\s+на|Подп(?:исано)?\.?\s*в\s*печ|Тираж\s+[\d ]{2,}\s*экз|Уч\.?\s*-?\s*изд\.?\s*л\.|"
    r"Печ\.?\s*л\.|Форм(?:ат)?\.?\s*(?:бум|\d)|Гарнитура|Печать\s+офсетн|Отпечатано|"
    r"полиграфическ\w*\s+комбинат|типографи\w*\s*(?:№|Мос|«)|Московская\s+типограф|"
    r"Архитектора\s+Власова|[Ee]-?\s*mail|adminet|@\w+\.\w|отдел\s+научной\s+обработк"
)


def _strip_backmatter(ann):
    """Отсекает заднюю часть книги, проглоченную последней карточкой тома: алфавитный/именной
    указатель и выходные данные типографии. Три детектора указателя покрывают все форматы:
    «Назв - NNNN» (изд.1990-х), «Назв NNNN»/именной указатель с em-dash и OCR-мусором (изд.1961, V4),
    «Назв - Назв - Назв» без номеров. Режем по самому раннему маркеру."""
    if not ann:
        return ann
    cut = len(ann)
    m = COLOPHON_RE.search(ann)
    if m:
        cut = min(cut, m.start())
    idx = re.search(r"(?:(?:\d{1,5}\s+)?[А-ЯЁ][^-–—\n]{1,55}?\s+[-–—][~\s]*\d{1,5}\s+){3,}", ann[:cut])  # ≥3 «Назв - NNNN»
    if idx:
        cut = min(cut, idx.start())
    dense = re.search(r"(?:[^\d\n]{1,35}?\S*\d{2,}\S*\s){7,}", ann[:cut])      # плотный поток ссылочных номеров (≥7) — грязный нумер. указатель
    if dense:
        cut = min(cut, dense.start())
    idxn = re.search(r"(?:[А-ЯЁ][^-–—\n]{1,55}?\s+[-–—]\s+){6,}", ann[:cut])   # ≥6 «Назв - Назв» без номеров
    if idxn:
        cut = min(cut, idxn.start())
    return ann[:cut].rstrip(" .,;:—–-")


def clean_annotation(block, parts_to_strip):
    """Субтрактивно: убираем из блока известные структурные части, остаток-проза = аннотация."""
    text = block
    for p in parts_to_strip:
        if p:
            text = text.replace(p, " ")
    # убираем метастроку (заглавие + жанр/метраж/студия/год/ВЭ) — это первая «техническая» строка
    text = re.sub(r"^.*?(?:ВЭ\s*[^.\n]*?\d{4}\s*г\.|1[89]\d{2}\s*г\.)", " ", text, count=1, flags=re.S)
    # построчно: выкидываем строки-номера страниц, остатки титров (звукоопер., ассист., дир. группы и т.п.)
    keep = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if PAGEONLY_RE.match(s):
            continue
        if re.match(r"^(опер|худ|композ|звукоопер|ассист|пом\.?\s*реж|дир\.?\s*групп|дириж|ред\.|звукомонтаж|монтаж)", s, re.I):
            continue
        keep.append(s)
    ann = squeeze(" ".join(keep))
    # отрезаем возможный хвост библиографии, если просочился
    ann = re.split(r"БИБЛИО\w*|Библиограф", ann, maxsplit=1)[0].strip()
    return ann


# Мис-OCR глифа «№» перед номером выпуска: латинская N + 0-2 «хвостовых» символа.
# (в томах 1996 г. «№» массово распознан как N!, Nt, NI, N2, No, N° — это тот же глиф)
_NUMERO_RE = re.compile(r"\bN[\u2116!ltiI12oO°·]{0,2}(?=\s*\d)")

def _repair_title(title, raw_full):
    """Безопасная починка заглавия БЕЗ фабрикации:
    1) нормализует мис-OCR глифа «№» («ФИТИЛЬ N! 92» → «ФИТИЛЬ № 92»);
    2) восстанавливает пустое заглавие киножурнала «Фитиль», если декоративная
       буквица съела «Ф», но в сыром тексте читается «ИТИЛЬ» + чистый 2–3-значный
       номер выпуска (источник однозначно называет серию и номер).
    Порченый номер (одна цифра, символьный мусор) НЕ достраивается — честный остаток."""
    if title:
        title = _NUMERO_RE.sub("№", title)
        title = re.sub(r"№\s*[·•∙]?\s*", "№ ", title)     # единый пробел после №, без мусора
        title = re.sub(r"\s{2,}", " ", title).strip()
        # киножурналы «Ералаш»/«Фитиль» с битым номером: «No» вместо «№», номер срезан «*»
        # или распознан кириллицей («ЗЗ»→33). Срабатывает ТОЛЬКО если нормального «№ NN» ещё нет.
        jm = re.match(r"(ЕРАЛАШ|ФИТИЛЬ)\b", title)
        if jm and not re.search(r"№\s*\d", title):
            hm = re.search(r"(?:ЕРАЛАШ|ФИТИЛ[ЬD])\W{0,3}(?:№|No|N[°oO!ltiI]{0,2})?\W{0,3}"
                           r"([0-9ЗОоб]{1,3})", raw_full[:50], re.I)
            if hm:
                digits = re.sub(r"\D", "", hm.group(1).translate(str.maketrans("ЗОоб", "3006")))
                if digits:
                    title = f"{jm.group(1)} № {digits}"
        return title
    m = re.search(r"ИТИЛ[ЬD]\W{0,4}(?:№|N[!ltiI12oO°]{0,2})?\W{0,4}(\d{2,3})(?!\d)", raw_full[:70], re.I)
    if m:
        return f"ФИТИЛЬ № {m.group(1)}"
    return title


def _recover_guillemet_title(seg):
    """Запасное извлечение заглавия — срабатывает ТОЛЬКО когда обычная очистка дала пусто.
    Типичный случай: название целиком в кавычках с испорченной OCR буквицей
    («ТЕМА», «КРЕПОСТЬ», «СКВОРЕЦ» И «ЛИРА»). Берём CAPS-слова, срезая мусор буквицы.
    Если чистого CAPS-слова нет — остаётся пусто (честный остаток). Логику «Ы»/«ТРЕСТ»
    не затрагивает, т.к. там заглавие непустое и сюда исполнение не доходит."""
    if re.search(r"итил", seg, re.I):                            # Фитиль с непоправимым номером —
        return ""                                                #   честный пропуск, не «ИТИЛЬ»
    seg = re.sub(r"[«»\"'`„“”]", " ", seg)                       # кавычки → пробел
    out = []
    for t in seg.split():
        core = t.strip("()[]{}/\\®©§*^~<>|.,—- ")
        if not core:                                       continue
        if re.search(r"[()\[\]{}/\\®©§*^<>|~]", core):     continue   # буквица с внутренним мусором
        if re.search(r"[a-z]", core):                      continue   # латиница-огрызок
        core = re.sub(r"^[а-яё]+(?=[А-ЯЁ]{3,})", "", core)           # «ссКРЕПОСТЬ» → «КРЕПОСТЬ»
        caps = sum(c.isupper() for c in core); low = sum(c.islower() for c in core)
        if caps >= 3 and caps >= low:                      out.append(core)
        elif core in ("И", "В", "С", "НА", "ИЗ", "ПО"):    out.append(core)   # связки-предлоги
    title = re.sub(r"\s{2,}", " ", " ".join(out)).strip(" .,—-")
    return title if len(title) >= 3 else ""


def parse_record(num, page_idx, block, fmt, volume, pages):
    block = block.strip()
    # склейка слов, разорванных мягким переносом (U+00AD) при юстировке PDF 1996 г.:
    # «писа­ теля» → «писателя». Делается ПОСЛЕ сегментации — границы карточек не меняются.
    # Мягкий перенос — типографский управляющий символ; настоящие дефисы (U+002D) не трогаются.
    block = re.sub("\u00ad\\s*", "", block)
    raw_full = block                                          # полный текст карточки — для raw и поля «bibliography»
    # БИБЛИОГРАФИЮ режем ДО разбора сюжета: иначе детектор начала сюжета цепляется за текст внутри
    # библиографии (заголовок рецензии и т.п.), а карточки вовсе без сюжета получают её как «сюжет».
    block = re.split(r"БИБЛИО\w*|Библиограф", block, maxsplit=1)[0].strip()
    head = squeeze(block[:400])  # метастрока живёт в начале; схлопываем переносы строк

    # граница заглавия = самое раннее из: «точка+пробел», жанровое слово, метраж «N ч.»
    rawhead = re.sub(r"^[\s‚.,·*'\"]{0,5}\d{1,4}(?:\s*[—–-]\s*\d{1,4}|\s*[а-яёa-z]{1,2}|\s*\d{1,2})?\.+\s*", "", head)
    # Старые сканы (том 2, 1930-1957): каталожный номер, склеенный с названием из-за потерянного
    # при OCR разделителя. «Н68. ДЕТСТВО» → «ДЕТСТВО» (ведущая буква-артефакт + номер + точка);
    # «1820НЕБЕСНЫЙ» → «НЕБЕСНЫЙ» (номер вплотную к слову из ≥2 кир. CAPS, без разделителя).
    rawhead = re.sub(r"^[А-ЯЁ]\d{1,4}\.+\s+(?=[А-ЯЁ])", "", rawhead)
    rawhead = re.sub(r"^\d{1,4}(?=[А-ЯЁ]{2,})", "", rawhead)
    # Издания 2001/2003 (V14/V15): декоративная буквица распознана как ОТДЕЛЬНЫЕ символьные токены
    # перед названием («CQ) CQ) к;?. (/  ПЕТРОГРАДСКИЕ ...»), и точка внутри мусора режет сегмент.
    # Токен-срез: «слово заглавия» = токен с ≥3 кириллическими CAPS (даже сквозь OCR-цифры: ГР03А);
    # срезаем ведущие токены-мусор (символы/латиница, <3 кир. CAPS), сохраняя предшествующий
    # короткий пуре-кириллический предлог. Применяется ТОЛЬКО к этим изданиям — иной OCR-профиль,
    # чем у ранних djvu-томов, где буквица склеена со словом (там срез вредит).
    if volume in _DROPCAP_JUNK_VOLUMES:
        _rh_toks = rawhead.split()
        _first = next((i for i, t in enumerate(_rh_toks)
                       if sum(1 for c in t if ('А' <= c <= 'Я') or c == 'Ё') >= 3), None)
        if _first and _first > 0:
            _pre = _rh_toks[:_first]
            if any(re.search(r"[(){}\[\]/\\®©§~@<>|;]", t) for t in _pre):
                _kf = _first - 1 if re.fullmatch(r"(?:НА|ОБ?|ВО?|С|К|ПО|ОТ|ЗА|И|ИЗ|У|О)",
                                                 _rh_toks[_first - 1]) else _first
                rawhead = " ".join(_rh_toks[_kf:])
    bm = TITLE_BOUNDARY.search(rawhead)
    pdot = re.search(r"\.\s", rawhead)
    rmreels = re.search(r"\d+\s*ч\b", rawhead)         # метраж надёжно заканчивает заглавие
    vye = re.search(r"\bВ[ЭУ]\b|1[89]\d{2}\s*г", rawhead)  # «ВЭ/ВУ»/год — в заглавии их не бывает (страховка)
    ends = []
    if bm:
        ends.append(bm.start())
    if pdot and " " in rawhead[:pdot.start()]:         # точка = конец многословного заглавия, а не инициал
        ends.append(pdot.start())
    if rmreels:
        ends.append(rmreels.start())
    if vye:
        ends.append(vye.start())
    title = squeeze(rawhead[:min(ends)]) if ends else squeeze(rawhead[:60])
    _title_seg = title                                                 # сырой сегмент — для запасного прохода
    if volume == "v1_1918-1935":
        # Издание 1961 г. (немые, A№17): альт-названия ВСЕГДА в круглых скобках после
        # основного — «ОКТЯБРЬ («Десять дней, которые потрясли мир»)»; «…» ВНЕ скобок —
        # часть ОСНОВНОГО названия: «БРОНЕНОСЕЦ «ПОТЕМКИН»». Общий HARDJUNK-фильтр на
        # этом макете калечит заглавие: роняет токены с «» («ПОТЕМКИН»), оставляя голые
        # хвосты скобочного альт-названия («дней, которые потрясли», «в»). Срез по первой
        # скобке снимает альт-хвост целиком (альты уже извлечены в alt_titles из head),
        # кавычки основного названия снимаются как в _recover_guillemet_title.
        # Только v1: в поздних томах «…» в хвосте — дубль альт-названия, его штатно
        # снимает HARDJUNK; их макет не трогаем.
        title = re.split(r"\s*\(", title, 1)[0]
        title = re.sub(r"[«»]", " ", title)
        title = re.sub(r"\s{2,}", " ", title).strip()
    elif fmt == "new":
        # Тома 1966-1987 (новый режим, A№19): «…» В ПРЕДЕЛАХ заглавия (после среза по
        # жанру/метражу) — часть ОСНОВНОГО названия: «В бой идут одни «Старики»»,
        # «СКВОРЕЦ» И «ЛИРА». Снимаем символы кавычек, сохраняя слова; альт-названия в
        # круглых скобках срезаем (они уже извлечены в alt_titles). Без этого HARDJUNK ниже
        # роняет токены с «», и заглавие обрезается («В бой идут одни «Старики»» → «В бой
        # идут одни»). Граница заглавия уже отсекла жанр, поэтому затронут только сам титул.
        title = re.split(r"\s*\(", title, 1)[0]
        title = re.sub(r"[«»]", " ", title)
        title = re.sub(r"\s{2,}", " ", title).strip()
    # (1) глобально выкинуть токены с жёстким символьным мусором (в настоящем заглавии их не бывает;
    #     заодно так снимается хвостовое альт-название в «…»/(…) — оно есть в alt_titles отдельно)
    HARDJUNK = re.compile(r"""[()\[\]{}/\\®©§*^~<>|"«»]""")
    # (1a) срезать ведущий мусор буквицы, ПРИКЛЕЕННЫЙ к первому CAPS-слову токена
    #      («~@ТЯЖЕЛАЯ»→«ТЯЖЕЛАЯ», «®1)'\УЗНАЙ»→«УЗНАЙ», «@СТРЕЛЬБА»→«СТРЕЛЬБА»):
    #      префикс из структурного мусора/латиницы/цифр перед прогоном 3+ кириллических CAPS.
    #      Кавычки «» НЕ трогаем — иначе сломается логика «Ы»/«ТРЕСТ» (там сабтайтл в кавычках).
    _STRUCT_JUNK = re.compile(r"[~@\\/®©§*^<>|(){}\[\]]")
    def _strip_lead_junk_tok(t):
        m = re.search(r"[А-ЯЁ]{3,}", t)
        if m and m.start() > 0:
            pre = t[:m.start()]
            if _STRUCT_JUNK.search(pre) and not re.search(r"[А-ЯЁа-яё«»]", pre):
                cand = t[m.start():]
                if re.match(r"ИТИЛ|ФИТИЛ", cand):       # Фитиль-фрагмент — отдать логике Фитиля,
                    return t                              #   не «оживлять» мусорное «ИТИЛЬ»
                return cand
        return t
    toks = [_strip_lead_junk_tok(t) for t in title.split()]
    toks = [t for t in toks if not HARDJUNK.search(t)]
    # (2) срезать ведущие огрызки буквицы: латиница/строчные, «цифра+буква» (6Э),
    #     одиночная заглавная буква, не являющаяся предлогом/союзом (Л, М, Ш — мусор; А, В, О — оставить)
    def _lead_junk(t, has_next):
        if re.search(r"[a-z]", t):                    return True   # латиница строчная — мусор
        if not re.search(r"[А-ЯЁ]", t):               return True   # нет заглавной кириллической
        if sum(c.islower() for c in t) > sum(c.isupper() for c in t): return True  # преобладают строчные
        if re.fullmatch(r"\d+[А-ЯЁ]|[А-ЯЁ]\d+", t):   return True   # «6Э» — огрызок буквицы
        if len(t) <= 2 and re.search(r"[а-яё]", t) and has_next: return True  # «лЛ» — огрызок буквицы
        if len(t) == 1 and t not in "АИВКОСУЯ" and has_next: return True  # одиночная буква-непредлог
        return False
    if toks:
        toks[0] = re.sub(r"^[а-яё](?=[А-ЯЁ]{4,})", "", toks[0])   # «йАБЕСАЛОМ» → «АБЕСАЛОМ»
    while toks and _lead_junk(toks[0], len(toks) > 1):
        toks.pop(0)
    title = " ".join(toks)
    title = re.sub(r"[\s.,;:»\-]+$", "", title).strip()                # хвостовая пунктуация
    title = re.sub(r"\s+сер(?:ия|\.)?$", "", title, flags=re.I).strip()# хвостовой огрызок «… сер»
    if re.search(r"\bсер\.|\d+\s*ч\b", title) or len(title) < 2:
        title = ""                                                     # обрывок метастроки, не название
    title = _repair_title(title, raw_full)                             # № глиф + восстановление «Фитиль»
    if not title:                                                      # запасной проход для кавычечных
        title = _recover_guillemet_title(_title_seg)                   # названий с битой буквицей

    # жанр: между заглавием и метражом; берём слово(а) до первой запятой, без форматных пометок
    _after = rawhead[bm.start():] if bm else rawhead
    _after = re.sub(r"^[\s‚.,*\-]+", "", _after)        # снять ведущую пунктуацию (граница «,жанр»)
    _mr = re.search(r"\d+\s*ч[ .,]", _after)
    genre_seg = _after[:_mr.start()] if _mr else _after[:50]
    _g = FORMAT_QUAL.sub(" ", genre_seg).split(",")[0]
    _g = re.sub(r"\s+", " ", _g).strip(" ;,.-‚·*")
    if _g and re.search(r"""[0-9A-Za-z£®±§\\/"«»~|<>^]""", _g):     # остаточный OCR-мусор в жанре
        _g = None
    genre_disp = (_g[0].lower() + _g[1:]) if _g else None
    tech_anim = bool(ANIM_TECH.search(genre_seg))

    def _real_alt(a):
        a = a.strip()
        return (len(a) >= 3 and not re.fullmatch(r"[А-ЯЁ]\.?", a)
                and not re.fullmatch(r"(?:М|Л|К|Од|Тб|Ер|Свердл|Минск|Киев|Рига|Баку|Алма-Ата)\.?", a)
                and not re.search(r"фильм|студи|кинохроник", a, re.I)   # это студия, не альт-название
                and bool(re.search(r"[А-Яа-яёA-Za-z]{3,}", a)))
    alts = [squeeze(a) for a in ALT_TITLE_RE.findall(head) if _real_alt(a)]

    ym = YEAR_RE.search(head)
    year = ym.group(1) if ym else None
    reels = (REELS_RE.search(head) or [None, None])[1] if REELS_RE.search(head) else None
    metres = (METRES_RE.search(head) or [None, None])[1] if METRES_RE.search(head) else None
    ve = VE_RE.search(head)
    ve_date = squeeze(ve.group(1)) if ve else None
    sm = STUDIO_RE.search(head)
    studio = squeeze(sm.group(1)) if sm else None

    # правило анимации: техника графич/кукольн/… ИЛИ мультстудия -> жанр "мультфильм"
    if tech_anim or (studio and ANIM_STUDIO.search(studio)):
        genre = "мультфильм"
    else:
        genre = genre_disp

    credits = CREDITS_RE.search(block)
    credits_txt = squeeze(credits.group(1)) if credits else None
    director = None
    if credits_txt:
        dm = DIRECTOR_RE.search(credits_txt)
        if dm:
            director = squeeze(dm.group(1))

    biblio_m = BIBLIO_RE.search(raw_full)
    biblio = squeeze(biblio_m.group(1)) if biblio_m else None

    preserv_m = PRESERV_RE.search(block)
    preserv = squeeze(preserv_m.group(1)) if preserv_m else None

    # граница "актёры | сюжет". Сюжет начинается либо с типового зачина (О.../Экраниз...),
    # либо с первого прозаического предложения (Заглавное_слово + строчное) после списка актёров —
    # это ловит сюжеты, начинающиеся с персонажа («Скромный страховой агент Юрий Деточкин…»).
    vr = re.search(r"В\s*ролях[:.\- ]+", block)
    search_from = vr.end() if vr else 0
    aw = _award_start(block, search_from)        # начало наградной секции — за ней сюжета нет
    region = block[search_from:aw]
    opener = SYNOPSIS_RE.search(region)
    if opener:                                   # надёжный зачин сюжета — приоритет
        cut = search_from + opener.start()
    else:
        ell = re.match(r"\s*(?:\.\.\.|…)\s*[А-ЯЁ]", region)   # сюжет, ОТКРЫВАЮЩИЙСЯ с многоточия («…Спустя год…»)
        if ell:
            cut = search_from + ell.start()
        else:
            prose = re.search(
                r"[.;]\s+(?!(?:Реж|Опер|Худ|Композ|Звукоопер|Звукооформ|Авт|Ассист|Дириж|"
                r"Балетм|Постан|Монтаж|Консульт|Хормейст|Декор|Пом|Грим)\.?(?:\s|\.))"
                r"([А-ЯЁ][а-яё]{2,}\s+[а-яё])", region)        # первое прозаическое предложение (мимо терсовых титров)
            cut = search_from + prose.start(1) if prose else None
    if cut is not None:
        cast = tidy(block[search_from:cut]) if vr else None
        annotation = tidy(block[cut:])
    else:
        cast_m = CAST_RE.search(block)
        cast = squeeze(cast_m.group(1)) if cast_m else None
        annotation = clean_annotation(block, [credits_txt, cast, biblio, preserv])

    # отрезаем хвостовую БИБЛИОГРАФИЮ (если просочилась), наградную секцию и заднюю часть книги
    # (алфавитный указатель + выходные данные типографии у последней карточки тома) — для поиска бесполезны
    if annotation:
        annotation = re.split(r"БИБЛИО\w*|Библиограф", annotation, maxsplit=1)[0]
        annotation = _strip_awards(annotation)
        annotation = _strip_backmatter(annotation)
        annotation = re.sub(r"[\s.,;:—–·*-]+$", "", annotation).strip()

    return {
        "volume": volume,
        "catalog_number": num,
        "scan_page": page_idx + 1,
        "printed_page": printed_page_number(pages[page_idx]) if page_idx < len(pages) else None,
        "title": title,
        "alt_titles": alts,
        "year": year,
        "studio": studio,
        "genre": genre,
        "reels": reels,
        "metres": metres,
        "release_date": ve_date,
        "director": director,
        "cast": cast,
        "annotation": annotation,
        "credits": credits_txt,
        "bibliography": biblio,
        "preservation": preserv,
        "raw": squeeze(raw_full.replace("\n", " ")),
    }


# ----------------------------------------------------------------------------
# 6. Запись результатов
# ----------------------------------------------------------------------------

def slugify(s, maxlen=60):
    """Имя файла на кириллице (как в ранее обработанных томах). Корректная распаковка
    обеспечивается UTF-8-флагом (EFS, бит 0x800) при упаковке через Python zipfile —
    утилита zip(1) этот флаг НЕ ставит, из-за чего Windows ломает кириллицу."""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r'[\\/:*?"<>|]+', "", s)        # символы, запрещённые в именах Windows
    s = re.sub(r"\s+", "_", s).strip("_.")
    s = re.sub(r"_{2,}", "_", s)
    return s[:maxlen].strip("_.") or "untitled"


def record_to_txt(r):
    """Только заголовок, год, студия и сюжет (+ ссылка на том/страницу для поиска в каталоге)."""
    lines = []
    head = r["title"] or "Без названия"
    tail = [x for x in (r.get("genre"), r["year"], r["studio"]) if x]
    lines.append(f"{head} ({', '.join(tail)})" if tail else head)
    if r["alt_titles"]:
        lines.append("Другие названия: " + "; ".join(r["alt_titles"]))
    src = f"Источник: {r['volume']}, скан-стр. {r['scan_page']}"
    if r["printed_page"]:
        src += f" (печатная стр. {r['printed_page']})"
    if r["catalog_number"] is not None:
        src += f", № {r['catalog_number']}"
    lines.append(src)
    lines.append("")
    lines.append(r["annotation"] or "(сюжет не распознан)")
    return "\n".join(lines).strip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="Парсер каталогов Госфильмофонда (DjVu/PDF) -> карточки фильмов.")
    ap.add_argument("inputs", nargs="+", help="файлы .djvu / .pdf")
    ap.add_argument("-o", "--out", default="records", help="папка для результатов")
    ap.add_argument("--format", choices=["txt", "jsonl", "both"], default="both")
    ap.add_argument("--djvutxt", default="djvutxt", help="путь к djvutxt, если не в PATH")
    ap.add_argument("--force", choices=["auto", "old", "new"], default="auto", help="принудительный формат макета")
    args = ap.parse_args()

    outdir = Path(args.out)
    (outdir / "txt").mkdir(parents=True, exist_ok=True)
    jsonl_path = outdir / "films.jsonl"
    jsonl_f = open(jsonl_path, "w", encoding="utf-8") if args.format in ("jsonl", "both") else None

    grand_total = 0
    for inp in args.inputs:
        volume = Path(inp).stem
        print(f"\n=== {volume} ===")
        pages = extract_pages(inp, args.djvutxt)
        full = "\n".join(pages)
        if len(full.strip()) < 1000:
            print("  [!] Текстовый слой пуст или почти пуст — нужен OCR. Пропускаю.")
            continue

        auto_fmt, n_orn, n_num, n_meta, backbone = detect_format(full)
        fmt = args.force if args.force != "auto" else auto_fmt
        print(f"  страниц: {len(pages)} | орнаментов ►: {n_orn} | нумер. заголовков: {n_num} | "
              f"метастрок: {n_meta} | хребет: {backbone} | формат: {fmt}"
              + ("" if args.force == "auto" else f" (форс, авто={auto_fmt})"))

        records = segment_new(pages) if fmt == "new" else segment_old(pages)
        records = rejoin_orphan_title_heads(records)  # воссоединить голову названия, перенесённую через разрыв страницы
        records = split_internal(records)           # склейки по второй метастроке
        records = split_by_cast(records)            # добивка по «N ч.» перед лишним «В ролях»
        records = merge_series_continuations(records)  # вернуть отрезанные 2-е/3-и серии к фильму
        records = split_internal(records)           # повторно: merge мог достроить 2-ю метастроку (год был в хвосте)
        records = split_at_ornament(records)            # разрезать слитые в строку фильмы по орнаменту
        parsed = [parse_record(num, pi, blk, fmt, volume, pages) for (num, pi, blk) in records]

        # статистика качества
        with_ann  = sum(1 for r in parsed if r["annotation"] and len(r["annotation"]) > 30)
        with_year = sum(1 for r in parsed if r["year"])
        gaps = ""
        if fmt == "old":
            nums = [r["catalog_number"] for r in parsed if r["catalog_number"] is not None]
            if nums:
                gaps = f" | номера {min(nums)}–{max(nums)}, пропусков в цепочке ~{(max(nums)-min(nums)+1)-len(set(nums))}"
        print(f"  карточек: {len(parsed)} | с аннотацией: {with_ann} | с годом: {with_year}{gaps}")

        for idx, r in enumerate(parsed, 1):
            if jsonl_f:
                slim = {k: r[k] for k in ("volume", "catalog_number", "scan_page", "printed_page",
                                          "title", "alt_titles", "year", "studio", "genre", "annotation")}
                slim["raw"] = r["raw"]      # сырой блок — на случай покалеченной карточки
                jsonl_f.write(json.dumps(slim, ensure_ascii=False) + "\n")
            if args.format in ("txt", "both"):
                key = r["catalog_number"] if r["catalog_number"] is not None else idx
                fname = f"{volume}__{key:>05}__{slugify(r['title'])}.txt" if isinstance(key, int) \
                        else f"{volume}__{idx:05}__{slugify(r['title'])}.txt"
                (outdir / "txt" / fname).write_text(record_to_txt(r), encoding="utf-8")
        grand_total += len(parsed)

    if jsonl_f:
        jsonl_f.close()
    print(f"\nГотово. Всего карточек: {grand_total}. Папка: {outdir.resolve()}")


if __name__ == "__main__":
    main()
