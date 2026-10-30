# CORPUS — definitive multi-runtime agent-session corpus inventory

Generated: 2026-10-18 (final scan run completed 10:30:04; machine-local time)
Built by: `build_corpus.py` (this directory) — **READ-ONLY on every source**: the tool only
`os.scandir()`s and `open()`s files for hashing/parsing. Nothing outside this output
directory (`manifest.jsonl`, `dedup_index.json`, `canonical_set.json`, `stats.json`,
`.state.json`, `scan.log`) was moved, renamed, modified or deleted. All output writes are
atomic (tmp + `os.replace`). The corpus output directory itself is excluded from indexing
(self-exclusion) so the inventory can never index its own artifacts.

## 1. Totals

| metric | value |
|---|---|
| manifest records | **124,327** (122,733 `ok` + 1,594 `missing`, never dropped) |
| unique content hashes (annotation set) | **41,877** |
| duplicate files / duplicate hashes | 116,445 files sharing 35,589 hashes |
| parsed (message_count extracted) | 68,633 (`parse_ok=true`) |
| parse-deferred (budget; see §10) | 51,548 — picked up by later `--update` runs |
| total bytes of `ok` records | 371,673,156,809 (≈346.1 GiB) |
| total message records counted | 35,885,450 |
| by drive | C: 51,643 · D: 71,090 |
| by origin | live 47,892 · backup 51,446 · **orphan-backup 23,395** |
| by storage_type | jsonl 109,199 · json 4,294 · zst 5,270 · gz 1,118 · sqlite 1,477 · directory 510 · other 865 |

Per-file schema: `{path, drive, runtime, origin, storage_type, size, mtime, sha256,
parse_ok, message_count, first_ts, last_ts, status, parse_note, file_count, members,
jsonl_members}` (`status` is `ok`/`missing`; `file_count` on directory records; `members`
on the tar record).

Identity rule (control fact a): `sha256` is over the file's bytes **as stored** — for
`.jsonl.zst` that is the **compressed** bytes. Decompression is used only to count
messages, never for identity.

## 2. Per-runtime inventory (records ≥ 5; 72 runtimes total)

