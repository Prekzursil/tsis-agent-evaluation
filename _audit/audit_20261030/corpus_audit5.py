import json, os
C = "tsis/deepdive/corpus"
di = json.load(open(os.path.join(C,"dedup_index.json"), encoding="utf-8"))
groups = di["groups"]
# manifest lookup: path -> (sha256, status)
by_path = {}
with open(os.path.join(C,"manifest.jsonl"), encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        by_path[rec["path"]] = (rec["sha256"], rec["status"])
member_total = 0; foreign = 0; wronghash = 0; not_ok = 0
sample_checked = 0
for h, members in groups.items():
    member_total += len(members)
    for p in members:
        if p not in by_path: foreign += 1
        else:
            sha, st = by_path[p]
            if sha != h: wronghash += 1
            if st != "ok": not_ok += 1
print(f"groups={len(groups)} member_total={member_total}")
print(f"declared duplicate_files={di['duplicate_files']} match={di['duplicate_files']==member_total}")
print(f"declared duplicate_hashes={di['duplicate_hashes']} match={di['duplicate_hashes']==len(groups)}")
print(f"foreign_paths={foreign} wrong_hash={wronghash} non_ok_members={not_ok}")
# every group hash should have >1 member (it's a DUP group)
sing = sum(1 for m in groups.values() if len(m)<2)
print("groups with <2 members:", sing)
