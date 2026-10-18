# -*- coding: utf-8 -*-
"""Ф6-П3: сборка резолюции правок аннотаций → scripts/f6_p3_resolution.json.
Классы: restore (продолжение/новеллы по печати, work/f6_p3_manual.RESTORE), tail (срез призового блока/мусора: автоматически по
work/f6_p3_prize_cut.json [status OK] + вручную TAIL), punct (конечная пунктуация по печати: work/f6_p3_tail_scan.json END-PUNCT + PUNCT).
Каждая позиция: cat, field, class, before, after, vol, lines, note, ops."""
import json, re, sys
sys.path.insert(0, 'work')
import f6_p2_lib as L
from f6_p3_clean import clean, join_lines
from f6_p3_manual import RESTORE, TAIL, PUNCT, REPL_AFTER, PUNCT_LINE
src = open('work/f6_p3_tail_scan.py', encoding='utf-8').read()
ns = {'re': re, 'L': L}; exec(src[src.index('JUNKLINE ='):src.index('res = []')], ns)
nmap = ns['nmap']
cat = json.load(open('state/catalog_f6_p2e.json', encoding='utf-8'))
scan = {x['cat']: x for x in json.load(open('work/f6_p3_tail_scan.json', encoding='utf-8'))}
pcut = {x['cat']: x for x in json.load(open('work/f6_p3_prize_cut.json', encoding='utf-8'))}
MARK = re.compile(r'(Авт\. сцен|Авт\.сцен|Авт\. текста|реж\.-пост|звукоопер|опер\.-пост|В ролях|Библиограф|дир\. картины|худ\.-пост|Роли дублир|Роли озвучив|Фильм дублирован|Реж\. дубл|худ\.-костюм|худ\.-грим|ассист\. реж|Гл\. опер|Реж\.-пост|Опер\.-пост|[;,] реж\. |[;,] опер\. |[;,] худ\. |[;,] композ\. )')
PUNCT_END = re.compile(r'[.!?…]$')
def line(v, j): return L.lines(v)[j][1]
def rest_of_line(v, j, base):
    """остаток печатной строки j после конца base (последние 30 норм. знаков base)"""
    A_n, _ = nmap(base); ln, idx = nmap(line(v, j))
    pr = A_n[-30:]; p = ln.rfind(pr)
    assert p >= 0, f'rest: конец base не найден в {v} @{j}'
    end = idx[p + len(pr) - 1] + 1
    return line(v, j)[end:]
res = []
def add(i, cls, before, after, lines, note, ops, extra=None):
    assert after != before and after == after.strip() and '  ' not in after and '\t' not in after, f'cat{i}: after'
    r = cat[i]
    e = {'cat': i, 'title': r['title'], 'source': r['source'], 'field': 'annotation', 'class': cls, 'before': before, 'after': after,
         'vol': r['source'].split('_')[0], 'lines': lines, 'note': note, 'ops': ops}
    if extra: e.update(extra)
    res.append(e)