| runtime | files | size | parsed | origin mix | where |
|---|---:|---:|---:|---|---|
| agent-sessions-vault | 39,716 | 163.2 GiB | 38,421 | backup | `D:\agent-sessions-vault\stores\**` (wave-7/8 sync target; growing during scan — §8) |
| claude-code | 29,365 | 30.9 GiB | 21,503 | live 19,351 + backup 10,014 | `~/.claude/projects` + `D:\claude-projects-archive` |
| claude-code-free | 20,040 | 12.3 GiB | 1 | live | `~/.claude-free/projects` — **parallel Claude home, missed by every control** |
| claude-history-viewer | 19,769 | 9.4 GiB | 0 | orphan-backup | `D:\claude-history-viewer-archive` (C: `~/.claude-history-viewer` is a 1-file stub) |
| codex | 4,131 ok (+1,586 missing) | 42.2 GiB ok | 2,617 | live 2,617 + backup 1,514 | `~/.codex/sessions` (.zst), `archived_sessions` (19, separate runtime), `D:\codex-seed-extracted`; `D:\codex-sessions-archive-20260621` emptied mid-scan (§8) |
| codex-seed-tar | 1 | 40.9 GiB | — | backup | `D:\codex-sessions-seed-20260315.tar`, **2,186 members** listed via tar headers only, never extracted |
| vm-backup | 3,376 | 3.4 GiB | 3,286 | orphan-backup | `~/Downloads/BACKUPS VM` (VM profile snapshots containing session files) |
| cursor-chats | 1,522 | 1.8 GiB | 1,093 | live | `~/.cursor/chats` (json + sqlite) |
| cursor-globalstorage | 2 | 2.8 GiB | 0 | live | `AppData\Roaming\Cursor\User\globalStorage\state.vscdb` (3.0 GB) + `conversation-search.db` — sqlite, `parse_ok=false` by design |
| cursor-acp | 4 | — | 2 | live | `~/.cursor/acp-sessions/<uuid>/{meta.json,store.db}` |
| vscode-globalstorage / -workspacestorage | 3 / 54 | 0.02 GiB | 0 | live | Copilot-chat state.vscdb + `github.copilot-chat` session jsons |
| zcode-rollout | 530 | 18.3 GiB | 520 | live | `~/.zcode/cli/rollout/model-io-sess_*.jsonl` |
| zcode-exec | 719 | 8.3 GiB | 0 | live | `~/.zcode/cli/exec/sess_<id>/**` (all files; exec logs) |
| zcode-image-cache | 28 | 0.01 GiB | 0 | live | `~/.zcode/cli/image-cache/sess_<id>/**` |
| zcode-memories | 69 | <0.01 GiB | 0 | live | `~/.zcode/cli/memories/{projects,sess_*}` |
| zcode-v2 / zcode-cli-db | 2 / 1 | 0.4 GiB | 0 | live | `~/.zcode/v2/db.sqlite`(+`tasks-index.sqlite`) · `~/.zcode/cli/db/db.sqlite` (no `*.bak` snapshots exist — verified by `ls`) |
| zcode-workspace | 296 | 0.18 GiB | 170 | live | `~/.zcode/workspace/**` session-pattern files (corpus dir self-excluded) |
| grok | 505 (dirs) | 3.9 GiB | 505 | live | `~/.grok/sessions/<enc-cwd>/<session-id>/` — **one DIRECTORY per session** (control fact b); `sha256` = Merkle digest over the session dir's file hashes; `message_count` from `updates.jsonl`+`chat_history.jsonl` |
| grok-desktop | 2 | — | 0 | live | `AppData\Roaming\Grok Bot` leveldb dirs (directory records) |
| gemini-cli | 197 | <0.01 GiB | 197 | live | `~/.gemini/tmp/<proj>/chats/session-*.jsonl` |
| antigravity | 14 | — | 14 | live | `~/.gemini/config/projects/*.json` (the real target of the `~/.antigravitycli` **symlink**, which is never traversed) + `AppData\Local\antigravity` |
| claude-desktop-code-sessions | 8 | — | 8 | live | `AppData\Roaming\Claude\claude-code-sessions/<u1>/<u2>/local_*.json` |
| claude-desktop-agent-mode | 2 | — | 2 | live | `AppData\Roaming\Claude\local-agent-mode-sessions/**` |
| claude-desktop-indexeddb / -localstorage | 2 / 1 | — | 0 | live | claude.ai desktop leveldb (directory records, `parse_ok=false`) |
| claude-agent-worktrees | 10 | — | 10 | live | `~/.claude/agent-worktrees/agent-*/` (control fact g) |
| claude-agent-handoff | 5 | — | 0 | live | `~/.claude/agent-handoff/**` — all files, index-only (control fact g) |
| claude-todos / claude-checkpoints | 24 / 2 | — | 2 | live | `~/.claude/todos/*.jsonl`, `~/.claude/checkpoints` |
| codex-root-state | 12 | 0.7 GiB | 6 | live | `~/.codex/{history.jsonl, session_index.jsonl, state_5.sqlite, …}` |
| codex-archived | 19 | — | 19 | live | `~/.codex/archived_sessions` (ai-sessions-render deliberately skips it; we include it) |
| opencode | 2 | — | 1 | live | `~/.local/share/opencode/{opencode.db, storage/session_diff/ses_*.json}` |
| cline | 26 | 0.35 GiB | 18 | live | `~/.cline/apps/kanban/sessions/*.jsonl`, `user_input_history.jsonl`, `db/*.db` |
| copilot / copilot-mem0 | 1 / 1 | — | 1 | live | `~/.copilot/session-state/*.jsonl` · `~/.copilot/mem0` |
| continue-index | 2 | — | 0 | live | `~/.continue/index/*.sqlite` |
| cyberstrike | 1 | — | 0 | live | `~/.cyberstrike/cyberstrike.db` |
| basic-memory-sessions | 43 | — | 0 | live | `D:\basic-memory\sessions\*.md` — **vault's own session-capture notes; no control names it** |
| ai-exports | 28 | 0.26 GiB | 28 | orphan-backup | `~/Downloads/AIs Conversations` (ChatGPT/Claude/Gemini export `conversations.json`/`transcript.json`) |
| skills-claude-web | 210 | — | 206 | orphan-backup | `~/Downloads/skills_claude_web` |
| vm-consolidated | 12 | — | 12 | orphan-backup | `~/Downloads/vm-consolidated-2026-09-24` |
| d-backups | 33 | 3.6 GiB | 0 | backup | `D:\Backups/**` (config snapshots etc.) |
| other:* (generic sweep) | ~2,000 | ~2.7 GiB | ~5 | mostly live | 33 further dotdirs — largest: `.vscode` 923, `.agents` 690, `.pplx` 149, `.scratch` 47, `.quokka` 30 … |

