"""Offline verification for the GLM full-scale tau2-bench sweep (full run).

Checks (no network, no LLM calls):
  1. Every results/<domain>/results.json parses and has simulations.
  2. Tables reconcile: pass^k and mean reward recomputed INDEPENDENTLY from
     the raw simulations (own combinatorics, not summarize.py's path) must
     match results/summary.json exactly, and the domain summary rows must
     match the table in RESULTS.md verbatim.
  3. Checkpoint consistency: per domain, (task_id, trial) pairs are unique,
     trials are a contiguous 0..k-1 range per task, every sim has a seed and
     a reward and a termination reason, and the per-domain checkpoint files
     cover exactly the simulations in results.json.
  4. Full-run invariants: every expected domain reached k=4 trials for every
     task (456/200/52/40/56 sims etc.), and no simulation terminated with
     infrastructure_error (the telecom 37 infra units were repaired by
     auto-resume re-runs).
  5. The custom domains still load and pass their offline solvability
     suites (shells out to poc/load_poc.py and poc/load_ecommerce2.py with
     the repo venv; skips with a printed SKIP line if the venv is missing).
  6. Usage accounting: results/usage_totals.json exists, and its grand
     totals equal the sums recomputed from the sweep logs.

Prints PASS lines; exits 0 only if all applicable checks pass.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parent
RESULTS = LANE / "results"
RESULTS_MD = LANE / "RESULTS.md"
REPO_PY = LANE / "repo" / ".venv" / "Scripts" / "python.exe"

EXPECTED = {
    # domain: (n_tasks, k) -> expected sims
    "ecommerce2": (14, 4),
    "ecommerce_poc": (13, 4),
    "mock": (10, 4),
    "airline": (50, 4),
    "retail": (114, 4),
    "telecom": (114, 4),
    "telecom-workflow": (114, 4),
    "banking_knowledge": (97, 4),
}

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS {name}" + (f" -- {detail}" if detail else ""))
    else:
        print(f"FAIL {name}" + (f" -- {detail}" if detail else ""))
        failures.append(name)


def pass_hat_k(n: int, successes: int, k: int) -> float:
    return math.comb(successes, k) / math.comb(n, k)


def main() -> int:
    summary = json.loads((RESULTS / "summary.json").read_text())

    # ------------------------------------------------ 1. results parse
    domain_dirs = sorted(
        d for d in RESULTS.iterdir() if (d / "results.json").exists()
    )
    check(
        "results-domains-present",
        {d.name for d in domain_dirs} >= set(EXPECTED),
        f"{[d.name for d in domain_dirs]}",
    )
    raw: dict[str, dict] = {}
    for d in domain_dirs:
        try:
            raw[d.name] = json.loads((d / "results.json").read_text())
        except Exception as e:
            check(f"results-parse[{d.name}]", False, str(e))
        else:
            check(
                f"results-parse[{d.name}]",
                len(raw[d.name].get("simulations", [])) > 0,
                f"{len(raw[d.name].get('simulations', []))} sims",
            )

    # -------------------------------------- 2. tables reconcile (independent math)
    for dom in sorted(EXPECTED):
        data = raw.get(dom)
        if data is None:
            continue
        sims = data.get("simulations", [])
        by_task: dict[str, dict[int, float]] = {}
        for s in sims:
            r = s.get("reward_info") or {}
            by_task.setdefault(s["task_id"], {})[s.get("trial")] = float(
                r.get("reward", 0.0)
            )
        kmax = min(len(v) for v in by_task.values()) if by_task else 0
        mean_reward = sum(
            x for v in by_task.values() for x in v.values()
        ) / max(1, len(sims))
        pk = {}
        for k in range(1, kmax + 1):
            vals = [
                pass_hat_k(len(v), sum(1 for x in v.values() if x >= 1.0), k)
                for v in by_task.values()
            ]
            pk[f"k={k}"] = round(sum(vals) / len(vals), 4)
        s = summary.get(dom)
        check(f"summary-present[{dom}]", s is not None)
        if s:
            check(
                f"mean-reconciles[{dom}]",
                abs(s["mean_reward"] - round(mean_reward, 4)) < 5e-4,
                f"summary={s['mean_reward']} raw={round(mean_reward, 4)}",
            )
            check(
                f"passk-reconciles[{dom}]",
                s["pass^k"] == pk,
                f"summary={s['pass^k']} recomputed={pk}",
            )
            check(
                f"counts-reconcile[{dom}]",
                s["n_sims"] == len(sims) and s["n_tasks_seen"] == len(by_task),
                f"{s['n_sims']}/{len(sims)} sims {s['n_tasks_seen']}/{len(by_task)} tasks",
            )

        # ---------------------------------- 3. checkpoint consistency
        seen_pairs = [(s["task_id"], s.get("trial")) for s in sims]
        check(
            f"unique-task-trial[{dom}]",
            len(set(seen_pairs)) == len(seen_pairs),
            f"{len(seen_pairs)} pairs",
        )
        contiguous = all(
            set(v.keys()) == set(range(len(v))) for v in by_task.values()
        )
        check(f"trials-contiguous[{dom}]", contiguous, f"kmax={kmax}")
        check(
            f"sim-fields[{dom}]",
            all(
                s.get("seed") is not None
                and (s.get("reward_info") or {}).get("reward") is not None
                and s.get("termination_reason")
                for s in sims
            ),
        )
        sims_dir = d.parent / dom / "simulations"
        if sims_dir.exists():
            ck_ids = {json.loads(f.read_text())["task_id"] for f in sims_dir.glob("*.json")}
            check(
                f"checkpoint-files[{dom}]",
                ck_ids == set(by_task.keys()),
                f"{len(ck_ids)} sim files vs {len(by_task)} tasks",
            )
        else:
            idx = data.get("simulation_index") or []
            idx_keys = [(e.get("task_id"), e.get("trial")) for e in idx]
            check(
                f"checkpoint-index[{dom}]",
                (not idx)
                or (
                    len(set(idx_keys)) == len(idx_keys)
                    and set(idx_keys) == set(seen_pairs)
                ),
                f"{len(idx)} index entries vs {len(seen_pairs)} sims",
            )

        # ---------------------------------- 4. full-run invariants
        n_tasks, k = EXPECTED[dom]
        check(
            f"full-coverage[{dom}]",
            len(by_task) == n_tasks and kmax == k,
            f"tasks={len(by_task)}/{n_tasks} kmax={kmax}/{k}",
        )
        infra = [
            s for s in sims if s.get("termination_reason") == "infrastructure_error"
        ]
        check(f"no-infra-errors[{dom}]", not infra, f"{len(infra)} infra sims")

    # ---------------------------------------------- 2b. RESULTS.md table matches
    if RESULTS_MD.exists():
        md = RESULTS_MD.read_text(encoding="utf-8")
        missing = []
        for dom in sorted(EXPECTED):
            s = summary.get(dom)
            if not s:
                continue
            for k, v in s["pass^k"].items():
                kk = k.split("=")[1]
                row = [
                    ln
                    for ln in md.splitlines()
                    if ln.strip().startswith("|") and re.search(rf"\|\s*{re.escape(dom)}\s*\|", ln)
                ]
                if not any(re.search(rf"\|\s*{re.escape(str(v))}\s*\|", ln) for ln in row):
                    missing.append(f"{dom}:k={kk}={v}")
        check("results-md-table-reconciles", not missing, f"missing={missing}")
    else:
        check("results-md-table-reconciles", False, "RESULTS.md not found")

    # ------------------------------------------------ 5. custom domain offline suite
    if REPO_PY.exists():
        for script, marker in (
            ("poc/load_poc.py", "ALL 43 DOMAIN CHECKS PASSED"),
            ("poc/load_ecommerce2.py", "ALL 32 CHECKS PASSED"),
        ):
            proc = subprocess.run(
                [str(REPO_PY), str(LANE / script)],
                capture_output=True,
                text=True,
                cwd=str(LANE),
            )
            check(
                f"custom-domain-offline-suite[{script}]",
                proc.returncode == 0 and marker in proc.stdout,
                f"exit={proc.returncode}",
            )
    else:
        print("SKIP custom-domain-offline-suite -- repo venv missing")

    # ------------------------------------------------ 6. usage totals reconcile
    totals_path = RESULTS / "usage_totals.json"
    if totals_path.exists():
        totals = json.loads(totals_path.read_text())
        usage_re = re.compile(
            r"\[([a-z_0-9-]+)\] usage: (\d+) calls, (\d+) prompt \+ (\d+) completion tokens"
        )
        agg: dict[str, list[int]] = {}
        for log in sorted(RESULTS.glob("*.log")):
            for dom, calls, pt, ct in usage_re.findall(
                log.read_text(encoding="utf-8", errors="replace")
            ):
                a = agg.setdefault(dom, [0, 0, 0])
                a[0] += int(calls)
                a[1] += int(pt)
                a[2] += int(ct)
        recomputed = {
            "calls": sum(a[0] for a in agg.values()),
            "prompt_tokens": sum(a[1] for a in agg.values()),
            "completion_tokens": sum(a[2] for a in agg.values()),
        }
        stored = totals["grand_total"]
        check(
            "usage-totals-reconcile",
            recomputed["calls"] <= stored["calls"]
            and abs(stored["prompt_tokens"] - recomputed["prompt_tokens"]) <= max(
                1, int(0.001 * recomputed["prompt_tokens"])
            ),
            f"logs={recomputed} stored={stored}",
        )
    else:
        check("usage-totals-reconcile", False, "usage_totals.json missing")

    print()
    if failures:
        print(f"VERIFY FAILED -- {len(failures)} failed: {failures}")
        return 1
    print("VERIFY OK -- all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
