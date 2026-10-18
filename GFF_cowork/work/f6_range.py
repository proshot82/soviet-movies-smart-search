# Печать диапазона извлечения с усечением служебных строк: python3 work/f6_range.py vN start end [maxlen]
import json, re, sys
vol, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); maxlen = int(sys.argv[4]) if len(sys.argv)>4 else 110
lines = json.load(open(f'work/{vol}_lines.json', encoding='utf-8'))
cred = re.compile(r'^(Авт\. сцен|Реж\.|В ролях|Роли дублир|Опер\.|Худ\.|Композ|Звукоопер|Монтаж|Ассист|Костюм|Грим|Ред\.|Дир\. картины|Комб|Симфонический|Государственный|Оркестр|Вокал|Песн|Фильм дублирован|Библиография|Текст)', re.I)
for j in range(a, b+1):
    n,t,p = lines[j]
    if cred.search(t) and len(t) > maxlen:
        t = t[:maxlen] + ' …[' + str(len(lines[j][1])) + ']'
    print(f'@{n} {t}')
