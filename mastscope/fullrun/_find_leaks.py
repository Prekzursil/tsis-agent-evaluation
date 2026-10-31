import json, random, re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE.parent / "corpus"
FULLRUN = HERE / "fullrun"

targets = {}
with (FULLRUN / "targets.jsonl").open(encoding="utf-8") as fh:
    for line in fh:
        try:
            t = json.loads(line)
            targets[t["target_id"]] = t
        except Exception:
            pass

rng = random.Random(11)
home_name = Path.home().name
parseable = [t for t in targets.values()
             if t.get("storage_type") in ("jsonl", "json", "zst", "gz", "directory")]
probes = []
tries = 0
while len(probes) < 60 and tries < 400:
    tries += 1
    t = rng.choice(parseable)
    try:
        p = Path(t["path"].replace("<USER>", home_name))
        if t["storage_type"] == "directory":
            cands = list(p.glob("*.jsonl"))
            if not cands:
                continue
            p = cands[0]
        if t["storage_type"] == "zst" or p.suffix == ".zst":
            import zstandard
            with open(p, "rb") as raw:
                with zstandard.ZstdDecompressor(max_window_size=1 << 31).stream_reader(raw) as rdr:
                    text = rdr.read(3_000_000).decode("utf-8", errors="replace")
        elif t["storage_type"] == "gz" or p.suffix == ".gz":
            import gzip
            with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
                text = fh.read(3_000_000)
        else:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read(3_000_000)
    except Exception:
        continue
    mm = re.findall(r'"text"\s*:\s*"([^"\\]{80,240})"', text)
    if not mm:
        mm = re.findall(r"([A-Za-z,;: ]{100,240})", text)
    if not mm:
        continue
    s = rng.choice(mm).strip()
    if len(s) < 60 or p.name in s or p.stem in s:
        continue
    probes.append(s)

lane_files = [q for q in HERE.rglob("*") if q.is_file() and CORPUS not in q.parents
              and q.suffix in {".jsonl", ".json", ".md", ".html", ".py", ".log", ".txt", ".js", ".sh"}]
found = 0
for q in lane_files:
    try:
        blob = q.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for s in probes:
        if s in blob:
            found += 1
            print(f"LEAK: {q.relative_to(HERE)}  probe[:70]={s[:70]!r}")
print(f"probes={len(probes)} lane_files={len(lane_files)} leaks={found}")
