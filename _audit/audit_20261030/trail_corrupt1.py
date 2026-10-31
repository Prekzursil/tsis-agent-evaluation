import json, re, os
p = "tsis/deepdive/trail/work/fullrun/gold_outputs/nvidia-nemotron-3-ultra/GAIA/41bbc898aa7de0f31d2382ff57700a76.json"
raw = open(p, "rb").read().decode("utf-8")
print("bytes:", len(raw), "crlf:", raw.count("\r\n"), "lf:", raw.count("\n"))
# strict parse to capture error
try:
    json.loads(raw)
except json.JSONDecodeError as e:
    print("strict parse:", e.msg, "at line", e.lineno, "col", e.colno, "pos", e.pos)
    print("context:", repr(raw[e.pos-40:e.pos+60]))
# how many lines look like KEY: unquoted-value
badl = []
for i, line in enumerate(raw.splitlines(), 1):
    m = re.match(r'^\s*"[A-Za-z_]+"\s*:\s*[^"\s{\[\d]', line)
    if m:
        badl.append((i, line[:90]))
print("lines with unquoted scalar values:", len(badl))
for b in badl:
    print("  ", b)
# attempt: add a quote where the error is -> does the rest parse?
if badl:
    i = badl[0][0]
    lines = raw.splitlines()
    fixed = lines[:]
    # insert a quote right after the colon
    fixed[i-1] = re.sub(r'^(\s*"[A-Za-z_]+"\s*:\s*)', r'\1"', fixed[i-1], count=1)
    try:
        json.loads("\n".join(fixed))
        print("HYPOTHETICAL: quoting line", i, "makes the file parse (repair candidate; NOT applied)")
    except json.JSONDecodeError as e:
        print("HYPOTHETICAL repair still fails:", e.msg, "line", e.lineno)
