#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ф5: извлечение строк docx-тома сырым XML (python-docx запрещён проектно).
Обход mc:AlternateContent: ветка mc:Choice, при пустой — mc:Fallback (не обе);
вложенные w:p текстбоксов — отдельными строками с типом 'txbx'. Контент таблиц
(w:tbl) извлекается с типом 'tbl' — в v3 основная масса контента лежала там.
Использование: python3 f5_extract_lines.py "3 1958-1963.docx" v3_lines.json"""
import sys, json, zipfile
import xml.etree.ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'

def para_text_own(p):
    out = []
    def walk(el):
        if el.tag == f'{{{MC}}}AlternateContent':
            return
        if el.tag == f'{{{W}}}t':
            out.append(el.text or '')
        elif el.tag == f'{{{W}}}tab':
            out.append('\t')
        elif el.tag in (f'{{{W}}}br', f'{{{W}}}cr'):
            out.append(' ')
        for ch in el:
            walk(ch)
    walk(p)
    return ''.join(out)

def extract_lines(path):
    root = ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    body = root.find(f'{{{W}}}body')
    lines = []
    def emit(text, kind):
        lines.append((len(lines), text.strip(), kind))
    def handle_p(p, kind='main'):
        emit(para_text_own(p), kind)
        for ac in p.iter(f'{{{MC}}}AlternateContent'):
            choice = ac.find(f'{{{MC}}}Choice')
            fb = ac.find(f'{{{MC}}}Fallback')
            branch = None
            if choice is not None and ''.join(t.text or '' for t in choice.iter(f'{{{W}}}t')).strip():
                branch = choice
            elif fb is not None:
                branch = fb
            if branch is None:
                continue
            for tp in branch.iter(f'{{{W}}}p'):
                txt = ''.join(t.text or '' for t in tp.iter(f'{{{W}}}t'))
                if txt.strip():
                    emit(txt, 'txbx')
    for ch in body:
        if ch.tag == f'{{{W}}}p':
            handle_p(ch)
        elif ch.tag == f'{{{W}}}tbl':
            for tp in ch.iter(f'{{{W}}}p'):
                handle_p(tp, 'tbl')
    return lines

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    lines = extract_lines(src)
    json.dump([[i, t, k] for i, t, k in lines], open(dst, 'w', encoding='utf-8'),
              ensure_ascii=False)
    ne = sum(1 for _, t, _ in lines if t)
    print(f"{src} → {dst}: строк {len(lines)}, непустых {ne}")
