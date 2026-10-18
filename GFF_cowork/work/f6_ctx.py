# Поиск печатного контекста в извлечениях томов: python3 work/f6_ctx.py vN "игла" [before] [after]
import json, re, sys
def norm(s):
    s = (s or '').lower().replace('ё','е')
    tr = str.maketrans({'0':'о','4':'ч','i':'1','l':'1','a':'а','e':'е','o':'о','p':'р','c':'с','x':'х','y':'у','k':'к','h':'н','b':'в','m':'м','t':'т','°':'о','й':'и'})
    s = s.translate(tr)
    return re.sub(r'[^а-я0-9]+',' ', s).strip()
vol = sys.argv[1]; needle = norm(sys.argv[2]); before = int(sys.argv[3]) if len(sys.argv)>3 else 3; after = int(sys.argv[4]) if len(sys.argv)>4 else 12
lines = json.load(open(f'work/{vol}_lines.json', encoding='utf-8'))
hits = [i for i,(n,t,p) in enumerate(lines) if needle in norm(t)]
print(f'{vol}: hits {len(hits)} for {needle!r}')
for h in hits[:6]:
    print('-'*80)
    for j in range(max(0,h-before), min(len(lines), h+after+1)):
        n,t,p = lines[j]
        print(f'@{n}{"*" if j==h else " "} {t}')
