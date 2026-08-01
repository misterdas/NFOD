import re, sys

css = open('styles.css', encoding='utf-8').read()
# strip comments
s = re.sub(r'/\*.*?\*/', ' ', css, flags=re.S)
# strip strings (state walk, respects backslash escapes)
out, i, n, quote = [], 0, len(s), None
while i < n:
    ch = s[i]
    if quote is not None:
        if ch == '\\':
            out.append(ch); i += 1
            if i < n:
                out.append(s[i])
        elif ch == quote:
            quote = None
        i += 1
        continue
    if ch in '"\'':
        quote = ch; i += 1; continue
    out.append(ch); i += 1
s = ''.join(out)
ok = True
for a, b in [('(', ')'), ('[', ']'), ('{', '}')]:
    ca, cb = s.count(a), s.count(b)
    flag = 'OK' if ca == cb else 'UNBALANCED'
    if ca != cb:
        ok = False
    print(f"{a}{b}: {ca}/{cb} {flag}")
print('ALL BALANCED' if ok else 'FAIL')
sys.exit(0 if ok else 1)
