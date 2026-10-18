# -*- coding: utf-8 -*-
"""Ф6-П2: сборка резолюции scripts/f6_p2_resolution.json из авто-черновика (work/f6_p2_ann_draft.json) и ручных
спецификаций (work/f6_p2_manual.py). Печатает обзор ручных правок в work/f6_p2_review.txt."""
import sys, json, re, datetime
sys.path.insert(0, 'work')
import f6_p2_lib as L
import f6_p2_manual as M
cat = json.load(open('state/catalog_f6_p1.json', encoding='utf-8'))
al = json.load(open('state/alignment_f6_p1.json', encoding='utf-8'))
m = json.load(open('state/index_master_f6_p1.json', encoding='utf-8'))
bycat = {r['cat_pos']: r for r in m['rows'] if r['kind'] == 'card'}
scan = {x['cat']: x for x in json.load(open('work/f6_p2_ann_scan.json', encoding='utf-8'))}
draft = {x['cat']: x for x in json.load(open('work/f6_p2_ann_draft.json', encoding='utf-8'))}
MARKERS = re.compile(r'(Авт\. сцен|Авт\.сцен|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиография|БИБЛИОГРАФИЯ|дир\. картины|худ\.-пост)')
rev = []
def vol_of(c): return cat[c]['source'].split('_')[0]
def evid(c, text, lo=None, hi=None):
    """индекс печатной строки статьи cat c, содержащей нормализованное начало text"""
    v = vol_of(c); ls = L.lines(v); x = scan.get(c); n = L.norm_m(text)[:28]
    if not n: return None
    lo = lo if lo is not None else (x['h'] if x else 0); hi = hi if hi is not None else ((x['e'] + 3) if x else len(ls) - 1)
    for j in range(lo, min(hi, len(ls) - 1) + 1):
        if n in L.norm_m(ls[j][1]): return j
    hits = [j for j in range(len(ls)) if n in L.norm_m(ls[j][1])]   # запасной поиск по всему тому (скан мог не найти статью)
    return hits[0] if len(hits) == 1 else None
def entry(c, cls, before, after, lines, note):
    assert after is None or (after == after.strip() and '  ' not in after and '\n' not in after), f'cat{c}: after'
    assert after != before, f'cat{c}: after == before'
    return {'cat': c, 'title': cat[c]['title'], 'source': cat[c]['source'], 'field': 'annotation', 'class': cls,
            'before': before, 'after': after, 'vol': vol_of(c), 'lines': lines, 'note': note}
ann_items = {}
# ── авто-черновик ──
for c, d in draft.items():
    if c in M.DRAFT_OVERRIDE or c in M.DRAFT_DROP: continue
    ann_items[c] = dict(d)
manual = set()
def put(e):
    c = e['cat']
    if c in ann_items and c not in manual: rev.append(f'  (перекрыт авто-черновик {ann_items[c]["class"]})')
    ann_items[c] = e; manual.add(c)
# ── LEAD по маркеру ──
def lead_by_marker(c, mk, tail_mk=None, tail_from_scan=False):
    a = cat[c]['annotation']; assert a is not None, f'cat{c}: None'
    assert a.count(mk) == 1, f'cat{c}: маркер «{mk}» встречается {a.count(mk)} раз'
    p = a.index(mk); after = a[p:]
    lines = []; j = evid(c, a[p:p + 40]); lines += [j] if j is not None else []
    note = f'лид {p} зн. (титры/участники) до печатной прозы' + (f' @{j}' if j is not None else '')
    if tail_mk is not None:
        assert after.count(tail_mk) == 1, f'cat{c}: хвост «{tail_mk}» ×{after.count(tail_mk)}'
        q = after.index(tail_mk); cut = after[q:]; after = after[:q].rstrip()
        k = evid(c, after[-40:]); lines += [k] if k is not None else []
        note += f'; хвост {len(cut)} зн. после последней печатной прозы' + (f' @{k}' if k is not None else '') + f' («{cut[:40].strip()}…»)'
    elif tail_from_scan:
        x = scan[c]; assert 'TAIL' in x['class'], f'cat{c}: скан без TAIL ({x["class"]})'
        tp = x['tail_pos']; cut = a[tp:]; assert after.endswith(cut), f'cat{c}: хвост скана вне after'
        after = after[:len(after) - len(cut)].rstrip()
        note += f'; хвост {len(cut)} зн. после последней печатной прозы @{x["last_prose_line"]} («{cut[:40].strip()}…»)'; lines.append(x['last_prose_line'])
    after = re.sub(r'\s+', ' ', after).strip()
    cls = 'lead' + ('+tail' if (tail_mk is not None or tail_from_scan) else '')
    if not lines and c in M.LEAD_EVID: lines = list(M.LEAD_EVID[c]); note += f' @{lines[0]}'
    put(entry(c, cls, a, after, sorted(set(lines)), note))
