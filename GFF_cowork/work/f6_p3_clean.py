# -*- coding: utf-8 -*-
"""Ф6-П3: механическая чистка восстановленного по печати текста теми же правилами, что П2д (work/f6_p2d_rules.py):
A (номер страницы внутри переноса), C (мусорные символы/апострофы), Q (кавычки), dot, D (инициалы), E (латиница в слове),
B (переносы «w1- w2» по словарю pymorphy3), WS. Функции П2д загружаются из исходника без запуска его главного цикла."""
import re, sys, json
sys.path.insert(0, 'work')
_src = open('work/f6_p2d_rules.py', encoding='utf-8').read()
_src = _src[:_src.index('draft = {}; review = []')]
_src = _src.replace("cat = json.load(open('state/catalog_f6_p2.json', encoding='utf-8'))", "cat = []")
_ns = {'__name__': 'f6_p2d_rules_funcs'}
exec(compile(_src, 'f6_p2d_rules(funcs)', 'exec'), _ns)
fix_T, fix_BIB, fix_A, fix_C, fix_Q, fix_dot, fix_D, fix_E, fix_B, norm_ws = (_ns[k] for k in ('fix_T', 'fix_BIB', 'fix_A', 'fix_C', 'fix_Q', 'fix_dot', 'fix_D', 'fix_E', 'fix_B', 'norm_ws'))
known = _ns['known']
def clean(v, text, cat_i=None):
    """→ (after, ops, manual): чистка П2д без T/BIB/P/R (хвосты и номера страниц в П3 снимаются явно по строкам)"""
    ops = []; manual = []
    a = text
    a = fix_A(a, ops); a = fix_C(a, ops); a = fix_Q(a, ops); a = fix_dot(a, ops); a = fix_D(a, ops); a = fix_E(a, ops); a = fix_B(v, a, ops, manual, cat_i)
    a = norm_ws(a)
    a2 = re.sub(r'\s([.,;:])$', r'\1', a)
    a2 = re.sub(r'(?<=[.!?…»)])\s[.,;:](?=\s)', '', a2)
    a2 = re.sub(r'(?<=[А-ЯЁа-яё0-9)»])\s([.,;:])(?=\s)', r'\1', a2)
    a2 = re.sub(r'(?<=\S)\s+([,.;:!?»)])(?=\s|$)', r'\1', a2)
    a2 = re.sub(r'«\s+(?=[А-ЯЁа-яё0-9])', '«', a2)
    a2 = re.sub(r'(?<=[А-ЯЁа-яё0-9.!?…])\s+»', '»', a2)
    a2 = re.sub(r'(\d) -я', r'\1-я', a2)
    a2 = re.sub(r'([?!])\.(?=\s|$)', r'\1', a2)      # «Что важнее?.» → «Что важнее?»
    a2 = norm_ws(a2)
    if a2 != a: ops.append(('WS', 'одиночные знаки препинания/пробелы', '')); a = a2
    return a, ops, manual
def join_lines(pieces):
    """склейка печатных строк: перенос «слово-» + строчная → слитно; иначе через пробел"""
    out = ''
    for p in pieces:
        p = p.strip()
        if not p: continue
        if out and re.search(r'[А-ЯЁа-яё]-$', out) and re.match(r'^[а-яё]', p): out = out[:-1] + p
        elif out: out = out + ' ' + p
        else: out = p
    return out
if __name__ == '__main__':
    for v, t in (('v3', 'но Ки- сельников, которому'), ('v2', 'Михайло д^вно уже любит бедную батрачку Анну. Она\'разжигает в Савве'), ('v1', 'десятки и сотни скоро- печатающих станков'), ('v3', 'к измене Родине бесполезны» Бинкль принял'), ('v9', 'Что важнее?. «Центрнаучфильм». Далее')):
        print(clean(v, t))
    print(repr(join_lines(['смертоносного воспламеняю-', 'щегося газа. Вскоре', 'Продолжение серии.'])))
