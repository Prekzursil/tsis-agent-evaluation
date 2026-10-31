import json, os, collections
TR = "tsis/deepdive/trail/work/fullrun"
GO = os.path.join(TR, "gold_outputs")

# proper walk of gold_outputs
for sub in sorted(os.listdir(GO)):
    p = os.path.join(GO, sub)
    for splitdir in sorted(os.listdir(p)):
        sp = os.path.join(p, splitdir)
        if os.path.isdir(sp):
            files = os.listdir(sp)
            okj, badj, notjson = 0, [], 0
            for f in files:
                fp = os.path.join(sp, f)
                if not f.endswith(".json"):
                    notjson += 1
                    continue
                try:
                    json.load(open(fp, encoding="utf-8"))
                    okj += 1
                except Exception as e:
                    badj.append((f, str(e)[:60]))
            print(f"gold_outputs/{sub}/{splitdir}: files={len(files)} json_ok={okj} json_fail={len(badj)} non-json={notjson}")
            for b in badj[:5]:
                print("   BAD:", b)
        else:
            print(f"gold_outputs/{sub}/{splitdir}: FILE (not dir) size={os.path.getsize(sp)}")

# last-wins coherence: for each gold_meta, files whose LAST attempt is ok must exist on disk
def last_ok_files(meta_path):
    last = {}
    for l in open(meta_path, encoding="utf-8"):
        r = json.loads(l)
        last[r["file"]] = r
    return {f: r for f, r in last.items() if r["status"] == "ok"}, {f: r for f, r in last.items() if r["status"] != "ok"}

def disk_files(sub):
    out = set()
    p = os.path.join(GO, sub)
    for splitdir in os.listdir(p):
        sp = os.path.join(p, splitdir)
        if os.path.isdir(sp):
            for f in os.listdir(sp):
                out.add((splitdir, f))
    return out

for meta, sub in (("gold_meta.jsonl", "glm-5.3"), ("gold_meta_nv.jsonl", "nvidia-nemotron-3-ultra")):
    okmap, errmap = last_ok_files(os.path.join(TR, meta))
    disk = disk_files(sub)
    print(f"\n{meta} -> gold_outputs/{sub}: last-attempt-ok={len(okmap)} last-attempt-err={len(errmap)} on-disk={len(disk)}")
    # match by filename
    disknames = set(f for _, f in disk)
    oknames = set(okmap.keys())
    missing_on_disk = oknames - disknames
    extra_on_disk = disknames - oknames
    print(f"  ok-files missing on disk: {len(missing_on_disk)} {sorted(missing_on_disk)[:4]}")
    print(f"  disk files without last-ok: {len(extra_on_disk)} {sorted(extra_on_disk)[:4]}")

# union-top composition
ut = disk_files("union-top")
print(f"\nunion-top on disk: {len(ut)} entries; splits={collections.Counter(s for s, _ in ut)}")