done = set()
# ── restore ──
for i, sp in RESTORE.items():
    r = cat[i]; v = r['source'].split('_')[0]; a0 = r['annotation']; a = a0; ops = []
    if sp.get('drop_end'):
        assert a.endswith(sp['drop_end']), f'cat{i}: drop_end'
        a = a[:-len(sp['drop_end'])].rstrip(); ops.append(('DROP', sp['drop_end'], ''))
    for old, new in sp.get('replace', []):
        assert a.count(old) == 1, f'cat{i}: replace «{old}» ×{a.count(old)}'
        a = a.replace(old, new); ops.append(('REPL', old, new))
    if sp.get('prefix'):
        a = sp['prefix'] + a; ops.append(('PREFIX', '', sp['prefix']))
    pieces = []; lines = []; raw = []
    for kind, val in sp['pieces']:
        if kind == 'line': t = line(v, val); lines.append(val); raw.append(t)
        elif kind == 'rest': t = rest_of_line(v, val, a); lines.append(val); raw.append(t)
        else:
            t = val; raw.append('[заголовок по печати] ' + t)
            # анти-фабрикация: заголовок сюжета должен быть началом печатной строки статьи
            nt = nmap(t)[0]; ctx = [j for j in range(max(0, min(lines or [val] if False else [x for k, x in sp['pieces'] if k != 'text']) - 30), max([x for k, x in sp['pieces'] if k != 'text']) + 1)]
            assert any(nmap(line(v, j))[0].startswith(nt) or nt in nmap(line(v, j))[0] for j in ctx), f'cat{i}: заголовок «{t}» не найден в печати'
        pieces.append(t)
    if pieces:
        # остаток строки: снять начальную пунктуацию, если база уже кончается знаком
        if sp['pieces'][0][0] == 'rest' and PUNCT_END.search(a) or (sp['pieces'][0][0] == 'rest' and re.search(r'[»)]$', a)):
            pieces[0] = re.sub(r'^[\s.!?…»)"\']+', '', pieces[0])
        app = join_lines(pieces)
        app, cops, manual = clean(v, app, i)
        for item in REPL_AFTER.get(i, []):
            old, new, why = item[0], item[1], item[2]; n = item[3] if len(item) > 3 else 1
            assert app.count(old) == n, f'cat{i}: REPL_AFTER «{old}» ×{app.count(old)} (ожидалось {n})'
            app = app.replace(old, new); cops.append(('M', old, new, why) + ((f'×{n}',) if n > 1 else ()))
        assert not MARK.search(app), f'cat{i}: маркер титров в добавляемом тексте: {MARK.search(app).group()}'
        manual = [m for m in manual if m[1] in app]
        assert not manual, f'cat{i}: нерешённые переносы {manual}'
        sep = sp['sep']
        if sp.get('glue'): sep = ''
        elif sp['pieces'][0][0] == 'rest' and sep == '':
            sep = '' if re.match(r'^[,.;:!?…»)]', raw[0].lstrip()) else ' '                                  # остаток строки: пунктуация вплотную, слово — через пробел
        if sep == '' and re.search(r'[А-ЯЁа-яё]$', a) and re.match(r'^[а-яё]', app) and (sp['pieces'][0][0] == 'line' or sp.get('glue')): after = a + app   # склейка переноса
        elif sep == '' : after = a + app                                                                     # остаток строки с пунктуацией
        else: after = a + sep + app
        ops += [('APPEND', app[:60] + ('…' if len(app) > 60 else ''), '')] + cops
    else:
        after = a; raw = []
    after = re.sub(r'\s+', ' ', after).strip()
    add(i, 'restore', a0, after, lines, sp['note'], ops, {'raw': raw})
    done.add(i)
# ── tail: автоматический срез призового блока (проверен по печати) ──
for i, x in sorted(pcut.items()):
    if x.get('status') != 'OK' or i in done or i in TAIL: continue
    r = cat[i]; v = x['vol']; a0 = r['annotation']; rest = a0[:len(a0) - len(x['tail'])].rstrip()
    assert a0.startswith(rest) and a0[len(rest):].strip() == x['tail'].strip(), f'cat{i}: tail'
    after = rest; ops = [('TAIL', x['tail'][:80] + ('…' if len(x['tail']) > 80 else ''), '')]
    lp = x['last_prose_line']
    if not PUNCT_END.search(after) and lp is not None:
        m = re.search(r'([.!?…]+)[»)"\'\s]*$', line(v, lp))
        if m and not re.search(r'[.!?…]', re.search(r'[^А-ЯЁа-яё0-9A-Za-z]*$', after).group(0)):
            after = after + m.group(1); ops.append(('PUNCT', '', m.group(1)))
    add(i, 'tail', a0, after, [k for k, t in x['prize_lines']], f'призовой блок по печати ({v} @{", ".join(str(k) for k, t in x["prize_lines"])}); последняя печатная проза @{lp}', ops, {'raw': [t for k, t in x['prize_lines']]})
    done.add(i)