for c, mk in M.LEAD.items(): lead_by_marker(c, mk)
for c, (mk, tmk) in M.LEAD_TAIL.items(): lead_by_marker(c, mk, tmk, tail_from_scan=(tmk is None))
# ── LEAD по позиции скана ──
for c in M.LEAD_SCAN:
    x = scan[c]; a = cat[c]['annotation']; lp = x['lead_pos']; assert lp > 0
    after = a[lp:]; note = f'лид {lp} зн. до печатной прозы @{x["first_prose_line"]}' + ('; концертная группа: срезаны только жёсткие титры' if x['concert'] else '')
    lines = [x['first_prose_line']]; cls = 'lead'
    if c in M.LEAD_SCAN_TAIL:
        tp = x['tail_pos']; cut = a[tp:]; after = after[:len(after) - len(cut)]; cls = 'lead+tail'
        note += f'; хвост {len(cut)} зн. после последней печатной прозы @{x["last_prose_line"]} («{cut[:40].strip()}…»)'; lines.append(x['last_prose_line'])
    after = re.sub(r'\s+', ' ', after).strip()
    if x['class'].startswith('LEAD-X'): note += ' [скан LEAD-X: фрагменты лида совпадают с печатными титрами/участниками — проверено вручную]'
    if x['class'].startswith('LEAD?'): note += ' [скан LEAD?: часть лида не найдена в печати (OCR) — проверено вручную]'
    put(entry(c, cls, a, after, sorted(set(lines)), note))
# ── TAIL по маркеру ──
for c, mk in M.TAIL.items():
    a = cat[c]['annotation']; assert a.count(mk) == 1, f'cat{c}: tail-маркер ×{a.count(mk)}'
    q = a.index(mk); after = a[:q].rstrip(); k = evid(c, after[-40:])
    put(entry(c, 'tail', a, re.sub(r'\s+', ' ', after), [k] if k is not None else [], f'хвост {len(a) - q} зн. после последней печатной прозы' + (f' @{k}' if k is not None else '') + f' («{a[q:q + 50].strip()}…»)'))
# ── PREFIX ──
for c, (pre, v, n) in M.PREFIX.items():
    a = cat[c]['annotation']; assert v == vol_of(c)
    t = L.lines(v)[n][1]; assert L.norm_m(pre) in L.norm_m(t), f'cat{c}: префикс не найден @{n}'
    assert L.norm_m(a[:30]) in L.norm_m(t), f'cat{c}: продолжение не найдено @{n}'
    put(entry(c, 'prefix', a, (pre + a).strip(), [n], f'утраченное начало абзаца по печати @{n}'))
# ── MID ──
for c, subs in M.MID.items():
    a = cat[c]['annotation']; after = a
    for s in subs:
        if isinstance(s, tuple):
            _, s = s; assert after.count(s) >= 2, f'cat{c}: mid-all «{s[:30]}» ×{after.count(s)}'
        else:
            assert after.count(s) == 1, f'cat{c}: mid «{s[:30]}» ×{after.count(s)}'
        after = after.replace(s, '')
    after = re.sub(r'\s+', ' ', after).strip(); x = scan.get(c) or json.load(open('work/f6_p2_articles.json', encoding='utf-8')).get(str(c))
    put(entry(c, 'mid', a, after, [x['h'], x['e']], f'удалены титры/дубляж/хвост внутри аннотации — печатно строки статьи v{vol_of(c)[1:]} @{x["h"]}–{x["e"]}: ' + ' | '.join(f'«{(s[1] if isinstance(s, tuple) else s).strip()[:60]}»' for s in subs)))
