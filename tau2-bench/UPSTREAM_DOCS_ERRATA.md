# Upstream docs errata — sierra-research/tau2-bench @ v1.0.1

**Written:** 2026-10-18 (tau2-bench lane, round-2 audit fix)
**Scope:** two statements in the upstream repo's own docs contradict the data
shipped in the same v1.0.1 tree. The clone in `repo/` is intentionally left
pristine (`git status` clean, remote `sierra-research/tau2-bench`, version
pinned 1.0.1); this file is the in-lane record of the discrepancy. The
dossier correction lives in `research-sota.md` §1.4; `verify.py` pins the
data distributions as regression checks (`reward-basis-data[...]`).

## Erratum 1 — `docs/evaluation.md:12-13` (TL;DR) is stale vs the shipped data

Upstream says:

> The default `reward_basis` for the airline, retail, and telecom domains
> is `["DB", "COMMUNICATE"]` — matching the original τ-bench paper.

Fact (re-parsed this session from `repo/data/tau2/domains/*/tasks.json`):

| domain | tasks | actual `reward_basis` distribution |
|---|---|---|
| airline | 50 | 50 × `[DB, COMMUNICATE]` (explicit in every task JSON) |
| retail | 114 | 112 × `[DB, NL_ASSERTION]`, 2 × `[DB]` — **0 use COMMUNICATE** |
| telecom | 2285 | 2253 × `[ENV_ASSERTION]`, 32 × `[ENV_ASSERTION, ACTION]` — **0 use COMMUNICATE** |

The statement is true only as the **pydantic schema default**:
`src/tau2/data_model/tasks.py:435`
(`default_factory=lambda: [RewardType.DB, RewardType.COMMUNICATE]`), applied
when `reward_basis` is omitted — and for airline's data. Retail and telecom
tasks carry explicit values that diverge from it.

## Erratum 2 — `tasks.py:257-258` docstring (and `docs/evaluation.md:21-24`) claim ACTION is unused in the three core domains

Upstream says (RewardType.ACTION docstring):

> Used in a few `banking_knowledge` tasks; not used in airline/retail/telecom.

Fact: **32 telecom tasks include `ACTION` in `reward_basis`** (all
`[ENV_ASSERTION, ACTION]`), e.g. `[service_issue]lock_sim_card_pin[PERSONA:Hard]`,
`[service_issue]contract_end_suspension[PERSONA:Hard]`,
`[service_issue]airplane_mode_on|lock_sim_card_pin[PERSONA:Easy]`. 20 of the
32 are in the 114-task `base` evaluation split (94 ENV_ASSERTION-only + 20
with ACTION), so even "telecom uses only env assertions" holds for 94/114
base tasks, not all.

## Receipts (this session)

- Data re-parse (workspace-relative `tss/tsis-deepdive/tau2-bench/`):
  `python -c` counter over the three `tasks.json` files → distributions above.
- Telecom split cross-check: `split_tasks.json` `base` ∩ ACTION-gated ids → 20.
- `sed -n '250,268p;425,445p' src/tau2/data_model/tasks.py` and
  `grep -n 'default_factory=lambda\|not used in airline/retail/telecom'` →
  `tasks.py:435`, `tasks.py:257-258`.
- `grep -n -i 'COMMUNICATE\|ACTION\|reward_basis' docs/evaluation.md` →
  lines 12-13 and 21-24.
- `verify.py` checks `reward-basis-data[airline|retail|telecom]` and
  `reward-basis-data[telecom-base-split]` PASS against the same counts.

## Disposition

- Clone left unpatched on purpose (faithful to upstream v1.0.1).
- **Reported upstream (2026-10-18): https://github.com/sierra-research/tau2-bench/issues/635**
  — "docs: evaluation.md reward_basis claims contradict the shipped v1.0.1
  task data (retail/telecom), and ACTION is used in telecom", filed
  2026-10-18T00:41:46Z under the user's account (<os-user> — masked 2026-10-31, privacy
  pass; the GitHub account name is on the linked issue itself), covering both
  errata with the same counts/lines/commit (96a3ef9). State OPEN, 0 comments
  as of this session (`gh issue view 635 --repo sierra-research/tau2-bench`).
- Reinstall check (round 2): `git fetch origin` → up to date; `origin/main`
  still `96a3ef92329baf908ffe9dfe188cea34e8701d2a` (0 new commits) — the
  stale docs are still live upstream, so there is no newer tree to reinstall
  toward. When maintainers land a fix, a plain `git pull` + `python verify.py`
  (the `reward-basis-data[...]` pins double as data-drift guards) is the
  update path.
- No further in-lane action exists: patching the pristine clone would
  misrepresent upstream v1.0.1 and be reverted by any reinstall.
