# -*- coding: utf-8 -*-
"""Ф6-П3а: сборка резолюции корректирующего пакета → scripts/f6_p3a_resolution.json.
Вход: state/catalog_final_v1.json, work/vN_lines.json, work/f6_ref_gap_scan.json (области статей h2/E, k1/k2, покрытие),
work/f6_p3a_manual.py (спецификации). Текст восстановлений — verbatim печать + чистка П2д (work/f6_p3_clean.clean) + точечные repl.
Каждая позиция аннотации: cat, title, source, field, class, before, after, vol, lines, raw, note, ops.
Дополнительно: insert (вставка записи «Старый наездник» 1940 перед cat1628) и title (титул cat708)."""
import json, re, sys, hashlib, datetime
sys.path.insert(0, 'work')
import f6_p2_lib as L
from f6_p3_clean import clean, join_lines
from f6_p3a_manual import PRE, HEAD, POST, GAP, TAILREPL, ALMANAC, INSERT, TITLE
src = open('work/f6_p3_tail_scan.py', encoding='utf-8').read()
ns = {'re': re, 'L': L}; exec(src[src.index('JUNKLINE ='):src.index('res = []')], ns)
nmap = ns['nmap']
CAT_PATH = 'state/catalog_final_v1.json'
cat = json.load(open(CAT_PATH, encoding='utf-8'))
sha = hashlib.sha256(open(CAT_PATH, 'rb').read()).hexdigest()
scan = {x['cat']: x for x in json.load(open('work/f6_ref_gap_scan.json', encoding='utf-8'))}
MARK = re.compile(r'(Авт\. сцен|Авт\.сцен|Авт\. текста|авт\. текста|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер|Реж\.-пост|Опер\.-пост|[;,] реж\. |[;,] опер\. |[;,] худ\. |[;,] композ\. |ЦСДФ|Автор С\.|реж\.-опер|Авт\.-опер)')
PUNCT_END = re.compile(r'[.!?…»)]$')
def line(v, j): return L.lines(v)[j][1]
def probes(tn):
    if len(tn) <= 14: return [tn] if len(tn) >= 6 else []
    n = max(3, min(7, len(tn) // 20)); step = (len(tn) - 14) / (n - 1) if n > 1 else 0
    return [tn[int(j * step):int(j * step) + 14] for j in range(n)]
def coverage(a, t):
    A = nmap(a)[0]; pr = probes(nmap(t)[0])
    if not pr: return 'junk'
    h = sum(1 for p in pr if p in A); return 'cov' if h * 2 >= len(pr) else ('part' if h else 'no')
def region(i):
    x = scan[i]; return x['h2'], x['E'], x['k1'], x['k2']
def check_lines(i, v, lines, before):
    h2, E, k1, k2 = region(i)
    for k in lines:
        assert h2 < k < E, f'cat{i}: @{k} вне области статьи [{h2},{E})'
        assert coverage(before, line(v, k)) != 'cov', f'cat{i}: @{k} уже покрыта аннотацией'
        assert L.kind(line(v, k)) == 'prose' or i in (2,), f'cat{i}: @{k} kind={L.kind(line(v, k))}'
def build_text(i, v, lines, repl=(), add_dot=False):
    raw = [line(v, k) for k in lines]
    t = join_lines(raw)
    t, ops, manual = clean(v, t, i)
    for old, new, why in repl:
        assert t.count(old) == 1, f'cat{i}: repl «{old}» ×{t.count(old)}'
        t = t.replace(old, new); ops.append(('M', old, new, why))
    manual = [m for m in manual if m[1] in t]
    assert not manual, f'cat{i}: нерешённые переносы {manual}'
    if add_dot and not PUNCT_END.search(t): t += '.'; ops.append(('DOT', '', '.', 'логлайн без знака в печати'))
    assert not MARK.search(t), f'cat{i}: маркер титров: {MARK.search(t).group()}'
    return t, ops, raw
res = []
def add(i, cls, before, after, lines, raw, note, ops, extra=None):
    assert after != before and after == after.strip() and '  ' not in after and '\t' not in after and '\n' not in after, f'cat{i}: after'
    assert PUNCT_END.search(after) or (cls in ('gap-pre', 'gap-head', 'gap-mid') and not PUNCT_END.search(before)), f'cat{i}: нет конечной пунктуации'
    r = cat[i]
    e = {'cat': i, 'id': r['id'], 'title': r['title'], 'source': r['source'], 'field': 'annotation', 'class': cls, 'before': before, 'after': after,
         'vol': r['source'].split('_')[0], 'lines': lines, 'raw': raw, 'note': note, 'ops': ops}
    if extra: e.update(extra)
    res.append(e)
# ── PRE ──
for i, sp in PRE.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']
    check_lines(i, v, sp['lines'], b)
    h2, E, k1, k2 = region(i)
    assert max(sp['lines']) < k1, f'cat{i}: PRE-строки не перед началом аннотации (k1={k1})'
    t, ops, raw = build_text(i, v, sp['lines'], sp.get('repl', ()), sp.get('add_dot'))
    add(i, 'gap-pre', b, t + ' ' + b, sp['lines'], raw, sp.get('note', 'строка аннотационного блока перед началом аннотации утеряна (логлайн/примечание/формула источника)'), [('PREFIX', t[:70], '')] + ops)
# ── HEAD ──
for i, sp in HEAD.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']
    check_lines(i, v, sp['lines'], b)
    hl = line(v, sp['head_line']); ln, idx = nmap(hl); a0 = nmap(b)[0][:16]
    p = ln.find(a0); assert p > 0, f'cat{i}: начало аннотации не найдено в @{sp["head_line"]}'
    headpart = hl[:idx[p]].rstrip()
    assert L.kind(headpart) == 'prose' and len(headpart) < 60, f'cat{i}: headpart {headpart!r}'
    raw = [line(v, k) for k in sp['lines']] + [headpart]
    t = join_lines(raw); t, ops, manual = clean(v, t, i); assert not manual and not MARK.search(t)
    add(i, 'gap-head', b, t + ' ' + b, sp['lines'] + [sp['head_line']], raw, f'обрыв начала аннотации: печать @{sp["lines"][0]} + начало @{sp["head_line"]} до первого слова аннотации', [('PREFIX', t[:70], '')] + ops)
# ── POST ──
for i, sp in POST.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']
    check_lines(i, v, sp['lines'], b)
    h2, E, k1, k2 = region(i)
    assert min(sp['lines']) > k2, f'cat{i}: POST-строки не после конца аннотации (k2={k2})'
    assert PUNCT_END.search(b), f'cat{i}: before без конечной пунктуации'
    t, ops, raw = build_text(i, v, sp['lines'], sp.get('repl', ()))
    add(i, 'gap-post', b, b + ' ' + t, sp['lines'], raw, 'примечание после прозы утеряно: строка с прописной аббревиатурой/формулой принята за голову статьи (ложная голова)', [('APPEND', t[:70], '')] + ops)
# ── GAP ──
for i, sp in GAP.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']
    check_lines(i, v, sp['lines'], b)
    t, ops, raw = build_text(i, v, sp['lines'], sp.get('repl', ()))
    if 'anchor_text' in sp:
        assert b.count(sp['anchor_text']) == 1, f'cat{i}: anchor «{sp["anchor_text"]}» ×{b.count(sp["anchor_text"])}'
        pos = b.index(sp['anchor_text']); anchor = sp['anchor_text']
    else:
        nx = nmap(line(v, sp['next']))[0][:16]; B, bidx = nmap(b)
        p = B.find(nx); assert p >= 0 and B.count(nx) == 1, f'cat{i}: якорь следующей строки @{sp["next"]} не найден/неоднозначен'
        pos = bidx[p]; anchor = line(v, sp['next'])[:40]
    assert pos > 0 and b[pos - 1] == ' ', f'cat{i}: позиция вставки не на границе слова'
    a = b[:pos] + t + ' ' + b[pos:]
    for old, new, why in sp.get('repl_after', ()):
        assert a.count(old) == 1, f'cat{i}: repl_after «{old}» ×{a.count(old)}'
        a = a.replace(old, new); ops.append(('M', old, new, why))
    add(i, 'gap-mid', b, a, sp['lines'], raw, f'строка между покрытыми строками утеряна; вставлена перед текстом печатной строки «{anchor}…»', [('INSERT', t[:70], f'перед «{anchor[:30]}»')] + ops)
# ── TAILREPL ──
for i, sp in TAILREPL.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']
    assert b.endswith(sp['drop_end']), f'cat{i}: drop_end'
    h2, E, k1, k2 = region(i)
    for k in sp['lines']: assert h2 < k < E
    t, ops, raw = build_text(i, v, sp['lines'])
    assert t.endswith(sp['drop_end'])
    core = b[:-len(sp['drop_end'])].rstrip()
    add(i, 'gap-tailrepl', b, core + ' ' + t, sp['lines'], raw, 'последняя печатная строка была взята частично (только формула «Фильм не сохранился.»); заменена полной строкой', [('DROP', sp['drop_end'], ''), ('APPEND', t[:70], '')] + ops)
# ── ALMANAC ──
for i, sp in ALMANAC.items():
    r = cat[i]; v = r['source'].split('_')[0]; b = r['annotation']
    h2, E, k1, k2 = region(i)
    parts = []; ops = []; raw = []; lines = []; group = []
    def flush():
        global group
        if group:
            t = join_lines([line(v, k) for k in group]); t, cops, manual = clean(v, t, i)
            manual = [m for m in manual if m[1] in t]; assert not manual, f'cat{i}: переносы {manual}'
            parts.append(t); ops.extend(cops); group = []
    for kind, val in sp['pieces']:
        if kind == 'line':
            assert h2 < val < E, f'cat{i}: @{val} вне области'
            assert coverage(b, line(v, val)) != 'cov' or sp.get('rebuild'), f'cat{i}: @{val} уже покрыта'
            group.append(val); lines.append(val); raw.append(line(v, val))
        else:
            flush()
            nt = nmap(val)[0]
            hits = [j for j in range(h2, E) if nmap(line(v, j))[0].startswith(nt)]
            assert hits, f'cat{i}: титул «{val}» не является началом печатной строки статьи'
            parts.append(val); raw.append(f'[титул по печати @{hits[0]}] {val}'); lines.append(hits[0])
    flush()
    t = ' '.join(parts)
    for old, new, why in sp.get('repl', ()):
        assert t.count(old) == 1, f'cat{i}: repl «{old}» ×{t.count(old)}'
        t = t.replace(old, new); ops.append(('M', old, new, why))
    assert not MARK.search(t), f'cat{i}: маркер титров: {MARK.search(t).group()}'
    if sp.get('rebuild'): a = t; ops = [('REBUILD', b[:60] + '…', '')] + ops
    else:
        a = (sp['prefix'] + ' ' if sp.get('prefix') else '') + b + ' ' + t
        ops = ([('PREFIX', sp['prefix'], '')] if sp.get('prefix') else []) + [('APPEND', t[:70], '')] + ops
    add(i, 'gap-almanac', b, re.sub(r'\s+', ' ', a).strip(), sorted(set(lines)), raw, sp['note'], ops)
# ── INSERT ──
v = INSERT['vol']; Ls = L.lines(v)
head = Ls[INSERT['head_line']][1]
assert re.match(r'^1628а\. СТАРЫЙ НАЕЗДНИК', head), head
for k in INSERT['lines']: assert L.kind(Ls[k][1]) == 'prose'
assert L.headset(v) & set(range(INSERT['head_line'] + 1, INSERT['lines'][-1] + 1)) == set(), 'внутри статьи есть голова'
t = join_lines([Ls[k][1] for k in INSERT['lines']]); t, iops, manual = clean(v, t, None)
manual = [m for m in manual if m[1] in t]; assert not manual and not MARK.search(t)
assert not PUNCT_END.search(t)   # печать @3141 без конечного знака (OCR) — как в политике П3 END-NOPUNCT: не добавляем
assert cat[INSERT['before_cat']]['title'] == 'Суворов' and cat[INSERT['before_cat'] - 1]['title'] == 'Случай в вулкане'
assert not any(r['title'] == INSERT['record']['title'] for r in cat)
rec = dict(INSERT['record']); rec['annotation'] = t
insert = {**INSERT, 'record': rec, 'raw_head': head, 'raw_credits': [Ls[INSERT['head_line'] + 1][1], Ls[INSERT['head_line'] + 2][1]], 'raw': [Ls[k][1] for k in INSERT['lines']], 'ops': iops}
# ── TITLE ──
titles = []
for i, sp in TITLE.items():
    r = cat[i]
    assert r['title'] != sp['after'] and 'Что должен знать' in r['title']
    hl = [j for j, (n, tt, p) in enumerate(L.lines('v1')) if tt.startswith('ЧТО ДОЛЖЕН ЗНАТЬ РАБОЧИЙ И КРЕСТЬЯНИН О СССР')]
    assert hl == [4881]
    titles.append({'cat': i, 'id': r['id'], 'field': 'title', 'before': r['title'], 'after': sp['after'], 'xlsx_row': sp['xlsx_row'], 'note': sp['note'], 'print_line': 4881})
from collections import Counter
meta = {'package': 'Ф6-П3а', 'date': datetime.date.today().isoformat(), 'input': CAT_PATH, 'input_sha256': sha, 'input_records': len(cat),
        'counts': dict(Counter(x['class'] for x in res)), 'insert': 1, 'title': len(titles),
        'basis': 'регрессионная сверка со старым каталогом (reference/catalog_old_from_db.json, 6857) + печатный скан пропусков work/f6_ref_gap_scan.py; каждая позиция верифицирована по печати (work/vN_lines.json)'}
out = {'_meta': meta, 'set': sorted(res, key=lambda x: x['cat']), 'insert': insert, 'title': titles}
json.dump(out, open('scripts/f6_p3a_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(meta['counts'], 'set', len(res), '| insert 1 | title', len(titles))
with open('work/f6_p3a_review.txt', 'w', encoding='utf-8') as f:
    for x in out['set']:
        f.write(f"### cat{x['cat']} id{x['id']} {x['vol']} «{x['title']}» [{x['class']}] @{x['lines']}\n   note: {x['note']}\n   ops: {x['ops']}\n   BEFORE: {x['before']}\n   AFTER : {x['after']}\n\n")
    f.write(f"### INSERT before cat{insert['before_cat']}: {insert['record']}\n   head: {insert['raw_head']}\n   ops: {insert['ops']}\n\n")
    for t in titles: f.write(f"### TITLE cat{t['cat']}: {t['before']!r} → {t['after']!r}\n")