# ── NONE ──
for c, why in M.NONE.items():
    a = cat[c]['annotation']; put(entry(c, 'none', a, None, [2176, 2181], why))
# ── RESTORE ──
def compose(v, items):
    ls = L.lines(v); out = ''; used = []
    for it in items:
        if isinstance(it, tuple):
            _, n, pre = it; t = ls[n][1].strip(); assert t.startswith(pre), f'{v}@{n}: нет префикса «{pre}»'; t = t[len(pre):].strip(); used.append(n)
        elif isinstance(it, int):
            t = ls[it][1].strip(); used.append(it)
        else:
            t = it
        t = re.sub(r'\s+', ' ', t)
        if not out: out = t
        elif out.endswith('-') and re.match(r'[а-яё]', t): out = out[:-1] + t
        else: out = out + ' ' + t
    out = re.sub(r'[\s*]+$', '', out)   # печатная звёздочка-маркер/таб в конце абзаца (в каталоге не хранится)
    return out, used
for c, items in M.RESTORE.items():
    v = vol_of(c); after, used = compose(v, items)
    lits = [it for it in items if isinstance(it, str)]
    for s in lits:  # титул новеллы должен быть в печати блока
        j = evid(c, s, min(used) - 14, max(used) + 3); assert j is not None, f'cat{c}: титул «{s}» не найден в печати'
    assert not MARKERS.search(after), f'cat{c}: маркер в restore: {MARKERS.search(after).group()}'
    a = cat[c]['annotation']
    note = f'RESTORE по печати @{used[0]}–@{used[-1]}' + (f' (k4: титулы новелл {", ".join("«"+s+"»" for s in lits)})' if lits else '')
    if c == 2243: note = 'П2-а: тело статьи «ПЕС И КОТ» 1955 (v2 @7559) — проза @7563–@7564 verbatim («О Туманяна» — как в печати); прежняя аннотация = дубль статьи 1938 г. (cat1514)'
    put(entry(c, 'restore', a, after, sorted(set(used)), note))
# ── END_FIX (дефис-обрывы) ──
for c, (old, new, v, lines) in M.END_FIX.items():
    a = cat[c]['annotation']; assert a.endswith(old), f'cat{c}: не оканчивается на «{old}»'
    after = a[:len(a) - len(old)] + new
    put(entry(c, 'restore', a, after, lines, f'дефис-обрыв конца аннотации: «…{old}» → «…{new}» по печати {v} @{"–@".join(map(str, lines))}'))
# ── CONT: продолжение прозы после обрыва на границе страницы ──
for c, ns in M.CONT.items():
    base = ann_items[c]['after'] if c in ann_items else cat[c]['annotation']
    x = scan[c]; ls = L.lines(vol_of(c)); lp = x['last_prose_line']
    assert L.norm_m(base[-30:]) in L.norm_m(ls[lp][1]) or L.norm_m(ls[lp][1][-25:]) in L.norm_m(base[-60:]), f'cat{c}: конец after не совпадает с печатной строкой @{lp}'
    out = base.rstrip('- ')
    prev_hyph = ls[lp][1].rstrip().endswith('-')
    for i, n in enumerate(ns):
        t = re.sub(r'\s+', ' ', ls[n][1].strip())
        if i == 0 and prev_hyph and re.match(r'[а-яё]', t): out = out + t
        elif out.endswith('-') and re.match(r'[а-яё]', t): out = out[:-1] + t
        else: out = out + ' ' + t
    out = re.sub(r'[\s*,\t]+$', '', out)
    note = f'обрыв на границе страницы (колонтитул после @{lp}): продолжение прозы по печати @{ns[0]}–@{ns[-1]}' + (' (перенос «-» склеен)' if prev_hyph else '')
    if c in ann_items:
        e = ann_items[c]; e['after'] = out; e['class'] = e['class'] + '+restore'; e['note'] += '; ' + note; e['lines'] = sorted(set(e['lines'] + ns)); manual.add(c)
    else:
        put(entry(c, 'restore', cat[c]['annotation'], out, ns, note))
