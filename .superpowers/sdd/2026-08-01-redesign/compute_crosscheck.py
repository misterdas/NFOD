import csv

rows = list(csv.DictReader(open(r"C:\Users\Surajit Pakira\Documents\NFOD\FDCP_Data.csv", encoding="utf-8")))
def row(d, pt):
    for r in rows:
        if r["Client Type"].strip() == pt and r["Date"].strip() == d:
            return {k.strip(): (int(v) if v.strip().isdigit() else v.strip()) for k, v in r.items()}
    return None
def f(r, k): return r.get(k, 0)

p31, p30 = row("31-07-2026", "Pro"), row("30-07-2026", "Pro")
f31, f30 = row("31-07-2026", "FII"), row("30-07-2026", "FII")
c31, c30 = row("31-07-2026", "Client"), row("30-07-2026", "Client")

def delta(r, p, col):
    return (f(r[1], col) - f(r[0], col))

fii_fut = (f(f31, "Future Index Long") - f(f30, "Future Index Long")) - (f(f31, "Future Index Short") - f(f30, "Future Index Short"))
cl_calls = (f(c31, "Option Index Call Long") - f(c30, "Option Index Call Long")) - (f(c31, "Option Index Call Short") - f(c30, "Option Index Call Short"))
pr_calls = (f(p31, "Option Index Call Long") - f(p30, "Option Index Call Long")) - (f(p31, "Option Index Call Short") - f(p30, "Option Index Call Short"))
pr_puts = (f(p31, "Option Index Put Short") - f(p30, "Option Index Put Short")) - (f(p31, "Option Index Put Long") - f(p30, "Option Index Put Long"))
fii_long = f(f31, "Future Index Long") - f(f30, "Future Index Long")

def line(name, val, a1, b1, a2, b2):
    print("%s = %d = (%d-%d) - (%d-%d)" % (name, val, a1, b1, a2, b2))

line("FII fut net  ", fii_fut, f31["Future Index Long"], f30["Future Index Long"], f31["Future Index Short"], f30["Future Index Short"])
line("Client calls", cl_calls, c31["Option Index Call Long"], c30["Option Index Call Long"], c31["Option Index Call Short"], c30["Option Index Call Short"])
line("Pro calls    ", pr_calls, p31["Option Index Call Long"], p30["Option Index Call Long"], p31["Option Index Call Short"], p30["Option Index Call Short"])
line("Pro puts     ", pr_puts, p31["Option Index Put Short"], p30["Option Index Put Short"], p31["Option Index Put Long"], p30["Option Index Put Long"])
print("FII fut longD = %d" % fii_long)
print("bias = %d + %d + %d = %d" % (fii_fut, pr_calls, pr_puts, fii_fut + pr_calls + pr_puts))
