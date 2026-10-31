#!/usr/bin/env python3
"""Full-scale MAST annotation sweep v2 - hash-keyed over the rebuilt corpus targets.

Same annotation contract as the smoke-stage pipeline (faithful to repo/MAST
llm_judge_pipeline.ipynb: instructions + definitions.txt + trace, @@-delimited binary
answers, temperature 1.0, zero-shot). Keyed by canonical content hash so restarts and
corpus rebuilds resume cleanly. PRIVACY: labels/ids/counts/tokens only are persisted.

Usage:
  python annotate2.py --workers 16 [--limit N] [--tier flash|full|degraded] \
      [--sample N --seed 7] [--labels labels_full.jsonl]
"""
import argparse
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
sys.path.insert(0, str(HERE))
DEFS_PATH = LANE / "repo" / "MAST" / "taxonomy_definitions_examples" / "definitions.txt"
TARGETS = HERE / "targets.jsonl"

# targets.jsonl paths are username-redacted (<USER>); restore the real path to open files.
HOME_NAME = Path(os.path.expanduser("~")).name


def unredact(p: str) -> str:
    return p.replace("<USER>", HOME_NAME) if HOME_NAME else p

BASE_URL = "https://api.z.ai/api/coding/paas/v4"
TIER_MODEL = {"flash": "glm-5.3-flash", "degraded": "glm-5.3-flashx", "full": "glm-5.3"}
MODE_CODES = ["1.1", "1.2", "1.3", "1.4", "1.5",
              "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
              "3.1", "3.2", "3.3"]

INSTRUCTIONS = (
    "Below I will provide a multiagent system trace. provide me an analysis of the failure modes "
    "and inefficiencies as I will say below. \n"
    "In the traces, analyze the system behaviour."
    "There are several failure modes in multiagent systems I identified. I will provide them below. "
    "Tell me if you encounter any of them, as a binary yes or no. \n"
    "Also, give me a one sentence (be brief) summary of the problems with the inefficiencies or "
    "failure modes in the trace. Only mark a failure mode if you can provide an example of it in "
    "the trace, and specify that in your summary at the end\n"
    "Also tell me whether the task is successfully completed or not, as a binary yes or no.\n"
    "At the very end, I provide you with the definitions of the failure modes and inefficiencies. "
    "After the definitions, I will provide you with examples of the failure modes and "
    "inefficiencies for you to understand them better.\n"
    "Tell me if you encounter any of them between the @@ symbols as I will say below, "
    "as a binary yes or no.\n"
    "Here are the things you should answer. Start after the @@ sign and end before the next @@ "
    "sign (do not include the @@ symbols in your answer):\n"
    "*** begin of things you should answer *** @@\n"
    "A. Freeform text summary of the problems with the inefficiencies or failure modes in the "
    "trace: <summary>\n"
    "B. Whether the task is successfully completed or not: <yes or no>\n"
    "C. Whether you encounter any of the failure modes or inefficiencies:\n"
    "1.1 Disobey Task Specification: <yes or no>\n"
    "1.2 Disobey Role Specification: <yes or no>\n"
    "1.3 Step Repetition: <yes or no>\n"
    "1.4 Loss of Conversation History: <yes or no>\n"
    "1.5 Unaware of Termination Conditions: <yes or no>\n"
    "2.1 Conversation Reset: <yes or no>\n"
    "2.2 Fail to Ask for Clarification: <yes or no>\n"
    "2.3 Task Derailment: <yes or no>\n"
    "2.4 Information Withholding: <yes or no>\n"
    "2.5 Ignored Other Agent's Input: <yes or no>\n"
    "2.6 Action-Reasoning Mismatch: <yes or no>\n"
    "3.1 Premature Termination: <yes or no>\n"
    "3.2 Weak Verification: <yes or no>\n"
    "3.3 No or Incorrect Verification: <yes or no>\n"
    "@@ *** end of things you should answer ***\n\n"
    "Here are the definitions of the failure modes and inefficiencies:\n\n"
)

HARNESS_NOTE = (
    "\n\nHere is the multiagent system trace:\n\n"
    "(Context: this is a coding-agent / AI-assistant session transcript from the owner's "
    "personal agent fleet. USER lines are the human operator or harness-injected inputs; "
    "ASSISTANT lines are the AI agent (its prose, tool calls and reasoning); SUB lines are "
    "delegated subagents; TOOL_RESULT lines are tool outputs. Treat the main agent + "
    "subagents + tool loop as the multiagent system.)\n\n"
)


def parse_response(response: str):
    cleaned = response.strip()
    m = re.search(r"\*?\*?\s*@@(.*?)@@", cleaned, flags=re.DOTALL)
    scope = m.group(1) if m else cleaned
    labels = {}
    for code in MODE_CODES:
        mm = re.search(rf"{re.escape(code)}[^:\n]*:\s*\**\s*(yes|no)\b",
                       scope, flags=re.IGNORECASE)
        labels[code] = (mm.group(1).lower() == "yes") if mm else None
    task_m = re.search(r"Whether the task is successfully completed or not:\s*\**\s*(yes|no)\b",
                       scope, flags=re.IGNORECASE)
    n_answered = sum(v is not None for v in labels.values())
    return {
        "task_completed": (task_m.group(1).lower() == "yes") if task_m else None,
        "modes": labels,
        "n_answered": n_answered,
    }