# ── pass B (остаточные титры-продолжения / soft-лиды / титры сюжетов внутри) ──
passb = json.load(open('work/f6_p2_passb.json', encoding='utf-8'))
nb = 0
for pb in passb:
    c = pb['cat']
    if c in M.PASSB_EXCLUDE or c in manual: continue
    kinds = sorted({o[0] for o in pb['ops']}, key=lambda k: ('lead', 'mid').index(k))
    note = 'pass B: ' + '; '.join(('лид (титры-продолжение/музыкально-исполнительские примечания) до первой печатной прозы' if k == 'lead' else 'титры сюжета/оркестра внутри — удалены по печати') for k in kinds) + f' @{pb["lines"]}'
    orig = cat[c]['annotation']
    if c in ann_items:  # поверх авто-черновика: before — исходная аннотация
        e = ann_items[c]; assert e['before'] == orig and e['after'] == pb['before'], f'cat{c}: pass B поверх черновика'
        e['after'] = pb['after']; e['class'] = e['class'] + '+' + '+'.join(kinds); e['note'] = e['note'] + '; ' + note; e['lines'] = sorted(set(e['lines'] + pb['lines']))
    else:
        assert pb['before'] == orig, f'cat{c}: pass B before'
        ann_items[c] = entry(c, '+'.join(kinds), orig, pb['after'], pb['lines'], note)
    nb += 1
print('pass B integrated:', nb)
# ── обзор ──
for c in sorted(manual):
    e = ann_items[c]; x = scan.get(c); v = e['vol']; ls = L.lines(v)
    rev.append(f'\n=== cat{c} «{e["title"]}» {cat[c]["year"]} {e["source"]} [{e["class"]}] {e["note"]}')
    rev.append(f'BEFORE ({len(e["before"] or "")}): {(e["before"] or "")[:160]!r}{" …" if e["before"] and len(e["before"])>160 else ""}')
    if e['after'] is None: rev.append('AFTER: None')
    elif e['class'] in ('restore', 'prefix', 'mid') or len(e['after']) <= 240: rev.append(f'AFTER ({len(e["after"])}): {e["after"]!r}')
    else: rev.append(f'AFTER ({len(e["after"])}): {e["after"][:160]!r} … {e["after"][-100:]!r}')
    for n in e['lines']:
        if isinstance(n, int) and n < len(ls): rev.append(f'   @{n} [{L.kind(ls[n][1], bool(x and x["concert"]))}] {ls[n][1][:140]}')
open('work/f6_p2_review.txt', 'w', encoding='utf-8').write('\n'.join(rev))
# ── титулы ──
title_items = []
for c, (after, src) in M.TITLES.items():
    b = cat[c]['title']; assert after != b and after == after.strip() and '  ' not in after, f'cat{c}: титул'
    title_items.append({'cat': c, 'title': b, 'source': cat[c]['source'], 'field': 'title', 'class': 'title', 'before': b, 'after': after,
                        'vol': vol_of(c), 'lines': [int(n) for n in re.findall(r'@(\d+)', src)], 'note': src,
                        'master': {'xlsx_row': bycat[c]['xlsx_row'], 'title_canon_before': bycat[c]['title_canon'], 'title_canon_after': after,
                                   'master_title_before': al[c]['master_title'], 'master_title_after': after}})