Checked and confirmed **empty of session-like files** (receipts: `ls`/`find` in the build
session): `.aider` (analytics/caches only), `.continue/dev_data` (empty), `.agy`
(AGENTS.md/skills), `.gemini/history` (git checkpointer data, no jsonl), AppData
`Goose`/`Codex`/`Claude`-caches/`fabric` (Electron app shells), `AppData\Local\Temp\tmp.*/sessions`
(pattern from the control — **zero matches**), `D:\Users\Prekzursil` (empty profile stub),
`.claude-free` sibling dirs `agents-backup-20260810`/`ast-salvage-20260810`/`file-history`
(0 jsonl each), `.claude\backups` (0 jsonl). Windsurf/Codeium, crush, `.goose`, `.fabric`:
**not installed** (no such dirs on C: or D: — receipt: full home dotdir listing + D: root listing).

## 3. Dedup & canonical set (control fact c)

Deduplication is **strictly per-file sha256**. No lineage, session-id or filename logic
anywhere — the failure mode documented in the vault note *"resumed-session merge fix (47%
of real Codex store was silently dropped)"* (two rollout files sharing one `session_id`)
is structurally impossible here: every physical file is its own manifest record keyed by
its own hash. 116,445 duplicate paths across 35,589 hashes are the expected consequence of
the vault/backup strategy (the wave-8 vault deliberately re-copies live stores).

- `dedup_index.json` — every hash with >1 path → all paths (sorted).
- `canonical_set.json` — one path per unique hash: **newest mtime wins, tie → larger size,
  tie → lexicographically smallest path** (deterministic). This is the annotation set
  (41,877 entries).

## 4. Origin classification

- `live` — under a live store root on C: (incl. `~/.codex/archived_sessions`, which is
  part of the live codex store despite the name; and `D:\basic-memory\sessions`, whose
  native home is the D: vault).
- `backup` — copy/snapshot whose original store still exists: `D:\claude-projects-archive`
  (original `~/.claude/projects` live), `D:\codex-seed-extracted` + seed tar (original
  `~/.codex/sessions` live), `D:\agent-sessions-vault` (copies of live stores).
- `orphan-backup` (23,395 files) — backups whose original no longer exists as a usable
  local store:
  - `D:\claude-history-viewer-archive` (19,769) — control fact e: the C:
    `~/.claude-history-viewer` is a stub containing only `user-data.json`; the ~9.4 GiB
    archive (lineage `GitHub-Full-backup-7-18-2026_e39521c3/sessions` and 6 sibling
    lineage dirs + `archive-manifest.json`) is the only real copy.
  - `~/Downloads/BACKUPS VM` (3,376 session files) and `vm-consolidated-2026-09-24` (12)
    — snapshots of VM-internal stores; the VM stores are not present as host folders.
  - `~/Downloads/AIs Conversations` (28) — cloud-conversation exports; no local original.
  - `~/Downloads/skills_claude_web` (210) — claude-web session exports.
  - `D:\codex-sessions-archive-20260621` — special case: **emptied while this scan was
    running** (§8); its 1,586 files are retained as `missing` records with their hashes,
    so nothing is lost to the index.

