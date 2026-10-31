#!/usr/bin/env python3
"""Provider-failover retry for the pending targets that z.ai's content filter (error
1301, HTTP 400) rejects on BOTH glm-5.3-flash and glm-5.3.

Same annotation contract as annotate2.py (identical prompt prefix, identical
parse_response, temperature 1.0, zero-shot) but the provider ladder is:
  1. Gemini   gemini-3.5-flash   (volume tier; OpenAI-compatible endpoint)
  2. NVIDIA   nvidia/nemotron-3-super-120b-a12b (volume tier)
  3. OpenRouter nvidia/nemotron-3.5-lightning:free (allowlisted :free, volume only)
Per target, the first provider that returns a parseable answer wins; the winning
model id is recorded in the label record. PRIVACY: prompt to API only; labels/ids/
counts persisted. No key value is ever printed or written.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import annotate2  # noqa: E402  (INSTRUCTIONS, HARNESS_NOTE, parse_response, unredact)
import extract2   # noqa: E402
import trace2     # noqa: E402

TARGETS = HERE / "targets.jsonl"
LABELS = HERE / "labels_full.jsonl"

LADDER = [
    ("gemini", "gemini-3.5-flash", "GEMINI_API_KEY",
     "https://generativelanguage.googleapis.com/v1beta/openai/"),
    ("nvidia", "nvidia/nemotron-3-super-120b-a12b", "NVIDIA_API_KEY",
     "https://integrate.api.nvidia.com/v1"),
    ("openrouter", "nvidia/nemotron-3.5-lightning:free", "OPENROUTER_API_KEY",
     "https://openrouter.ai/api/v1"),
]


def load_pending():
    targets = {}
    with TARGETS.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                t = json.loads(line)
                targets[t["target_id"]] = t
            except Exception:
                pass
    done = set()
    with LABELS.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                done.add(json.loads(line)["target_id"])
            except Exception:
                pass
    return [targets[tid] for tid in targets if tid not in done]


def build_prompt(t):
    real_path = annotate2.unredact(t["path"])
    if t["storage_type"] == "directory":
        fmt, summ = extract2.extract_directory(real_path)
    else:
        fmt, summ = extract2.extract_path(real_path, t["storage_type"], t.get("size") or 0)
    sess = summ[t["part"]] if summ and t["part"] < len(summ) else None
    if not sess:
        return None, None
    label = Path(real_path).name[:60]
    trace = trace2.build_trace(sess, label)
    if not trace:
        return None, None
    defs = annotate2.DEFS_PATH.read_text(encoding="utf-8")
    return (annotate2.INSTRUCTIONS + defs + annotate2.HARNESS_NOTE + trace), trace


def main():
    from openai import OpenAI
    pending = load_pending()
    print(f"[fallback] pending targets: {len(pending)}", flush=True)
    if not pending:
        return 0
    clients = {}
    for name, model, env, base in LADDER:
        if os.environ.get(env):
            clients[name] = OpenAI(api_key=os.environ[env], base_url=base,
                                   timeout=180.0, max_retries=0)
        else:
            print(f"[fallback] {name}: env {env} missing, skipping provider", flush=True)

    results = []
    for t in pending:
        prompt, trace = build_prompt(t)
        if not prompt:
            print(f"[fallback] {t['target_id']}: empty_trace", flush=True)
            continue
        rec = None
        for name, model, env, base in LADDER:
            cli = clients.get(name)
            if cli is None:
                continue
            for attempt in (1, 2, 3):
                try:
                    kw = dict(model=model, messages=[{"role": "user", "content": prompt}],
                              temperature=1.0, max_tokens=2000)
                    if name == "gemini":
                        kw["extra_body"] = {"google": {"thinking_config":
                                                        {"thinking_budget": 0}}}
                    resp = cli.chat.completions.create(**kw)
                    text = resp.choices[0].message.content or ""
                    pt = getattr(getattr(resp, "usage", None), "prompt_tokens", 0) or 0
                    ct = getattr(getattr(resp, "usage", None), "completion_tokens", 0) or 0
                    parsed = annotate2.parse_response(text)
                    if parsed["n_answered"] >= 10:
                        rec = {
                            "target_id": t["target_id"], "sha256": t["sha256"],
                            "ok": True, "task_completed": parsed["task_completed"],
                            "modes": parsed["modes"], "n_answered": parsed["n_answered"],
                            "model": model, "usage": {"pt": pt, "ct": ct},
                            "attempts": attempt, "runtime": t["runtime"],
                            "origin": t["origin"], "format": t["format"],
                            "n_user": t["n_user"], "n_asst": t["n_asst"],
                            "n_msg": t["n_msg"], "n_sidechain": t["n_sidechain"],
                            "first_ts": t.get("first_ts"),
                        }
                        break
                    if attempt == 3:
                        print(f"[fallback] {t['target_id']} @ {model}: parse_fail "
                              f"({parsed['n_answered']}/14 answered)", flush=True)
                except Exception as e:
                    msg = str(e)[:160].replace("\n", " ")
                    print(f"[fallback] {t['target_id']} @ {model} attempt {attempt}: "
                          f"{type(e).__name__}: {msg}", flush=True)
                    time.sleep(3 * attempt)
            if rec:
                print(f"[fallback] {t['target_id']}: OK via {model}", flush=True)
                break
        if rec:
            results.append(rec)

    if results:
        with LABELS.open("a", encoding="utf-8") as out:
            for r in results:
                out.write(json.dumps(r, separators=(",", ":")) + "\n")
    still = len(pending) - len(results)
    print(f"[fallback] wrote {len(results)} labels; still pending {still}", flush=True)
    (HERE / "fallback_pending.json").write_text(json.dumps({
        "attempted": len(pending), "written": len(results),
        "models": [r["model"] for r in results],
        "still_pending": still,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
