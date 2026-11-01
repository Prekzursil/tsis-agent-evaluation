# CORPUS — definitive multi-runtime agent-session corpus inventory

Refreshed: **2026-10-30/31** (final run completed 00:30:30; lineage: first build 2026-10-18).
Built by: `build_corpus.py` (this directory) — **READ-ONLY on every source**: the tool only
`os.scandir()`s and `open()`s files for hashing/parsing. Nothing outside this output
directory (`manifest.jsonl`, `dedup_index.json`, `canonical_set.json`, `stats.json`,
`.state.json`, `scan.log`) was moved, renamed, modified or deleted. All output writes are
atomic (tmp + `os.replace`); `.state.json` checkpoints every 5,000 records.

**Location note (2026-10-30):** the project tree was restructured mid-run by a concurrent
lane (`tsis/deepdive` → `tsis/agent-evaluation`, git-committed). The canonical incremental
lineage (incl. `.state.json`) lives HERE (`tsis/agent-evaluation/corpus/`); a synced copy of
the four deliverables is placed at `tsis/deepdive/corpus/` (the path the build mandate
names). Re-run the builder from THIS directory.

## 1. Totals (final run 2026-10-31T00:30)

| metric | value |
|---|---|
| manifest records | **163,681** (155,976 `ok` + 7,705 `missing`, never dropped) |
| unique content hashes (annotation set) | **71,590** |
| duplicate files / duplicate hashes | 122,448 files sharing 38,062 hashes |
| parsed (`parse_ok=true`) | 99,853 · deferred (budget) 50,074 |
| total bytes of `ok` records | 409,207,979,223 (≈381.0 GiB) |
| total message records counted | 45,332,719 |
| by drive | C: 65,022 · D: 90,954 |
| by origin | live 61,055 · backup 70,932 · **orphan-backup 23,989** |
| by storage_type | jsonl 124,761 · json 14,621 · zst 5,272 · gz 2,036 · sqlite 2,186 · directory 3,421 · other 3,679 |
| run economics | final warm run: `hashed=140 reused=155,785 errors=0` (~10 min, all cached except new live files); first cold run 2026-10-18 ~33 min |

Per-file schema: `{path, drive, runtime, origin, storage_type, size, mtime, sha256,
parse_ok, message_count, first_ts, last_ts, status, parse_note, file_count, members,
jsonl_members}` (`status` = `ok`/`missing`; `file_count` on directory records; `members`
on tar records).

Identity rule (control fact a): `sha256` is over the file's bytes **as stored** — for
`.jsonl.zst` that is the **compressed** bytes; decompression is used only to count
messages, never for identity.

## 2. Per-runtime inventory (ok records; 81 runtimes — top 42 shown)

