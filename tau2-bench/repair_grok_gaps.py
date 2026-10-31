"""Audit + repair driver for the grok-4.7 v2.0.0 batch.

For each expected domain: load results_v2_grok/<dom>/results.json, report
coverage (unique (task,trial) pairs vs tasks x trials), duplicate pairs and
infrastructure_error sims. With --repair, re-run the domain via
probe_grok_xhigh.py (auto_resume: skips good sims, re-runs infra sims and
missing units). mock is special (loader timestamps make resume impossible);
its repair = fresh run after archiving (handled manually 2026-10-28).

Run: python repair_grok_gaps.py [--repair] [--domains a,b] [--concurrency 4]
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

LANE = Path(__file__).resolve().parent
RESULTS = LANE / "results_v2_grok"
REPO_PY = LANE / "repo" / ".venv" / "Scripts" / "python.exe"

EXPECTED = {
    "ecommerce3": (14, 4),
    "mock": (10, 4),
    "airline": (50, 4),
    "retail": (114, 4),
    "telecom": (114, 4),
    "telecom-workflow": (114, 4),
    "banking_knowledge": (97, 4),
    "intake": (200, 4),
}


def audit(domain: str) -> dict:
    p = RESULTS / domain / "results.json"
    if not p.exists():
        return {"domain": domain, "missing_file": True}
    d = json.loads(p.read_text())
    sims = d.get("simulations", [])
    pairs = Counter((s["task_id"], s.get("trial")) for s in sims)
    dups = {f"{k[0]}#t{k[1]}": v for k, v in pairs.items() if v > 1}
    by_task: dict[str, set] = {}
    for s in sims:
        by_task.setdefault(s["task_id"], set()).add(s.get("trial"))
    n_tasks, k = EXPECTED[domain]
    covered = sum(len(v) for v in by_task.values())
    infra = sum(
        1
        for s in sims
        if s.get("termination_reason") == "infrastructure_error"
    )
    return {
        "domain": domain,
        "sims": len(sims),
        "unique_pairs": len(pairs),
        "expected_sims": n_tasks * k,
        "missing_units": n_tasks * k - len(pairs),
        "tasks_seen": len(by_task),
        "duplicates": dups,
        "infra_errors": infra,
        "complete": len(pairs) == n_tasks * k and not dups and infra == 0,
    }


def main() -> int:
    args = sys.argv[1:]
    do_repair = "--repair" in args
    concurrency = "4"
    if "--concurrency" in args:
        concurrency = args[args.index("--concurrency") + 1]
    domains = None
    if "--domains" in args:
        domains = [
            d.strip() for d in args[args.index("--domains") + 1].split(",")
        ]

    need_repair = []
    for dom in sorted(EXPECTED):
        if domains and dom not in domains:
            continue
        a = audit(dom)
        if a.get("missing_file"):
            print(f"{dom:20s} NO CHECKPOINT")
            need_repair.append(dom)
            continue
        status = "OK " if a["complete"] else "GAP"
        print(
            f"{dom:20s} {status} sims={a['sims']:4d}/{a['expected_sims']:4d} "
            f"unique={a['unique_pairs']:4d} infra={a['infra_errors']:3d} "
            f"dups={len(a['duplicates'])}"
        )
        if not a["complete"]:
            need_repair.append(dom)

    if not do_repair:
        print("\n(audit only; rerun with --repair to fill gaps)")
        return 0

    for dom in need_repair:
        print(f"\n=== repairing {dom} (auto-resume re-run, concurrency {concurrency})")
        log = LANE / f"results_v2_grok_{dom}_repair.log"
        with open(log, "w") as fp:
            proc = subprocess.run(
                [
                    str(REPO_PY),
                    str(LANE / "probe_grok_xhigh.py"),
                    "--domains",
                    dom,
                    "--trials",
                    "4",
                    "--max-concurrency",
                    concurrency,
                ],
                stdout=fp,
                stderr=subprocess.STDOUT,
                cwd=str(LANE),
            )
        print(f"exit={proc.returncode}, log={log.name}")
        a = audit(dom)
        print(
            f"after repair: sims={a.get('sims')}/{a.get('expected_sims')} "
            f"unique={a.get('unique_pairs')} infra={a.get('infra_errors')} "
            f"dups={len(a.get('duplicates', {}))}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
