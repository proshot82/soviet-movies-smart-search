# -*- coding: utf-8 -*-
"""Ф6-П4: патч film_search.py — ключ дедупликации импорта (title, year) → (title, year, studio).
Решение владельца 02.09.2026 (handoff Ф6 §6 п.4): 3 законные пары title+year — разные фильмы разных студий.
Запуск (Windows, из папки движка, рядом с film_search.py):  python patch_film_search.py
Делает резервную копию film_search.py.bak, меняет ровно один фрагмент, проверяет результат. Повторный запуск безопасен."""
import io, os, sys
P = 'film_search.py'
if not os.path.exists(P):
    sys.exit('[ОШИБКА] нет film_search.py в текущей папке — запусти скрипт из папки движка')
src = io.open(P, encoding='utf-8').read()
OLD = '''                # Check duplicate by title + year
                year = film.get('year')
                existing = conn.execute(
                    "SELECT film_id FROM films WHERE title = ? AND year IS ?",
                    (title, year)
                ).fetchone()'''
NEW = '''                # Check duplicate by title + year + studio (Ф6-П3: 3 законные пары title+year — разные студии)
                year = film.get('year')
                studio = film.get('studio')
                existing = conn.execute(
                    "SELECT film_id FROM films WHERE title = ? AND year IS ? AND studio IS ?",
                    (title, year, studio)
                ).fetchone()'''
if NEW in src:
    print('OK: film_search.py уже пропатчен (ключ title+year+studio).'); sys.exit(0)
n = src.count(OLD)
if n != 1:
    sys.exit(f'[ОШИБКА] ожидаемый фрагмент найден {n} раз (нужен ровно 1) — film_search.py отличается от версии проекта; правь вручную: '
             'в cmd_import строку SELECT film_id FROM films WHERE title = ? AND year IS ?  →  ... AND year IS ? AND studio IS ?, параметры (title, year, studio)')
io.open(P + '.bak', 'w', encoding='utf-8').write(src)
io.open(P, 'w', encoding='utf-8').write(src.replace(OLD, NEW))
print('OK: film_search.py пропатчен (резервная копия film_search.py.bak). Ключ дедупликации импорта: title + year + studio.')