| runtime | files | size | parsed | origin | where |
|---|---:|---:|---:|---|---|
| agent-sessions-vault | 60,707 | 212.6 GiB | 59,265 | backup | `D:\agent-sessions-vault\stores\**` (63 stores; grew 39.7k→60.7k files since Oct 18) |
| claude-code | 31,807 | 37.8 GiB | 23,944 | live+backup | `~/.claude/projects` + `D:\claude-projects-archive` |
| claude-code-free | 22,516 | 17.8 GiB | 2,487 | live | `~/.claude-free` — parallel Claude home, missed by every control |
| claude-history-viewer | 19,769 | 10.1 GiB | 0 | orphan-backup | `D:\claude-history-viewer-archive` (C: `~/.claude-history-viewer` = 1-file stub, control fact e) |
| **antigravity-cli (NEW)** | 3,894 | 0.56 GiB | 1,540 | live | `~/.gemini/antigravity-cli` — conversations/*.db(.pb), history.jsonl, brain/ — **found by this refresh, in no control** |
| grok | 3,416 (dirs) | 5.9 GiB | 3,416 | live | `~/.grok/sessions/<enc-cwd>/<id>/` — one DIRECTORY per session (fact b); Merkle sha; disk count re-verified = 3,416 |
| vm-backup | 3,389 | 3.6 GiB | 3,299 | orphan-backup | `~/Downloads/Backups/**` (re-homed, §5) |
| codex | 2,628 | 1.46 GiB | 2,628 | live | `~/.codex/sessions` — **.jsonl.zst only** (fact a) |
| other:vscode | 1,850 | — | ~0 | live | generic dotdir sweep |
| cursor-chats | 1,690 | 1.95 GiB | 1,261 | live | `~/.cursor/chats` (json + sqlite) |
| zcode-exec | 1,203 | 0.07 GiB | 0 | live | `~/.zcode/cli/exec/**` (fact h; sess_ dirs under bash-startup/ + shell-snapshots/) |
| from-c-backup (NEW) | 375 | 0.30 GiB | 17 | orphan-backup | `D:\Downloads\from-C-20260818` (67 GB C:-copy; Firefox-profile dbs + relocated .claude jsonl) |
| zcode-workspace | 365 | 0.50 GiB | 227 | live | `~/.zcode/workspace/**` |
| ai-exports | 241 | 1.21 GiB | 235 | orphan-backup | `~/Downloads/AI-Conversations/**` (re-homed, §5; includes the skills_claude_web tree) |
| gemini-cli | 203 | — | 203 | live | `~/.gemini/tmp/<proj>/chats/session-*.jsonl` |
| zcode-rollout | **83** | **37.9 GiB** | 65 | live | `~/.zcode/cli/rollout` — **rotated since Oct 18** (530 files/19.1 GiB → ~80/37.9 GiB; the 527 vanished files are `missing`-retained with hashes) |
| cowork-private (NEW) | 81 | 18.8 GiB | 49 | orphan-backup | `~/Cowork/private` — state.vscdb cursor snapshots (§5b-8) |
| cowork-backups (NEW) | 112 | 0.02 GiB | 85 | orphan-backup | `~/Cowork/backups` |
| cursor-globalstorage | 2 | 2.8 GiB | 0 | live | `state.vscdb` (3.0 GB) + conversation-search.db — sqlite, `parse_ok=false` by design |
| zcode-image-cache / -memories / -v2 / -cli-db / -backup | 47/126/2/1/8 | 0.45 GiB | 0/0/0/0/0 | live | fact h stores; v2 has **no `*.bak` db snapshots on disk** (receipt: `ls ~/.zcode/v2/*.bak*` → only config/setting .bak, no db.sqlite.bak) |
| codex-root-state / codex-archived | 12 / 19 | 0.72 GiB | 6/19 | live | `~/.codex` top + `archived_sessions` |
| claude-desktop-* | 11+2+1 | 0.05 GiB | 11+0+0 | live | Roaming\Claude: code-sessions 11, IndexedDB+LocalStorage leveldb 2+1; **local-agent-mode-sessions vanished** (2 records now `missing` — Claude Desktop removed it) |
| claude-agent-worktrees / -handoff / todos / checkpoints / history / server-commander | 10/5/24/2/1/1 | — | 10/0/24/2/1/1 | live | facts (g)+(this refresh's additions; todos = uuid-agent-*.json via walk_all — the prior CORPUS's "24" never existed in its own manifest, now it really does) |
| antigravity (NEW) | 8 | — | 8 | live | `~/.gemini/config/projects/*.json` (uuid names; prior CORPUS claimed these but no root covered them — fixed) |
| agentchattr (NEW) | 4 | — | 4 | live | `D:\agentchattr\data\{agentchattr_log,claude_queue,codex_queue,gemini_queue}.jsonl` (was wrongly D_PRUNEd) |
| grok-root (NEW) | 2 | — | 1 | live | `~/.grok` top (active_sessions.json …) |
| basic-memory-sessions | 51 | — | 0 | live | `D:\basic-memory\sessions\*.md` |
| d-backups | 33 | 5.75 GiB | 0 | backup | `D:\Backups/**` (docker-volumes/images pruned) |
| claude-desktop-backup (NEW) | 22 | 0.01 GiB | 22 | orphan-backup | `~/Documents/claude-desktop-backup-20260524` (7,460-file tree; 22 session-matching) |
| skills-claude-web / vm-consolidated (old paths) | 0 ok (210 + 12 `missing`) | — | — | — | content now lives under ai-exports / vm-backup at the re-homed parents |
| codex-seed-tar | 2 (1 ok + 1 missing) | 40.9 GiB | — | backup | vault copy **byte-identical** to the vanished original (sha `f44910f3…` MATCH); 2,186 members listed, never extracted |
| cline / copilot / copilot-mem0 / continue-index / opencode / cyberstrike | 26/1/1/2/2/1 | 0.73 GiB | 18/1/0/0/1/0 | live | as Oct-18 |
| other:* (generic sweep) | ~4,300 | ~2.9 GiB | ~10 | live | `.agents` 732, `.pplx` 149, `.grok-fleet` 48, `.scratch` 47, `.quokka` 30 … |

Checked, confirmed **no session store** (receipts: `ls`/`find` this session):
`.aider` (analytics/caches; no `.aider.chat.history.md` — checked), crush (no dir on C: at
all), fabric (Roaming shell = `locales` only), Windsurf (no Roaming dir; `.codeium/windsurf`
= 1 config json), Goose (`~/.goose` absent; `.config/goose` = configs + skills, **0 jsonl**;
`.local/share/goose` absent), Roo/Cline VS Code ext (no globalStorage entry; Cline lives at
`~/.cline`), `~/.antigravity` (empty), `AppData\Local\Temp\tmp.*/sessions` (zero matches),
`D:\verdict-archive` (web-crawl archive: html/items + 1 index.jsonl — non-session, see §5c),
`D:\Downloads\from-C-20260818` non-session bulk (media/installers).

## 3. Dedup & canonical set (control fact c)

Deduplication is **strictly per-file sha256** — no lineage/session-id/filename logic
anywhere. The failure mode documented in the vault note *"resumed-session merge fix (47% of
real Codex store silently dropped)"* (two rollout files sharing one `session_id`) is
structurally impossible here: every physical file is its own manifest record keyed by its
own hash. 122,392 duplicate paths across 38,048 hashes are the expected consequence of the
vault/backup strategy (the wave-7/8 vault deliberately re-copies live stores).

- `dedup_index.json` — every hash with >1 path → all paths (sorted).
- `canonical_set.json` — one path per unique hash: **newest mtime wins, tie → larger size,
  tie → lexicographically smallest path** (deterministic). The annotation set = 71,559.

## 4. Origin classification & orphans

- `live` — under a live store root (incl. `~/.codex/archived_sessions`; `D:\basic-memory`;
  `D:\agentchattr` — the bridge tool's live data home).
- `backup` — copy whose original store still exists (vault `stores/**`, `D:\claude-projects-archive`).
- `orphan-backup` (23,989) — original no longer exists as a usable local store:
  `D:\claude-history-viewer-archive` (19,769; fact e), re-homed Downloads backups
  (vm-backup 3,389 + skills 210 + vm-consolidated 12 + ai-exports 241), `~/Cowork/{private,backups}`
  (VM/cursor snapshot lineage), `~/Documents\claude-desktop-backup-20260524`, `D:\Downloads\from-C-20260818`.
- **`missing` (7,705) is not deletion** — read-only guarantee. Breakdown by runtime:
  vm-backup 3,376 (old `Downloads\BACKUPS VM` path, re-homed), codex 3,101 (the D: codex
  archive 1,586 + seed-extracted 1,514 + old tar path 1 — all consolidated INTO the vault;
  the vault's copies are indexed `ok` with identical hashes), zcode-rollout 527 + zcode-exec
  398 + zcode-workspace 33 (live-store rotation since Oct 18), skills 210 / ai-exports 28 /
  vm-consolidated 12 (re-homed), d-backups 15, claude-desktop-agent-mode 2 (store removed
  by Claude Desktop), agent-sessions-vault 2, codex-seed-tar 1 (old path), other churn.

## 5. Control-source reconciliation (BOTH directions)

Controls: **S1** `ai-sessions-render` (`llm_anthology/discover.py` PROVIDERS + `adapters/`);
**S2** vault notes `D:\basic-memory\projects\ai-sessions-render\*.md` (facts a/b/c);
**S3** `out\harness-audit-2026-10-18\CONTROL-session-stores.md` (+ its own control:
`sessions-vault.md` discovery table, 57-store `stores.yaml`); **S4** the build mandate
(facts d–j); **S5** the wave-8 vault itself (`manifest-summary.json` 2026-10-22: 63 stores,
234,193 files / 347.21 GB; `state/last-run.json` finished 2026-10-24, lossrisk=0).

### 5a. Every store any control knows → status here

| control store | here? | evidence |
|---|---|---|
| codex `.jsonl.zst` live (S1,S2-a) | ✅ 2,628 zst | §2 |
| Grok dir-per-session (S1,S2-b) | ✅ 3,416 dir records | §2 (disk recount = manifest) |
| per-file-hash dedup (S2-c) | ✅ structural | §3 |
| claude-code projects / codex_state / chatgpt+claude+gemini exports (S1) | ✅ | §2 (ai-exports) |
| `D:\claude-history-viewer-archive`, `D:\claude-projects-archive` (S3,e,f) | ✅ 19,769 / 10,014+ | §2 |
| agent-worktrees / agent-handoff (S3,S4-g) | ✅ 10 / 5 | §2 |
| Temp `tmp.*/sessions` (S3) | ✅ checked, zero exist | §2 receipts |
| vault / codex archives / seed tar (S4-f) | ✅ vault 60,707 ok; D: originals `missing`, vault copies ok; tar sha-identical, 2,186 members via headers only | §1, §4 |
| zcode exec/image-cache/v2 (S4-h) | ✅ 1,203 / 47 / 2 (+8 zcode-backup) | §2 |
| Downloads four backups (S4-i) | ✅ re-homed & covered at new parents | §5b-1 |
| junction triad (S4-j) | ✅ walker skips all reparse points; no `du` anywhere | `build_corpus.py::walk_files` |
| wave-8 additions beyond old ROOTS: claude-history, claude-free, claude-server-commander, grok-root, d-agentchattr, cowork-*, claude-desktop-backup-20260524, downloads-loose-rollouts (S3 sessions-vault.md) | ✅ ALL now first-class roots (this refresh); loose rollouts: 0 files remain on disk (`glob` receipt) — their vault copies are indexed | §2 |
| S5 vault stores `goose-config` (3,237 files) / `goose-appdata` (88) / `grokbot` (13) / `verdict-archive` (34,118) / `primariro-scratchpad-archive` (10) | ⚠️ vault whole-tree copies of **non-session** config/web-crawl data — vaulted by the vault's content-preservation policy, deliberately not session-corpus material; `.config/goose` itself probed: **0 jsonl**; `D:\verdict-archive`: 1 index.jsonl (web crawl) | §2 receipts |
| S5 `gemini-antigravity` (3,890) | ✅ now indexed live as antigravity-cli 3,894 | §2 |

### 5b. Found by this scan beyond the controls

1. **`~/.gemini/antigravity-cli`** — the Antigravity CLI session store (conversations
   .db/.pb ×120, history.jsonl, conversation_summaries.db, brain/) — in NO control source;
   the prior corpus missed it (`.gemini` is sweep-excluded; only `tmp` was a root).
2. `D:\Downloads\from-C-20260818` — 67 GB August copy of C: user data; 375 session-level
   records (Firefox profile dbs, relocated `.claude` trees under `New folder (2)`, `SWFOC
   editor`, `swfoc_memory`).
3. The Downloads **re-homing** itself (control paths now 404): `AI-Conversations\` and
   `Backups\` parents now carry the four control-(i) stores.
4. ZCode live-store rotation (rollout 530→80 files at ~2× per-file size) — detected, history
   kept as `missing` with hashes.
5. Prior refresh's beyond-control finds stand: `.claude-free` (22,497), `D:\basic-memory\sessions`,
   Claude Desktop stores, cursor globalStorage sqlite, VS Code Copilot surfaces, `.cline`,
   `.copilot`, `.continue`, `.local/share/opencode`, `.cyberstrike`.

### 5c. Known to controls, deliberately not manifest-tracked

- `~/.codex/archived_sessions` is INCLUDED (superset vs S1, which skips it).
- S1's anywhere-on-disk export matching is bounded here to scanned roots (a
  `conversations.json` in an arbitrary unswept folder would be missed — bounded by §6 scope).
- Vault stores that are pure config/web-crawl (goose-config, verdict-archive, …) — see §5a.

### 5d. Numeric cross-check vs the vault's own manifest (S5)

Vault summary (Oct 22) top stores vs this corpus's ok-records for the same content
(different accept rules — vault = whole-tree, corpus = session-pattern):
grok 70,969 files ↔ 3,416 dirs · claude-free 20,150 ↔ 22,497 · claude-code 19,457 ↔ 31,789 ·
claude-projects-archive 14,378 ↔ ~10,000 accepted · codex-archive 1,587 ↔ 60.79 GB absorbed into
vault runtime · codex-live 2,618 ↔ 2,628 · cowork-private 130 ↔ 81 (snapshot churn) ·
zcode-rollout 778 ↔ 81 live (vault froze the pre-rotation copy). No store known to the vault
is absent here after this refresh; the two prior one-way gaps (antigravity-cli live,
Cowork originals) are closed.

## 6. Exclusions (every one deliberate — hard rule 2)

Directory prunes (all roots): `node_modules .venv venv .git __pycache__ .pytest_cache
.mypy_cache .ruff_cache .ipynb_checkpoints target site-packages dist-info .hg .svn`.
Transient sqlite sidecars `-shm/-wal/-journal` skipped (main db is the record). Home-sweep
prunes (package/model/browser caches): `.cache .cargo .rustup .gradle .m2 .conda .npm .nuget
.dotnet .vscode-server* .android .docker .ollama .lmstudio .VirtualBox
.ScreamingFrogSEOSpider .kivy .msf4 go …` (full set in `build_corpus.py::HOME_SWEEP_PRUNE`).
D: depth-2 discovery prunes (61 names, `build_corpus.py::D_PRUNE`; `agentchattr` REMOVED
from it this refresh). `D:\Backups` prunes `docker-volumes/images`. Corpus dir self-excluded.
Generic `*.json` acceptance is name-gated (session/chat/conversation/history/rollout/
transcript/dialog/thread/completion/prompt, `local_*`, `ses_*`, `session-*`, `meta.json`,
`conversations*.json`, `codex.json`, `transcript.json`). Not scanned: non-dotdir project
folders on C: outside named roots, `Documents\GitHub\*`, WSL/VHDX interiors, browser-profile
caches, `D:\verdict-archive` (web crawl).

## 7. Verification receipts (executed this refresh)

- **Determinism (hashing)**: 25 independent re-hashes vs manifest sha256 — 12 random jsonl
  (seed 42) + stratified 3×zst, 3×gz, 3×json, 3×sqlite (seed 7) + 1 grok session-dir Merkle
  (18 files) recomputed from scratch — **25/25 MATCH, 0 mismatches** (commands in build log).
- **Grok disk recount**: on-disk session dirs 3,416 == manifest grok records 3,416.
- **Tar**: vault copy sha `f44910f341ba31f4…` == vanished original's sha; members 2,186 /
  jsonl_members 1,514 listed via streamed headers, never extracted.
- **Incrementality**: warm runs `hashed=92 reused=155,746`, `hashed=71 reused=155,781`,
  `hashed=140 reused=155,785`, errors=0 — ≥99.9 % cache skip.
- **Missing-history**: 7,705 missing records retained with full metadata (incl. sha256).
- **zst**: scan.log `zstandard=True`; live codex rollouts hashed as compressed bytes,
  parsed after decompression.
- **Interrupted-run safety**: a killed mid-scan run (23:08, exit -1) lost nothing — the next
  run resumed from the 5,000-record checkpoint and completed.
- Full timestamped log: `scan.log`.

## 8. Keeping the corpus current (re-run instructions)

```cmd
cd C:\Users\<os-user>\.zcode\workspace\default\tsis\agent-evaluation\corpus
python build_corpus.py --update                      # warm re-scan (~5-10 min)
python build_corpus.py --update --parse-budget-gb 0  # unlimited: fills deferred parses
python build_corpus.py --roots "codex"               # touch a subset only
```

Suggested cadence: **daily** or after heavy session days. Each `--update` re-attempts
deferred parses with a fresh 40 GiB budget, so parse coverage converges (99,784 parsed /
50,074 deferred after 3 runs). `message_count` = valid JSON-object lines (jsonl/zst/gz) or
list/dict entries (json) — record counts, not strict user turns. The scan is read-only,
timestamped and re-runnable by design; concurrent vault pipelines writing during a scan
manifest as growth (§5d), never as loss.
