#!/usr/bin/env python3
"""Tier agreement: full-tier (glm-5.3) crosscheck2.jsonl vs flash labels_full.jsonl."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODE_CODES = ["1.1", "1.2", "1.3", "1.4", "1.5",
              "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
              "3.1", "3.2", "3.3"]


def main():
    flash = {}
    with (HERE / "labels_full.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
                flash[r["target_id"]] = r
            except Exception:
                pass
    full = []
    with (HERE / "crosscheck2.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
                if r.get("ok"):
                    full.append(r)
            except Exception:
                pass

    modes = {}
    agree_sum = 0.0
    task_stats = {"yy": 0, "yn": 0, "ny": 0, "nn": 0}
    pairs = 0
    for r in full:
        f = flash.get(r["target_id"])
        if not f or not f.get("ok"):
            continue
        pairs += 1
        for m in MODE_CODES:
            a, b = r["modes"].get(m), f["modes"].get(m)
            d = modes.setdefault(m, {"yy": 0, "yn": 0, "ny": 0, "nn": 0, "none": 0})
            if a is None or b is None:
                d["none"] += 1
                continue
            d["yy" if a and b else "yn" if a and not b else "ny" if b and not a else "nn"] += 1
        ta, tb = r.get("task_completed"), f.get("task_completed")
        if ta is not None and tb is not None:
            key = "yy" if ta and tb else "yn" if ta and not tb else "ny" if tb and not ta else "nn"
            task_stats[key] += 1

    out_modes = {}
    for m in MODE_CODES:
        d = modes.get(m, {})
        tot = d.get("yy", 0) + d.get("yn", 0) + d.get("ny", 0) + d.get("nn", 0)
        out_modes[m] = {
            **{k: d.get(k, 0) for k in ("yy", "yn", "ny", "nn", "none")},
            "agree_pct": round(100 * (d.get("yy", 0) + d.get("nn", 0)) / max(tot, 1), 1),
        }
        agree_sum += out_modes[m]["agree_pct"]
    tt = sum(task_stats.values())
    out = {
        "model_flash": flash[full[0]["target_id"]]["model"] if full and full[0]["target_id"] in flash else "glm-5.3-flash",
        "model_full": full[0]["model"] if full else "?",
        "n_crosscheck_ok": len(full),
        "n_pairs": pairs,
        "modes": out_modes,
        "mean_agree_pct": round(agree_sum / len(MODE_CODES), 1),
        "task_agree_pct": round(100 * (task_stats["yy"] + task_stats["nn"]) / max(tt, 1), 1),
        "task_confusion": task_stats,
    }
    (HERE / "crosscheck2_agreement.json").write_text(json.dumps(out, indent=2),
                                                     encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n_pairs", "mean_agree_pct", "task_agree_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