class Sweep:
    def __init__(self, args):
        self.args = args
        self.out_path = HERE / args.labels
        self.status_path = HERE / "sweep_status2.json"
        self.done = set()
        if self.out_path.exists():
            with self.out_path.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        self.done.add(json.loads(line)["target_id"])
                    except Exception:
                        pass
        self.lock = threading.Lock()
        self.tok_lock = threading.Lock()
        self.pace_lock = threading.Lock()
        self.consec_429 = 0
        self.stop_reason = None
        self.model = TIER_MODEL[args.tier]
        self.degraded = False
        self.totals = {"calls": 0, "ok": 0, "parse_fail": 0, "api_fail": 0,
                       "http_429": 0, "prompt_tokens": 0, "completion_tokens": 0,
                       "done_total": len(self.done)}
        from openai import OpenAI
        self.client = OpenAI(
            api_key=os.environ["ZAI_CODING_PLAN_KEY"], base_url=BASE_URL, timeout=180.0,
            max_retries=0)
        self.defs = DEFS_PATH.read_text(encoding="utf-8")
        self.prefix = INSTRUCTIONS + self.defs + HARNESS_NOTE
        self.min_interval = 0.0   # adaptive pacing between request submissions
        self._last_submit = 0.0

    def _pace(self):
        while True:
            with self.pace_lock:
                now = time.time()
                wait = self.min_interval - (now - self._last_submit)
                if wait <= 0:
                    self._last_submit = now
                    return
            time.sleep(min(wait, 0.5))

    def annotate_one(self, t):
        import extract2
        import trace2
        if self.stop_reason:
            return {"target_id": t["target_id"], "ok": False, "fail": "sweep_stopped"}
        try:
            real_path = unredact(t["path"])
            if t["storage_type"] == "directory":
                fmt, summ = extract2.extract_directory(real_path)
            else:
                fmt, summ = extract2.extract_path(real_path, t["storage_type"], t.get("size") or 0)
            sess = summ[t["part"]] if summ and t["part"] < len(summ) else None
        except Exception:
            sess = None
        if not sess:
            return {"target_id": t["target_id"], "ok": False, "fail": "empty_trace"}
        label = Path(real_path).name[:60]
        trace = trace2.build_trace(sess, label)
        if not trace:
            return {"target_id": t["target_id"], "ok": False, "fail": "empty_trace"}
        prompt = self.prefix + trace
        attempts = 0
        while True:
            if self.stop_reason:
                return {"target_id": t["target_id"], "ok": False, "fail": "sweep_stopped"}
            attempts += 1
            self._pace()
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=1.0, max_tokens=2000,
                    extra_body={"thinking": {"type": "disabled"}})
                text = resp.choices[0].message.content or ""
                usage = getattr(resp, "usage", None)
                pt = getattr(usage, "prompt_tokens", 0) or 0
                ct = getattr(usage, "completion_tokens", 0) or 0
                with self.tok_lock:
                    self.totals["prompt_tokens"] += pt
                    self.totals["completion_tokens"] += ct
                parsed = parse_response(text)
                if parsed["n_answered"] < 14 and attempts <= 2:
                    continue
                rec = {
                    "target_id": t["target_id"],
                    "sha256": t["sha256"],
                    "ok": parsed["n_answered"] >= 10,
                    "task_completed": parsed["task_completed"],
                    "modes": parsed["modes"],
                    "n_answered": parsed["n_answered"],
                    "model": self.model,
                    "usage": {"pt": pt, "ct": ct},
                    "attempts": attempts,
                    "runtime": t["runtime"],
                    "origin": t["origin"],
                    "format": t["format"],
                    "n_user": t["n_user"], "n_asst": t["n_asst"], "n_msg": t["n_msg"],
                    "n_sidechain": t["n_sidechain"],
                    "first_ts": t.get("first_ts"),
                }
                if not rec["ok"]:
                    rec["fail"] = "parse_fail"
                with self.lock:
                    self.consec_429 = 0
                    self.min_interval = max(0.0, self.min_interval * 0.98)
                return rec
            except Exception as e:
                name = type(e).__name__
                status = getattr(e, "status_code", None)
                if status == 429 or "429" in str(e)[:200]:
                    with self.lock:
                        self.consec_429 += 1
                        self.totals["http_429"] += 1
                        c = self.consec_429
                        self.min_interval = min(self.min_interval + 0.01, 0.4)
                    if c > self.args.sustained:
                        self._handle_sustained_429()
                        if self.stop_reason:
                            return {"target_id": t["target_id"], "ok": False,
                                    "fail": "sweep_stopped"}
                    ra = getattr(e, "response", None)
                    delay = 6.0
                    try:
                        if ra is not None and ra.headers.get("retry-after"):
                            delay = float(ra.headers["retry-after"]) + 1.0
                    except Exception:
                        pass
                    delay = min(delay + min(c, 12) * 0.8 + random.uniform(0, 2), 90.0)
                    time.sleep(delay)
                    if attempts >= 8:
                        return {"target_id": t["target_id"], "ok": False,
                                "fail": "http_429_exhausted"}
                    continue
                if attempts >= 3:
                    with self.lock:
                        self.totals["api_fail"] += 1
                    return {"target_id": t["target_id"], "ok": False,
                            "fail": f"api:{name}:{str(e)[:80]}"}
                time.sleep(3 * attempts)

    def _handle_sustained_429(self):
        with self.lock:
            if self.args.tier in ("flash", "degraded") and not self.degraded:
                self.degraded = True
                self.model = TIER_MODEL["degraded"]
                self.consec_429 = 0
                print(f"[sweep2] sustained 429s -> DEGRADED tier to {self.model}", flush=True)
            else:
                self.stop_reason = (f"sustained 429s at model={self.model}; "
                                    f"stopping with exact progress recorded")
                print(f"[sweep2] STOP: {self.stop_reason}", flush=True)

    def write_status(self, note=""):
        st = {**self.totals, "model": self.model, "degraded": self.degraded,
              "stop_reason": self.stop_reason, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "note": note}
        self.status_path.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")


