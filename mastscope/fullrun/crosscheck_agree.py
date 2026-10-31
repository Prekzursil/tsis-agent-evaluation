#!/usr/bin/env python3
"""Tier-agreement analysis: flash-tier volume labels vs full-tier (glm-5.3) re-annotation
of the same 50 trace_ids. Joins fullrun/labels.jsonl with fullrun/crosscheck.jsonl.

Output: fullrun/crosscheck_agreement.json — confusion counts, agreement %, Cohen's kappa
per mode + for task_completed. Counts only.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODE_CODES = ["1.1", "1.2", "1.3", "1.4", "1.5",
              "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
              "3.1", "3.2", "3.3"]


def load(path):
    d = {}
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ok"):
                d[r["trace_id"]] = r
    return d


def kappa(yy, yn, ny, nn):
    n = yy + yn + ny + nn
    if n == 0:
        return None
    po = (yy + nn) / n
    p_yes1 = (yy + yn) / n
    p_yes2 = (yy + ny) / n
    pe = p_yes1 * p_yes2 + (1 - p_yes1) * (1 - p_yes2)
    if pe >= 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def main():
    flash = load(HERE / "labels.jsonl")
    full = load(HERE / "crosscheck.jsonl")
    pairs = [(f, full[tid]) for tid, f in flash.items() if tid in full]
    out_modes = {}
    agree_sum = 0.0
    for m in MODE_CODES:
        yy = yn = ny = nn = 0
        for fl, fu in pairs:
            a, b = fl["modes"].get(m), fu["modes"].get(m)
            if a is None or b is None:
                continue
            if a and b:
                yy += 1
            elif a and not b:
                yn += 1
            elif not a and b:
                ny += 1
            else:
                nn += 1
        n = yy + yn + ny + nn
        agree = (100 * (yy + nn) / n) if n else None
        out_modes[m] = {"yy": yy, "yn": yn, "ny": ny, "nn": nn,
                        "agree_pct": agree, "kappa": kappa(yy, yn, ny, nn)}
        if agree is not None:
            agree_sum += agree
    yy = yn = ny = nn = 0
    for fl, fu in pairs:
        a, b = fl.get("task_completed"), fu.get("task_completed")
        if a is None or b is None:
            continue
        if a and b:
            yy += 1
        elif a and not b:
            yn += 1
        elif not a and b:
            ny += 1
        else:
            nn += 1
    n = yy + yn + ny + nn
    out = {
        "n_pairs": len(pairs),
        "model_flash": pairs[0][0]["model"] if pairs else None,
        "model_full": pairs[0][1]["model"] if pairs else None,
        "modes": out_modes,
        "mean_agree_pct": round(agree_sum / len(MODE_CODES), 1),
        "task": {"yy": yy, "yn": yn, "ny": ny, "nn": nn,
                 "agree_pct": round(100 * (yy + nn) / n, 1) if n else None,
                 "kappa": kappa(yy, yn, ny, nn)},
        "task_agree_pct": round(100 * (yy + nn) / n, 1) if n else None,
        "note": "counts only; no content",
    }
    (HERE / "crosscheck_agreement.json").write_text(json.dumps(out, indent=2) + "\n",
                                                    encoding="utf-8")
    print(f"pairs={len(pairs)} mean_mode_agree={out['mean_agree_pct']}% "
          f"task_agree={out['task_agree_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