## 5. Control-source reconciliation (both directions)

Controls: **S1** `ai-sessions-render` repo (`llm_anthology/discover.py` PROVIDERS table,
`adapters/{codex_rollout,codex_state,claude_code,grok,chatgpt,claude,codex,gemini}.py`,
`.scratch/` probes); **S2** vault notes `D:\basic-memory\projects\ai-sessions-render\*.md`
(4 notes; the merge-fix note supplied facts a/b/c); **S3**
`out\harness-audit-2026-10-18\CONTROL-session-stores.md`; **S4** the task mandate (facts
d–j).

### 5a. Every store any control knows → status in this corpus

| store (control) | in corpus? | evidence |
|---|---|---|
| `~/.codex/sessions` rollout `.jsonl.zst` (S1,S2-fact-a) | ✅ 2,616 zst live + 19 archived | §2; `find` receipts |
| `~/.codex/state_5.sqlite` (S1 codex_state) | ✅ codex-root-state | §2 |
| `~/.claude/projects` (S1) | ✅ 19,351 live | §2 |
| Grok `<grok_home>/sessions/<enc-cwd>/<id>/` directory store (S1,S2-fact-b) | ✅ 505 dir records | §2 |
| ChatGPT export `conversations.json`(+`chat.html`) (S1) | ✅ ai-exports (orphan-backup) | §2 |
| Claude export `conversations.json`(+`users.json`…) (S1) | ✅ ai-exports | §2 |
| Codex task export `codex.json` (S1) | ✅ matched by name rule where present under scanned roots | file_accepts |
| Gemini Takeout `transcript.json` (S1) | ✅ ai-exports | §2 |
| `D:/claude-history-viewer-archive` (S3) | ✅ 19,769 orphan-backup | §4 |
| `D:/claude-projects-archive` (S3) | ✅ 10,014 backup | §2 |
| `~/.claude/agent-worktrees/agent-*`, `~/.claude/agent-handoff` (S3, S4-g) | ✅ 10 + 5 | §2 |
| `AppData/Local/Temp/tmp.*/sessions` (S3) | ✅ checked — **zero exist** (receipt: `ls -d …/Temp/tmp.*/sessions` → no match) | §2 |
| grok / opencode / cyberstrike / cursor / codex live+archive / zcode rollout+exec+workspace / claude projects (S3 "also verify") | ✅ all present with counts+bytes | §2 |
| `D:\agent-sessions-vault` manifest+stores+state (S4-f) | ✅ 39,716 records; vault's own `manifest.jsonl` cross-check in §6 | §6 |
| `D:\codex-sessions-archive-20260621`, `D:\codex-seed-extracted`, seed tar via `tar -t` (S4-f) | ✅ 1,586 (now missing-marked) · 1,514 · 1 tar record (2,186 members) | §2, §8 |
| ZCode `cli/exec/sess_*`, `cli/image-cache/sess_*`, v2 `db.sqlite`+`*.bak` (S4-h) | ✅ 719 · 28 · v2 2 (no `*.bak` snapshots exist on disk — `ls ~/.zcode/v2` receipt) | §2 |
| Downloads `AIs Conversations`, `BACKUPS VM`, `vm-consolidated-2026-09-24`, `skills_claude_web` (S4-i) | ✅ 28 · 3,376 · 12 · 210 | §2 |
| "Application Data" junction triad (S4-j) | ✅ never traversed: the walker skips every reparse point (`FILE_ATTRIBUTE_REPARSE_POINT` check) and no `du` was used anywhere | build_corpus.py `walk_files` |
| C: stub vs D: archive size-checking (S4-e) | ✅ every record carries real `size`; stub identified | §4 |

### 5b. Found by this scan beyond the control sources

1. `~/.claude-free` — full parallel Claude Code home, **20,040 session files (12.3 GiB)**.
   Not mentioned by S1/S2/S3. Largest single discovery.
