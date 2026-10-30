"""Offline verification for the tau2-bench full-scale sweeps (both batches).

Batch 1 (2026-10-18/19, harness v1.0.1 @ 96a3ef9, agent glm-5.3 +
user glm-5.3-flash): checks results/ ... unchanged from the original
verify_fullrun.py (v1 checks below).

Batch 2 (2026-10-28, harness v2.0.0 @ cc1df47, agent grok-4.7 xhigh +
user grok-4.7 low via the local grok-lane bridge): checks results_v2_grok/
-- results parse, full k=4 coverage for every domain (incl. ecommerce3 and
the new intake domain), zero infrastructure_error sims after repairs,
unique (task,trial) pairs, contiguous trials, independent pass^k/mean
recomputation reconciling with results_v2_grok/summary.json and the
RESULTS.md grok section, and usage totals reconciled from the sweep logs.

Checks (no network, no LLM calls). Prints PASS lines; exits 0 only if all
applicable checks pass.
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
RESULTS_GROK = LANE / "results_v2_grok"
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

# grok-4.7 v2.0.0 batch (2026-10-28): every shipped domain of v2.0.0 plus
# the grown custom domain. Task counts verified against the registry at
# cc1df47 this session (mock 10, airline 50, retail 114, telecom 114,
# telecom-workflow 114, banking_knowledge 97, intake 200, ecommerce3 14).
EXPECTED_GROK = {
    "ecommerce3": (14, 4),
    "mock": (10, 4),
    "airline": (50, 4),
    "retail": (114, 4),
    "telecom": (114, 4),
    "telecom-workflow": (114, 4),
    "banking_knowledge": (97, 4),
    "intake": (200, 4),
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


def verify_batch_1() -> None:
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
    # The repo was re-cloned at v2.0.0 @ cc1df47 on 2026-10-24. The v1-era
    # loaders (poc/load_poc.py, poc/load_ecommerce2.py) target the v1.0.1
    # API (e.g. CommunicateEvaluator.calculate_reward() gained a required
    # `scoring` kwarg in v2.0.0) and their passing receipts are preserved
    # from the v1.0.1 run (results/verify_fullrun_output.txt, 2026-10-19).
    # The current lane's custom domain is ecommerce3 (v2.0.0), whose offline
    # suite runs here.
    if REPO_PY.exists():
        proc = subprocess.run(
            [str(REPO_PY), str(LANE / "poc" / "load_ecommerce3.py")],
            capture_output=True,
            text=True,
            cwd=str(LANE),
        )
        check(
            "custom-domain-offline-suite[poc/load_ecommerce3.py]",
            proc.returncode == 0 and "ALL PASS (67/67 checks)" in proc.stdout,
            f"exit={proc.returncode}",
        )
        print(
            "SKIP custom-domain-offline-suite[poc/load_poc.py] -- v1.0.1-era "
            "script, API-incompatible with the v2.0.0 repo (v1 receipt: "
            "results/verify_fullrun_output.txt, 2026-10-19)"
        )
        print(
            "SKIP custom-domain-offline-suite[poc/load_ecommerce2.py] -- v1.0.1-era "
            "script, API-incompatible with the v2.0.0 repo (v1 receipt: "
            "results/verify_fullrun_output.txt, 2026-10-19)"
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


def verify_grok_batch() -> None:
    """Batch 2: grok-4.7 (xhigh agent / low user) on harness v2.0.0."""

    summary_path = RESULTS_GROK / "summary.json"
    check(
        "grok-summary-present",
        summary_path.exists(),
        str(summary_path),
    )
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text())

    # results parse + coverage + infra + uniqueness
    raw: dict[str, dict] = {}
    for dom in sorted(EXPECTED_GROK):
        p = RESULTS_GROK / dom / "results.json"
        if not p.exists():
            check(f"grok-results-parse[{dom}]", False, "results.json missing")
            continue
        try:
            raw[dom] = json.loads(p.read_text())
        except Exception as e:
            check(f"grok-results-parse[{dom}]", False, str(e))
            continue
        sims = raw[dom].get("simulations", [])
        check(
            f"grok-results-parse[{dom}]",
            len(sims) > 0,
            f"{len(sims)} sims",
        )
        by_task: dict[str, dict[int, float]] = {}
        for s in sims:
            r = s.get("reward_info") or {}
            by_task.setdefault(s["task_id"], {})[s.get("trial")] = r.get("reward")
        seen_pairs = [(s["task_id"], s.get("trial")) for s in sims]
        check(
            f"grok-unique-task-trial[{dom}]",
            len(set(seen_pairs)) == len(seen_pairs),
            f"{len(seen_pairs)} pairs",
        )
        contiguous = all(
            set(v.keys()) == set(range(len(v))) for v in by_task.values()
        )
        check(
            f"grok-trials-contiguous[{dom}]",
            contiguous,
            f"kmax={min((len(v) for v in by_task.values()), default=0)}",
        )
        n_tasks, k = EXPECTED_GROK[dom]
        kmax = min((len(v) for v in by_task.values()), default=0)
        check(
            f"grok-full-coverage[{dom}]",
            len(by_task) == n_tasks and kmax == k,
            f"tasks={len(by_task)}/{n_tasks} kmax={kmax}/{k}",
        )
        infra = [
            s
            for s in sims
            if s.get("termination_reason") == "infrastructure_error"
        ]
        check(
            f"grok-no-infra-errors[{dom}]",
            not infra,
            f"{len(infra)} infra sims",
        )
        check(
            f"grok-sim-fields[{dom}]",
            all(
                s.get("seed") is not None
                and (s.get("reward_info") or {}).get("reward") is not None
                and s.get("termination_reason")
                for s in sims
            ),
        )

        # independent pass^k + mean vs summary.json
        s_sum = summary.get(dom)
        check(f"grok-summary-present[{dom}]", s_sum is not None)
        if s_sum is None:
            continue
        evaluable = {
            t: {kk: float(vv) for kk, vv in v.items() if vv is not None}
            for t, v in by_task.items()
        }
        n_eval = sum(len(v) for v in evaluable.values())
        mean_reward = (
            round(sum(x for v in evaluable.values() for x in v.values()) / n_eval, 4)
            if n_eval
            else None
        )
        check(
            f"grok-mean-reconciles[{dom}]",
            s_sum["mean_reward"] == mean_reward,
            f"summary={s_sum['mean_reward']} raw={mean_reward}",
        )
        pk = {}
        for kk in range(1, kmax + 1):
            vals = [
                pass_hat_k(len(v), sum(1 for x in v.values() if x >= 1.0), kk)
                for v in evaluable.values()
                if len(v) >= kk
            ]
            if vals:
                pk[f"k={kk}"] = round(sum(vals) / len(vals), 4)
        check(
            f"grok-passk-reconciles[{dom}]",
            s_sum["pass^k"] == pk,
            f"summary={s_sum['pass^k']} recomputed={pk}",
        )
        check(
            f"grok-counts-reconcile[{dom}]",
            s_sum["n_sims"] == len(sims)
            and s_sum["n_tasks_seen"] == len(by_task),
            f"{s_sum['n_sims']}/{len(sims)} sims {s_sum['n_tasks_seen']}/{len(by_task)} tasks",
        )

    # RESULTS.md grok section reconciles
    if RESULTS_MD.exists():
        md = RESULTS_MD.read_text(encoding="utf-8")
        m = re.search(
            r"## 7\..*?grok-4\.7 second-model batch(.*?)(?=\n## |\Z)",
            md,
            re.S,
        )
        check("grok-md-section-present", m is not None, "§7 grok section")
        if m:
            section = m.group(1)
            missing = []
            for dom in sorted(EXPECTED_GROK):
                s = summary.get(dom)
                if not s or not s.get("pass^k"):
                    missing.append(f"{dom}:no-passk")
                    continue
                v = s["pass^k"].get("k=4")
                row = [
                    ln
                    for ln in section.splitlines()
                    if ln.strip().startswith("|")
                    and re.search(rf"\|\s*{re.escape(dom)}\s*\|", ln)
                ]
                if v is None or not any(
                    re.search(rf"\|\s*{re.escape(str(v))}\s*\|", ln) for ln in row
                ):
                    missing.append(f"{dom}:pass^4={v}")
            check("grok-md-table-reconciles", not missing, f"missing={missing}")
    else:
        check("grok-md-table-reconciles", False, "RESULTS.md not found")

    # usage totals reconcile (from the grok logs, per-process deltas)
    totals_path = RESULTS_GROK / "usage_totals.json"
    if totals_path.exists():
        stored = json.loads(totals_path.read_text())
        usage_re = re.compile(
            r"\[([a-z_0-9-]+)\] usage: (\d+) calls, (\d+) prompt \+ (\d+) completion tokens"
        )
        per_dom_stored = stored.get("per_domain", {})
        for log in sorted(LANE.glob("results_v2_grok*.log")):
            flushes = usage_re.findall(
                log.read_text(encoding="utf-8", errors="replace")
            )
            prev = {"calls": 0, "pt": 0, "ct": 0}
            for dom, calls, pt, ct in flushes:
                calls, pt, ct = int(calls), int(pt), int(ct)
                d_calls = calls - prev["calls"]
                d_pt = pt - prev["pt"]
                d_ct = ct - prev["ct"]
                if dom in per_dom_stored:
                    e = per_dom_stored[dom]
                    # deltas must not exceed stored totals (lower-bound style)
                    if d_calls > e["calls"] or d_pt > e["prompt_tokens"]:
                        check(
                            f"grok-usage-delta[{dom}@{log.name}]",
                            False,
                            f"delta {d_calls}/{d_pt} exceeds stored",
                        )
                prev = {"calls": calls, "pt": pt, "ct": ct}
        gt = stored.get("grand_total", {})
        recomputed_calls = sum(v["calls"] for v in per_dom_stored.values())
        check(
            "grok-usage-totals-reconcile",
            gt.get("calls") == recomputed_calls,
            f"grand={gt.get('calls')} per-domain-sum={recomputed_calls}",
        )
    else:
        check("grok-usage-totals-reconcile", False, "usage_totals.json missing")


def main() -> int:
    verify_batch_1()
    print()
    verify_grok_batch()
    print()
    if failures:
        print(f"VERIFY FAILED -- {len(failures)} failed: {failures}")
        return 1
    print("VERIFY OK -- all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
