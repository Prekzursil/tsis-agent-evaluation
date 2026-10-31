"""Chunk sizing stats for the hierarchical judge (read-only)."""
import json, glob, os
import statistics as st


def walk(s):
    yield s
    for c in s.get("child_spans", []) or []:
        yield from walk(c)


W, S = 15, 10
tot_units = {"GAIA": 0, "SWE Bench": 0}
tot_windows = {"GAIA": 0, "SWE Bench": 0}
unit_sizes = []
win_payloads = []
for split in ["GAIA", "SWE Bench"]:
    for f in sorted(glob.glob(os.path.join("repo/benchmarking/data", split, "*.json"))):
        t = json.load(open(f, encoding="utf-8", errors="replace"))
        spans = [s for top in t.get("spans", []) for s in walk(top)]
        units = []
        for s in spans:
            sa = s.get("span_attributes") or {}
            k = sa.get("openinference.span.kind")
            if k == "LLM":
                outs = []
                i = 0
                while f"llm.output_messages.{i}.message.content" in sa:
                    outs.append(str(sa[f"llm.output_messages.{i}.message.content"]))
                    i += 1
                txt = "\n".join(outs) or str(sa.get("output.value", ""))
                units.append(len(txt))
            elif k == "TOOL":
                txt = str(sa.get("input.value", "")) + "\n" + str(sa.get("output.value", ""))
                units.append(len(txt))
        tot_units[split] += len(units)
        unit_sizes += units
        n = len(units)
        nwin = 1 if n <= W else 1 + -(-(n - W) // S)
        tot_windows[split] += nwin
        # payload of largest window at cap 12k
        for wi in range(nwin):
            lo = wi * S
            hi = min(n, lo + W)
            win_payloads.append(sum(min(u, 12000) for u in units[lo:hi]))

unit_sizes.sort()
win_payloads.sort()
print("units:", tot_units, "total", sum(tot_units.values()))
print("windows:", tot_windows, "total", sum(tot_windows.values()),
      "=> chunk calls", sum(tot_windows.values()), "+ 148 recon =",
      sum(tot_windows.values()) + 148)
print("unit chars: p50/p90/p99/max",
      unit_sizes[len(unit_sizes)//2], unit_sizes[int(len(unit_sizes)*.9)],
      unit_sizes[int(len(unit_sizes)*.99)], unit_sizes[-1])
print("window payload chars (cap 12k/unit): p50/p90/max",
      win_payloads[len(win_payloads)//2], win_payloads[int(len(win_payloads)*.9)],
      win_payloads[-1])