2. `D:\basic-memory\sessions` — 43 markdown session-capture notes (the memory vault's own
   session logs). New store class (markdown); included as `storage_type=other`.
3. Claude Desktop stores (Roaming): `claude-code-sessions` (8), `local-agent-mode-sessions`
   (2), `IndexedDB`/`Local Storage` leveldb (3 directory records).
4. Cursor `acp-sessions` (4) and `globalStorage` state.vscdb 3.0 GB + `conversation-search.db`
   (S3 said "cursor chats" but not the globalStorage sqlite).
5. VS Code Copilot surfaces: `globalStorage` (3) + `workspaceStorage` (54 state.vscdb) +
   `github.copilot-chat` session jsons.
6. `~/.gemini/config/projects/*.json` — antigravity CLI session files (the
   `~/.antigravitycli` entry is a *symlink* into this dir; the walker refuses symlinks, so
   the real files are indexed at their real location).
7. `~/.cline/apps/kanban/sessions` (26), `~/.copilot/{session-state,mem0}` (2),
   `~/.continue/index` (2), `~/.local/share/opencode` (2), `~/.cyberstrike/cyberstrike.db`.
8. `~/.agents` (690 files), `~/.vscode` (923), `~/.pplx` (149), `~/.scratch` (47),
   `~/.quokka` (30) and 28 more dotdirs with a handful of session-like files each.
9. Grok desktop (`Grok Bot`) leveldb; `~/.grok` bookkeeping beyond `sessions/` was not
   separately inventoried (sessions tree is the store; `active_sessions.json` etc. are
   covered by the sweep as `other:grok`).

### 5c. Known by controls, deliberately not in the manifest (documented differences)

- S1's discovery does **not** count `~/.codex/archived_sessions`; we include it (19 files,
  runtime `codex-archived`) — a superset, not a miss.