# ── мастер-only ──
master_only = []
bad = []
for c in M.MASTER_ONLY:
    r = bycat[c]; t = cat[c]['title']; assert r['title_canon'] != t, f'cat{c}: canon уже = титул'
    v = vol_of(c); fa = L.find_article(v, t, cat[c]['year'], fuzzy=False); h, e, cands = fa if fa else (None, None, [])
    ok = h is not None and L.norm_m(re.sub(r'\s*\(«.*$', '', t)) in L.norm_m(L.lines(v)[h][1][:120])
    IDX = {3541: 'указатель v4 @7093/@7327 «Герой на час — 3547»', 4574: 'указатель v7 @2585 «Ход белой королевы — 830»', 5897: 'указатель v12 @3319 «Киноальманах «Молодость» (выпуск второй) — 2153»; голова v12 @676'}
    if not ok and c in IDX: ok = True; h = None
    if not ok: bad.append((c, t, r['title_canon']))
    master_only.append({'cat': c, 'xlsx_row': r['xlsx_row'], 'num': r['num'], 'title_canon_before': r['title_canon'], 'title_canon_after': t,
                        'master_title_before': al[c]['master_title'], 'master_title_after': t, 'xlsx_title': r['xlsx_title'],
                        'evidence': (f'печатная голова {v} @{h}' if h is not None else IDX.get(c, 'голова не найдена')), 'note': M.MASTER_NOTE.get(c, 'xlsx_title — OCR-дефект указателя; титул каталога = печатная голова')})
print('master-only без подтверждения головой:', bad)
res = {'_meta': {'package': 'Ф6-П2 точечные дефекты', 'generated': datetime.date.today().isoformat(),
                 'input_catalog': 'state/catalog_f6_p1.json (7173)', 'expected_after': {'catalog': 7173, 'master_rows': 7203, 'master_card': 7173, 'strays': 0},
                 'classes': {'lead': 'срез титров/участников до первой печатной прозы', 'tail': 'срез хвоста после последней печатной прозы (библиография/призы/мусор/следующая статья/сноска)',
                             'prefix': 'восстановление утраченного начала абзаца по печати', 'restore': 'аннотация по печати verbatim (RESTORE/k4-слияние новелл/дефис-обрыв)',
                             'mid': 'удаление титров внутри аннотации', 'none': 'аннотация → None (печать нечитаема) + запись реестра',
                             'year': 'год производства по печатной голове', 'studio': 'студия по печатной голове', 'title': 'титул по печатной голове/указателю (+ синхронно master_title/title_canon)'},
                 'sources': {'auto': 'work/f6_p2_ann_draft.json (скан work/f6_p2_ann_scan.json)', 'manual': 'work/f6_p2_manual.py'}},
       'set': sorted(ann_items.values(), key=lambda e: e['cat']) + title_items +
              [{'cat': c, 'title': cat[c]['title'], 'source': cat[c]['source'], 'field': f, 'class': f, 'before': b, 'after': a, 'vol': v, 'lines': ln,
                'note': 'П2-а: печатная голова v2 @7559 «ПЕС И КОТ Графич., цв., ч б, 2 ч 502,4 м, Союзмультфильм, 1955 г.»'}
               for c, fd in M.FIELDS.items() for f, (b, a, v, ln) in fd.items()],
       'master_only': master_only, 'rebind': M.REBIND, 'title_keep': {str(k): v for k, v in M.TITLE_KEEP.items()},
       'register': {'add': [{'cat': 4275, 'field': 'annotation', 'state': 'none', 'reason': M.NONE[4275]}],
                    'close': [{'cat': c, 'field': 'title', 'state': 'defect', 'closed_by': 'П2-б'} for c in (6812, 6813, 3685, 5654)] +
                             [{'cat': 5024, 'field': 'annotation', 'state': 'suspect', 'closed_by': 'П2-д prefix (v9 @1471)'}]}}
for c, fd in M.FIELDS.items():
    for f, (b, a, v, ln) in fd.items(): assert cat[c][f] == b, f'cat{c}/{f}: before {cat[c][f]!r}'
from collections import Counter
print('set:', len(res['set']), Counter((e['field'], e['class']) for e in res['set']))
print('manual:', len(manual), 'auto:', len([c for c in ann_items if c not in manual]), 'titles:', len(title_items), 'master_only:', len(master_only))
json.dump(res, open('scripts/f6_p2_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('review →', 'work/f6_p2_review.txt', len(rev), 'строк')