for i, sp in TAIL.items():
    r = cat[i]; v = r['source'].split('_')[0]; a0 = r['annotation']
    assert a0.count(sp['cut_from']) == 1, f'cat{i}: cut_from ×{a0.count(sp["cut_from"])}'
    after = a0[:a0.index(sp['cut_from'])].rstrip(); ops = [('TAIL', a0[a0.index(sp['cut_from']):][:80] + '…', '')]
    for old, new in sp.get('after_fix', []):
        assert after.endswith(old), f'cat{i}: after_fix'
        after = after[:-len(old)] + new; ops.append(('M', old, new))
    if i in pcut and pcut[i].get('last_prose_line') is not None and not PUNCT_END.search(after):
        m = re.search(r'([.!?…]+)[»)"\'\s]*$', line(v, pcut[i]['last_prose_line']))
        if m and not re.search(r'[.!?…]', re.search(r'[^А-ЯЁа-яё0-9A-Za-z]*$', after).group(0)): after = after + m.group(1); ops.append(('PUNCT', '', m.group(1)))
    add(i, 'tail', a0, after, pcut.get(i, {}).get('lines', []), sp['note'], ops)
    done.add(i)
# ── punct ──
for i, sp in PUNCT.items():
    a0 = cat[i]['annotation']; old, new = sp
    assert a0.endswith(old), f'cat{i}: PUNCT old'
    after = a0[:-len(old)] + new
    ln = scan[i].get('last_line') if scan[i].get('last_line') is not None else PUNCT_LINE[i]
    add(i, 'punct', a0, after, [ln], f'конечная пунктуация/мусор в конце по печати (ручная позиция; {cat[i]["source"].split("_")[0]} @{ln})', [('PUNCT', old, new)])
    done.add(i)
for i, x in sorted(scan.items()):
    if 'END-PUNCT' not in x['class'] or i in done: continue
    if x['class'].startswith('MID-CRED'): continue          # журналы — restore
    a0 = cat[i]['annotation']; add_p = x['add_punct']
    seq = re.match(r'[.!?…»)"\'’\s]*', x['raw_after']).group(0)
    if add_p in ('..', '...') and not re.match(r'^\s*\.\.\.', seq): add_p = '.'      # «.\t.\t.» / «. .» — точечные лидеры/мусор OCR, не многоточие
    assert add_p and re.fullmatch(r'[.!?…»)"\']+', add_p), f'cat{i}: add_punct {add_p!r}'
    after = a0 + add_p
    add(i, 'punct', a0, after, [x['last_line']], f'конечная пунктуация по печати ({x["vol"]} @{x["last_line"]}: «{x["raw_after"][:20]}»)', [('PUNCT', '', add_p)])
    done.add(i)
from collections import Counter
print('позиций:', len(res), dict(Counter(e['class'] for e in res)))
assert len({e['cat'] for e in res}) == len(res)
meta = {'package': 'Ф6-П3 сборка: аннотации (продолжения по печати, призовые хвосты, конечная пунктуация)', 'catalog_in': 'state/catalog_f6_p2e.json',
        'sources': {'restore': 'work/f6_p3_manual.py RESTORE (+REPL_AFTER)', 'tail': 'work/f6_p3_prize_cut.json [OK] + f6_p3_manual.TAIL', 'punct': 'work/f6_p3_tail_scan.json END-PUNCT + f6_p3_manual.PUNCT'},
        'counts': dict(Counter(e['class'] for e in res))}
json.dump({'_meta': meta, 'set': res}, open('scripts/f6_p3_resolution.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
with open('work/f6_p3_review.txt', 'w', encoding='utf-8') as f:
    for e in res:
        if e['class'] == 'punct': continue
        f.write(f"\n### cat{e['cat']} {e['vol']} «{e['title']}» [{e['class']}] lines={e['lines']}\n  NOTE: {e['note']}\n  OPS: {e['ops']}\n  BEFORE-END: {e['before'][-150:]!r}\n  AFTER: {e['after']!r}\n")