def load_targets(sample=None, seed=7):
    metas = []
    with TARGETS.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                metas.append(json.loads(line))
            except Exception:
                pass
    if sample:
        rng = random.Random(seed)
        metas = rng.sample(metas, min(sample, len(metas)))
    metas.sort(key=lambda r: ((r.get("size") or 0), r["target_id"]))
    return metas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tier", choices=["flash", "full", "degraded"], default="flash")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--labels", default="labels_full.jsonl")
    ap.add_argument("--sustained", type=int, default=80)
    args = ap.parse_args()

    if "ZAI_CODING_PLAN_KEY" not in os.environ:
        print("BLOCKER: ZAI_CODING_PLAN_KEY not in env", file=sys.stderr)
        return 3

    metas = load_targets(args.sample, args.seed)
    sweep = Sweep(args)
    todo = [m for m in metas if m["target_id"] not in sweep.done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"[sweep2] targets={len(metas)} already_done={len(sweep.done)} todo_now={len(todo)} "
          f"model={sweep.model} workers={args.workers}", flush=True)

    t0 = time.time()
    n_new = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(sweep.annotate_one, m): m for m in todo}
        for fut in as_completed(futs):
            rec = fut.result()
            # ONLY write full-schema records: ok=true or ok=false w/ parse_fail.
            # 429-exhausted / api-fail / empty-trace results are NOT persisted, so the
            # next resume round retries them.
            if rec is not None and "fail" not in rec or (
                    rec is not None and rec.get("fail") == "parse_fail"):
                with sweep.lock:
                    with sweep.out_path.open("a", encoding="utf-8") as out:
                        out.write(json.dumps(rec, separators=(",", ":")) + "\n")
                    if rec.get("ok"):
                        sweep.totals["ok"] += 1
                    else:
                        sweep.totals["parse_fail"] += 1
                    sweep.totals["done_total"] += 1
            n_new += 1
            if sweep.stop_reason:
                for f in futs:
                    f.cancel()
                break
            if n_new % 100 == 0:
                el = time.time() - t0
                print(f"[sweep2] {n_new}/{len(todo)} ok={sweep.totals['ok']} "
                      f"429={sweep.totals['http_429']} pt={sweep.totals['prompt_tokens']} "
                      f"ct={sweep.totals['completion_tokens']} "
                      f"rate={n_new/max(el,1):.2f}/s eta={(len(todo)-n_new)/max(n_new/el,0.01)/60:.0f}min",
                      flush=True)
                sweep.write_status()
    sweep.write_status("final" if not sweep.stop_reason else "stopped")
    # cumulative per-round history: sweep_status2.json is per-process and gets
    # overwritten by every round (and by cross-check runs sharing the path), so
    # append the final counters of each round here - one JSON line per round.
    with (HERE / "sweep2_status_history.jsonl").open("a", encoding="utf-8") as hf:
        hf.write(json.dumps({**sweep.totals, "model": sweep.model,
                             "degraded": sweep.degraded,
                             "stop_reason": sweep.stop_reason,
                             "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                             "labels_file": args.labels},
                            separators=(",", ":")) + "\n")
    print(f"[sweep2] DONE new={n_new} ok={sweep.totals['ok']} "
          f"parse_fail={sweep.totals['parse_fail']} 429={sweep.totals['http_429']} "
          f"stop={sweep.stop_reason}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