- S1 counts Claude/ChatGPT exports anywhere on disk via sibling-confirmed
  `conversations.json`; we match them inside the scanned roots (Downloads exports root +
  generic sweeps). A `conversations.json` sitting in an arbitrary unswept folder (e.g.
  somewhere under `Documents\`) would be missed — bounded, see §9.

## 6. Cross-check vs `D:\agent-sessions-vault`

- Vault's own `manifest.jsonl` (read 2026-10-18, multiple times): **4 entries**, both
  fixture stores `fixt-a`/`fixt-b` (`manifest-summary.json` totals `total_entries: 4`).
- This corpus records **39,716 files (163.2 GiB)** under the vault — the wave-7/8 sync
  pipelines are writing `stores/<runtime>/...` far ahead of their manifest. Discrepancy
  reported in both directions: the vault manifest **under**-reports its own content; the
  corpus manifest is the fuller view. Re-run after the pipelines quiesce to reconcile.

## 7. Verification receipts (all executed this session)

- **Hashing determinism**: 10 independent re-hashes of manifest records (random seeds 42
  and 7; formats jsonl/zst/3.0GB-sqlite/json/gz) — all `MATCH`. Grok directory Merkle
  digest independently recomputed for one session (12 files) — `MATCH`.
- **Tar member count**: `tar -tf D:\codex-sessions-seed-20260315.tar | wc -l` → **2186**;
  in-manifest `members` = 2186; `jsonl_members` = 1,514. Never extracted.
- **Incremental update**: final run `hashed=10 reused=122,672 errors=0`; the run before
  `hashed=64 reused=122,618`. Size+mtime cache skip proven at 99.99% of the corpus.
- **Missing-marking**: 1,594 records `status=missing` retained with full metadata (1,586 =
  the emptied codex archive; rest vault churn) — history never dropped.
- **zst**: `python -c "import zstandard"` → `zstandard 0.25.0` (Python 3.14.6); all live
  codex rollouts hashed as compressed bytes and parsed after decompression.
- Full command log with timestamps: `scan.log` in this directory.

## 8. Concurrent mutations observed DURING the scan (read-only scan of a moving target)

| time (scan.log) | event |
|---|---|
| 06:0x (pre-scan probe) | vault = 4 fixture entries, ~31 KB |
| 07:22:57 → 08:25 | vault `stores/` grows to 36,206 files while the scan walks it |
| ~08:30 | vault at 125.9 GB |
| between run 2 (07:31) and run 4 (09:48) | `D:\codex-sessions-archive-20260621` **emptied** (1,586 files → `missing`; content absorbed by the consolidating vault) |
| 10:0x | vault at 236.1 GB, still growing |
| across runs | live stores keep growing: `.claude/projects` 19,318 → 19,351 files; new session files appear with each pass |

The corpus is therefore **timestamped and re-runnable by design** (§10); `missing` never
means deleted-by-us (read-only guarantee, §top).

## 9. Exclusions (every one deliberate, per hard rule 2)

Directory-name prunes (all roots): `node_modules .venv venv .git __pycache__ .pytest_cache
.mypy_cache .ruff_cache .ipynb_checkpoints target site-packages dist-info .hg .svn`.
Transient sqlite sidecars `-shm/-wal/-journal` are skipped (the main db is the record).
Home dotdirs pruned from the generic sweep (pure package/model/browser caches):
`.cache .cargo .rustup .gradle .m2 .conda .npm .nuget .dotnet .vscode-server
.vscode-server-insiders .android .docker .ollama .lmstudio .VirtualBox
.ScreamingFrogSEOSpider .kivy .msf4 go`. D: trees pruned from the depth-2 discovery walk
(60 names, full list in `build_corpus.py::D_PRUNE` — games/VMs/ISOs/media/package caches,
e.g. `SteamLibrary, VMware VMs, HyperV, ISOs, Media, Models, Docker, WSL, npm-cache,
micromamba, metasploit-framework`). `D:\Backups` additionally prunes
`docker-volumes/images`. Curated store roots are excluded from the sweep (no
double-count). The corpus output dir excludes itself. `~/.zcode/workspace` session-pattern
files are included but the corpus dir inside it is self-excluded. Generic `*.json`
acceptance is name-gated (`session|chat|conversation|history|rollout|transcript|dialog|
thread|completion|prompt`, `local_*`, `ses_*`, `session-*`, `meta.json`,
`conversations*.json`, `codex.json`, `transcript.json`) so random config json is not
swept in. Not scanned at all (out of declared scope): non-dotdir project folders on C:
(e.g. `Cowork\` — grok Cowork *sessions* live under `~/.grok/sessions` with percent-encoded
Cowork cwd dirs, which are included), `Documents\GitHub\*` (control repo itself), WSL/VHDX
interiors, `D:\Backups\docker-volumes`, browser-profile caches.

## 10. Keeping the corpus current

```cmd
cd C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\corpus
python build_corpus.py --update                # ~2-5 min when little changed (tar is cached too)
python build_corpus.py --update --parse-budget-gb 0   # unlimited: fills deferred parses
python build_corpus.py --roots "codex"         # touch a subset only
```

- Suggested cadence: **daily** (or after heavy session days) — the first run took ~33 min
  cold; warm re-runs are minutes (receipt §7).
- Parsing: first run used a 40 GiB decompressed budget (68,633 parsed / 51,548 deferred).
  Each `--update` re-attempts deferred files with a fresh budget, so coverage converges
  without ever re-reading unchanged files. `parse_ok=false` reasons: `deferred_budget`,
  `size_cap` (>256 MB single file), `format_not_parsed` (sqlite/other), `no_zstd`.
- `message_count` semantics: count of valid JSON-object lines (jsonl/zst/gz) or list/dict
  entries (json) — a line/record count, not a strict user-turn count; `first_ts/last_ts`
  from common timestamp fields. Directory records aggregate their conversation jsonl.
- Safety: sources are only ever read. The state cache (`.state.json`) is written with
  merged checkpoints every 5,000 records, so even a killed run loses nothing.
