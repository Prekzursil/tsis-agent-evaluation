#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_corpus.py - definitive multi-runtime agent-session corpus inventory.

READ-ONLY on all sources: this tool only os.scandir()/open()s files for hashing and
parsing. It never moves, renames, modifies or deletes anything outside its own output
directory (manifest.jsonl, dedup_index.json, canonical_set.json, stats.json, .state.json,
scan.log - all written atomically via temp file + os.replace).

Usage:
    python build_corpus.py            # first build
    python build_corpus.py --update   # incremental re-scan (default behaviour too)
    python build_corpus.py --update --parse-budget-gb 0   # unlimited parse budget

Incremental semantics:
  * a file whose size+mtime_ns are unchanged since the last run keeps its cached
    sha256 + parse results (no re-read);
  * new files are appended;
  * vanished files are marked status="missing" and NEVER dropped (history is kept);
  * output files are written atomically (tmp + os.replace).

Identity: sha256 of the file's bytes as stored (for .jsonl.zst that means the
COMPRESSED bytes, per the control fact that the live Codex store is zst; the
decompressed stream is only used to parse/count, never for identity).

Dedup is strictly per-file-hash. No file lineage is ever assumed (control fact (c):
resumed sessions once caused 47.1% of the Codex store to be dropped by naive merge
logic - that failure mode is structurally impossible here because every physical
file is its own manifest record keyed by its own hash).

Directory-shaped stores (control fact (b), Grok): one manifest record per session
DIRECTORY with storage_type="directory"; sha256 is a Merkle digest over the session
dir's files (sha256 of "<relpath>\\0<FileHash>\\0" pairs, sorted by relpath).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import hashlib
import io
import json
import os
import stat as _stat
import sys
import tarfile

try:
    import zstandard  # type: ignore

    HAVE_ZSTD = True
except Exception:  # pragma: no cover
    HAVE_ZSTD = False

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = r"C:\Users\Prekzursil"
ROAMING = HOME + r"\AppData\Roaming"
LOCALAPP = HOME + r"\AppData\Local"

MANIFEST_PATH = os.path.join(HERE, "manifest.jsonl")
STATE_PATH = os.path.join(HERE, ".state.json")
DEDUP_PATH = os.path.join(HERE, "dedup_index.json")
CANON_PATH = os.path.join(HERE, "canonical_set.json")
STATS_PATH = os.path.join(HERE, "stats.json")
LOG_PATH = os.path.join(HERE, "scan.log")

HASH_CHUNK = 4 * 1024 * 1024
SELF_EXCLUDE = HERE.lower()  # never index our own outputs
PARSE_FILE_CAP = 256 * 1024 * 1024  # per-file decompressed parse cap

# ----------------------------------------------------------------------------------
# Exclusions (EVERY one is documented in CORPUS.md)
# ----------------------------------------------------------------------------------
EXCLUDE_DIR_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
    "target",
    "site-packages",
    "dist-info",
    ".hg",
    ".svn",
    "electron-builder-cache",
}
# home dotdirs that are pure package/model/browser caches - pattern-scan pruned
HOME_SWEEP_PRUNE = {
    ".cache",
    ".cargo",
    ".rustup",
    ".gradle",
    ".m2",
    ".conda",
    ".npm",
    ".nuget",
    ".dotnet",
    ".vscode-server",
    ".vscode-server-insiders",
    ".android",
    ".docker",
    ".ollama",
    ".lmstudio",
    ".VirtualBox",
    ".ScreamingFrogSEOSpider",
    ".kivy",
    ".msf4",
    ".gradle",
    ".cargo",
    "go",
    ".cupy",
    ".paddle",
    ".tox",
}
# curated store roots (scanned explicitly) - excluded from the generic dotdir sweep
HOME_CURATED = {
    ".claude",
    ".claude-free",
    ".codex",
    ".zcode",
    ".grok",
    ".gemini",
    ".cursor",
    ".continue",
    ".cline",
    ".copilot",
    ".cyberstrike",
    ".aider",
    ".antigravitycli",
    ".local",
}
# giant/irrelevant D: trees - pruned from the D:\ depth-2 discovery walk
D_PRUNE = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "SteamLibrary",
    "VMware VMs",
    "HyperV",
    "ISOs",
    "Media",
    "Models",
    "Drivers Backup",
    "Docker",
    "Videos",
    "Program Files",
    "Program Files (x86)",
    "ProgramData",
    "android-sdk",
    "android-sdk-bilbo",
    "battle cats recordings",
    "ReverseTools",
    "schrodinger",
    "ToolUniverse",
    "WSL",
    "micromamba",
    "npm-cache",
    "uv",
    "metasploit-framework",
    "pagefile.sys",
    "opt",
    "offline",
    "Installers",
    "PhoneTransfers",
    "TOR",
    "Orange Cloud",
    "MCP",
    "Tools",
    "Research",
    "Daria_proiect",
    "bolt",
    "bolteu-github",
    "graphomaly",
    "pentagi-work",
    "qzp-cve",
    "qzp-wct",
    "sast-depth",
    "vbox-rescue",
    "vr",
    "whatsapp-reunion",
    "a54-reroot-2026-03-23",
    "browser-recovery-folder",
    "Reframe",
    "wiztree-reports",
    "root",
    "tmp",
    "out",
    "c-reclaim-work",
    "offload-staging",
    "idx-extraction",
    "ig-rotate",
    "resources",
    "verdict-archive",
    "verdict-app-repo",
    "mem0-openmemory",
    "mem0-pilot",
    "model-council",
    "ms-ng",
    "ms-reconcile",
    "completeness-bisect",
    "csp-probe-target",
    "agent-monitor",
    "ai-models",
    "knowledge",
    "pbinfo",
    "sch_install",
    "searxng",
    "Bal",
    "bal",
    # NOTE 2026-10-30: "agentchattr" removed from this prune - the wave-8
    # sessions-vault.md control flagged D:\agentchattr as wrongly pruned
    # (data/ holds agentchattr_log.jsonl + claude/codex/gemini queue jsonl);
    # it is now an explicit ROOT below.
}

# ----------------------------------------------------------------------------------
# Roots. mode: walk_patterns | walk_all | grok_dir | single | tar | leveldb_dir
# ----------------------------------------------------------------------------------
ROOTS = [
    # ---------------- C: live stores ----------------
    dict(
        path=HOME + r"\.claude\projects",
        runtime="claude-code",
        origin="live",
        mode="walk_patterns",
        note="~/.claude/projects/<slug>/*.jsonl",
    ),
    dict(
        path=HOME + r"\.claude\agent-worktrees",
        runtime="claude-agent-worktrees",
        origin="live",
        mode="walk_patterns",
        note="control (g): session-adjacent",
    ),
    dict(
        path=HOME + r"\.claude\agent-handoff",
        runtime="claude-agent-handoff",
        origin="live",
        mode="walk_all",
        note="control (g): index only",
    ),
    dict(
        path=HOME + r"\.claude\todos",
        runtime="claude-todos",
        origin="live",
        mode="walk_patterns",
        note="per-session todo state",
    ),
    dict(
        path=HOME + r"\.claude\checkpoints",
        runtime="claude-checkpoints",
        origin="live",
        mode="walk_patterns",
        note="checkpoint metadata jsonl",
    ),
    dict(
        path=HOME + r"\.claude-free",
        runtime="claude-code-free",
        origin="live",
        mode="walk_patterns",
        note="parallel Claude Code home (alt profile); 19k+ session files",
    ),
    dict(
        path=HOME + r"\.codex\sessions",
        runtime="codex",
        origin="live",
        mode="walk_patterns",
        note="rollout-*.jsonl.zst first-class",
    ),
    dict(
        path=HOME + r"\.codex\archived_sessions",
        runtime="codex-archived",
        origin="live",
        mode="walk_patterns",
        note="codex move-to archive",
    ),
    dict(
        path=HOME + r"\.codex",
        runtime="codex-root-state",
        origin="live",
        mode="walk_patterns_top",
        note="history.jsonl/session_index.jsonl/state_5.sqlite",
        top_only=True,
    ),
    dict(
        path=HOME + r"\.grok\sessions",
        runtime="grok",
        origin="live",
        mode="grok_dir",
        note="control (b): one DIRECTORY per session",
    ),
    dict(
        path=HOME + r"\.zcode\cli\rollout",
        runtime="zcode-rollout",
        origin="live",
        mode="walk_patterns",
        note="model-io-sess_*.jsonl",
    ),
    dict(
        path=HOME + r"\.zcode\cli\exec",
        runtime="zcode-exec",
        origin="live",
        mode="walk_all",
        note="control (h): sess_<id>/ exec logs (all files)",
    ),
    dict(
        path=HOME + r"\.zcode\cli\image-cache",
        runtime="zcode-image-cache",
        origin="live",
        mode="walk_all",
        note="control (h): sess_<id>/ images (all files)",
    ),
    dict(
        path=HOME + r"\.zcode\cli\db",
        runtime="zcode-cli-db",
        origin="live",
        mode="walk_patterns",
        note="db.sqlite",
    ),
    dict(
        path=HOME + r"\.zcode\v2",
        runtime="zcode-v2",
        origin="live",
        mode="walk_patterns_top",
        top_only=True,
        note="control (h): db.sqlite + *.bak snapshots (+tasks-index.sqlite)",
    ),
    dict(
        path=HOME + r"\.zcode\cli\memories",
        runtime="zcode-memories",
        origin="live",
        mode="walk_all",
        note="per-session memory state (all files)",
    ),
    dict(
        path=HOME + r"\.zcode\workspace",
        runtime="zcode-workspace",
        origin="live",
        mode="walk_patterns",
        note="control: zcode workspace; corpus out dir self-excluded",
    ),
    dict(
        path=HOME + r"\.gemini\tmp",
        runtime="gemini-cli",
        origin="live",
        mode="walk_patterns",
        note="<proj>/chats/session-*.jsonl",
    ),
    dict(
        path=HOME + r"\.cursor\chats",
        runtime="cursor-chats",
        origin="live",
        mode="walk_patterns",
        note="json + sqlite per chat",
    ),
    dict(
        path=HOME + r"\.cursor\acp-sessions",
        runtime="cursor-acp",
        origin="live",
        mode="walk_patterns",
        note="meta.json + store.db per acp session",
    ),
    dict(
        path=ROAMING + r"\Cursor\User\globalStorage",
        runtime="cursor-globalstorage",
        origin="live",
        mode="walk_patterns_top2",
        top2_only=True,
        note="state.vscdb (3GB) + conversation-search.db; file-level only (sqlite parse_ok=false)",
    ),
    dict(
        path=HOME + r"\.local\share\opencode",
        runtime="opencode",
        origin="live",
        mode="walk_patterns",
        note="storage/** + opencode.db",
    ),
    dict(
        path=HOME + r"\.cline",
        runtime="cline",
        origin="live",
        mode="walk_patterns",
        note="apps/kanban/sessions/*.jsonl, user_input_history.jsonl, dbs",
    ),
    dict(
        path=HOME + r"\.copilot\session-state",
        runtime="copilot",
        origin="live",
        mode="walk_patterns",
        note="session-state jsonl",
    ),
    dict(
        path=HOME + r"\.copilot\mem0",
        runtime="copilot-mem0",
        origin="live",
        mode="walk_patterns",
        note="mem0 sqlite",
    ),
    dict(
        path=HOME + r"\.cyberstrike",
        runtime="cyberstrike",
        origin="live",
        mode="walk_patterns",
        note="cyberstrike.db (node_modules pruned)",
    ),
    dict(
        path=HOME + r"\.antigravitycli",
        runtime="antigravity",
        origin="live",
        mode="walk_all",
        note="cli session json",
    ),
    dict(
        path=LOCALAPP + r"\antigravity",
        runtime="antigravity-local",
        origin="live",
        mode="walk_patterns",
        note="staging",
    ),
    dict(
        path=ROAMING + r"\Claude\claude-code-sessions",
        runtime="claude-desktop-code-sessions",
        origin="live",
        mode="walk_patterns",
        note="Claude Desktop embedded claude-code",
    ),
    dict(
        path=ROAMING + r"\Claude\local-agent-mode-sessions",
        runtime="claude-desktop-agent-mode",
        origin="live",
        mode="walk_patterns",
        note="Claude Desktop agent mode",
    ),
    dict(
        path=ROAMING + r"\Claude\IndexedDB",
        runtime="claude-desktop-indexeddb",
        origin="live",
        mode="leveldb_dir",
        note="claude.ai desktop chats (leveldb, other)",
    ),
    dict(
        path=ROAMING + r"\Claude\Local Storage",
        runtime="claude-desktop-localstorage",
        origin="live",
        mode="leveldb_dir",
        note="leveldb, other",
    ),
    dict(
        path=ROAMING + r"\Grok Bot",
        runtime="grok-desktop",
        origin="live",
        mode="leveldb_dir",
        note="Grok desktop app leveldb dirs",
    ),
    dict(
        path=ROAMING + r"\Code\User\globalStorage",
        runtime="vscode-globalstorage",
        origin="live",
        mode="walk_patterns_top2",
        top2_only=True,
        note="state.vscdb + copilot-cli session jsons",
    ),
    dict(
        path=ROAMING + r"\Code\User\workspaceStorage",
        runtime="vscode-workspacestorage",
        origin="live",
        mode="walk_patterns",
        note="per-workspace state.vscdb (Copilot chat)",
    ),
    dict(
        path=HOME + r"\.continue\index",
        runtime="continue-index",
        origin="live",
        mode="walk_patterns",
        note="index sqlite",
    ),
    # ---------------- Downloads backup candidates (control (i)) ----------------
    # 2026-10-30: the four control-(i) stores were re-homed since the Oct-18 run:
    #   "AIs Conversations" + skills_claude_web now sit under Downloads\AI-Conversations\,
    #   "BACKUPS VM" + vm-consolidated-2026-09-24 under Downloads\Backups\.
    # The two parent roots below cover them (old paths auto-become `missing` history).
    dict(
        path=HOME + r"\Downloads\AI-Conversations",
        runtime="ai-exports",
        origin="backup",
        orphan=True,
        mode="walk_patterns",
        note="control (i) re-homed: AIs Conversations/ + skills_claude_web/ + "
        "grok_reupload_work/ + zcode-session_*/ nested here",
    ),
    dict(
        path=HOME + r"\Downloads\Backups",
        runtime="vm-backup",
        origin="backup",
        orphan=True,
        mode="walk_patterns",
        note="control (i) re-homed: BACKUPS VM/ + vm-consolidated-2026-09-24/ + "
        "home-preff-backup-20260925/ nested here",
    ),
    # ---------------- D: stores (control (f)) ----------------
    dict(
        path=r"D:\agent-sessions-vault",
        runtime="agent-sessions-vault",
        origin="backup",
        mode="walk_patterns",
        note="wave-8 vault stores/; concurrent pipelines possible",
    ),
    dict(
        path=r"D:\claude-projects-archive",
        runtime="claude-code",
        origin="backup",
        mode="walk_patterns",
        note="control (f): ~19.5GiB archive of live store",
    ),
    dict(
        path=r"D:\claude-history-viewer-archive",
        runtime="claude-history-viewer",
        origin="backup",
        orphan=True,
        mode="walk_patterns",
        note="control (e): real archive behind the 5KB C: stub",
    ),
    dict(
        path=r"D:\codex-sessions-archive-20260621",
        runtime="codex",
        origin="backup",
        mode="walk_patterns",
        note="control (f)",
    ),
    dict(
        path=r"D:\codex-seed-extracted",
        runtime="codex",
        origin="backup",
        mode="walk_patterns",
        note="control (f)",
    ),
    dict(
        path=r"D:\codex-sessions-seed-20260315.tar",
        runtime="codex-seed-tar",
        origin="backup",
        mode="tar",
        note="control (f): listed via tar headers only, never extracted",
    ),
    dict(
        path=r"D:\Backups",
        runtime="d-backups",
        origin="backup",
        mode="walk_patterns",
        prune=("images", "docker-volumes"),
        note="docker-volumes/images pruned (documented)",
    ),
    # discovered by the generic D: walk, named by NO control source: the
    # basic-memory vault's own session-capture notes (markdown, storage_type=other).
    # origin=live: the vault's native home IS D:\basic-memory.
    dict(
        path=r"D:\basic-memory\sessions",
        runtime="basic-memory-sessions",
        origin="live",
        mode="walk_all",
        note="live vault natively on D:; markdown session captures",
    ),
    # ---------------- 2026-10-30 additions (gap stores found by re-reconnaissance) ----------------
    # sessions-vault.md (wave-8 control) flagged Cowork + agentchattr as beyond the old
    # corpus ROOTS; .gemini/antigravity-cli + .claude/history.jsonl + the Documents
    # claude-desktop backup were found missing by direct probe this session.
    dict(
        path=HOME + r"\.claude\history.jsonl",
        runtime="claude-history",
        origin="live",
        mode="walk_patterns",
        note="global claude prompt history (2.6MB jsonl)",
    ),
    dict(
        path=HOME + r"\.claude\todos",
        runtime="claude-todos",
        origin="live",
        mode="walk_all",
        note="per-session todo state (uuid-agent-*.json names are name-gated out of "
        "walk_patterns; walk_all includes them - prior CORPUS.md claimed 24 "
        "records its own manifest never had)",
    ),
    dict(
        path=HOME + r"\.claude-server-commander",
        runtime="claude-server-commander",
        origin="live",
        mode="walk_patterns",
        note="server-commander session jsons",
    ),
    dict(
        path=HOME + r"\.grok",
        runtime="grok-root",
        origin="live",
        mode="walk_patterns_top",
        top_only=True,
        note="active_sessions.json + import state at grok home top",
    ),
    dict(
        path=HOME + r"\.gemini\antigravity-cli",
        runtime="antigravity-cli",
        origin="live",
        mode="walk_all",
        note="Antigravity CLI store: conversations/*.db(.pb), history.jsonl, "
        "conversation_summaries.db, brain/ (3896 files, ~560MB)",
    ),
    dict(
        path=HOME + r"\.gemini\config\projects",
        runtime="antigravity",
        origin="live",
        mode="walk_all",
        note="antigravity CLI per-project session jsons (uuid names; uuid.json does "
        "not match the name-gated accept rule, so walk_all)",
    ),
    dict(
        path=HOME + r"\.zcode\backup",
        runtime="zcode-backup",
        origin="live",
        mode="walk_all",
        note="tasks_index/cli snapshot backups",
    ),
    dict(
        path=HOME + r"\Cowork\private",
        runtime="cowork-private",
        origin="backup",
        orphan=True,
        mode="walk_patterns",
        note="56.8GB grok Cowork area: ~20 historical state.vscdb cursor snapshots "
        "+ session-adjacent state (134 acc per wave-8 control)",
    ),
    dict(
        path=HOME + r"\Cowork\backups",
        runtime="cowork-backups",
        origin="backup",
        orphan=True,
        mode="walk_patterns",
        note="cowork backup snapshots (112 acc)",
    ),
    dict(
        path=HOME + r"\Documents\claude-desktop-backup-20260524",
        runtime="claude-desktop-backup",
        origin="backup",
        orphan=True,
        mode="walk_patterns",
        note="Claude Desktop backup 2026-05-24 (7460 files)",
    ),
    dict(
        path=r"D:\agentchattr",
        runtime="agentchattr",
        origin="live",
        mode="walk_patterns",
        note="agentchattr multi-lane bridge: data/{agentchattr_log,claude_queue,"
        "codex_queue,gemini_queue}.jsonl (was wrongly in D_PRUNE)",
    ),
    dict(
        path=r"D:\Downloads\from-C-20260818",
        runtime="from-c-backup",
        origin="backup",
        orphan=True,
        mode="walk_patterns",
        note="67GB copy of C: user data (Aug 18); contains relocated .claude trees "
        "in 'New folder (2)', 'SWFOC editor', 'swfoc_memory'",
    ),
    # the seed tar was consolidated INTO the vault (its D:\ top-level original is
    # gone); index the vault copy as an archive record (headers listed, never
    # extracted) - walk_patterns alone would skip it (storage_type=other).
    dict(
        path=r"D:\agent-sessions-vault\stores\codex-seed-tar\codex-sessions-seed-20260315.tar",
        runtime="codex-seed-tar",
        origin="backup",
        mode="tar",
        note="vault copy of the vanished D:\\codex-sessions-seed-20260315.tar",
    ),
]

TS_KEYS = (
    "timestamp",
    "ts",
    "time",
    "created_at",
    "createdAt",
    "updated_at",
    "updatedAt",
    "datetime",
    "date",
    "startTime",
    "endTime",
)
LIST_KEYS = (
    "conversations",
    "messages",
    "chats",
    "sessions",
    "history",
    "turns",
    "mapping",
    "chat_messages",
    "items",
)


def log(msg: str) -> None:
    line = "[%s] %s" % (_dt.datetime.now().isoformat(timespec="seconds"), msg)
    print(line, file=sys.stderr, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def iso(ns: float) -> str:
    return _dt.datetime.fromtimestamp(ns).isoformat(timespec="seconds")


def storage_type_of(name: str) -> str:
    n = name.lower()
    if n.endswith(".jsonl.zst"):
        return "zst"
    if n.endswith(".jsonl.gz") or n.endswith(".json.gz"):
        return "gz"
    if n.endswith(".jsonl"):
        return "jsonl"
    if n.endswith(".json"):
        return "json"
    if n.endswith((".sqlite", ".sqlite3", ".db", ".vscdb")):
        return "sqlite"
    if n.endswith((".tar", ".tar.gz", ".tgz")):
        return "other"
    return "other"


_SESSIONISH = (
    "session",
    "chat",
    "conversation",
    "history",
    "rollout",
    "transcript",
    "dialog",
    "thread",
    "completion",
    "prompt",
)


def file_accepts(relpath: str, name: str) -> bool:
    """Generic session-file matcher for walk_patterns roots."""
    n = name.lower()
    st = storage_type_of(n)
    if st in ("jsonl", "zst", "gz"):
        return True
    if st == "sqlite":
        # skip transient sqlite sidecars; the main db carries the store
        if n.endswith(("-shm", "-wal", "-journal")):
            return False
        return True
    if st == "json":
        base = os.path.basename(n)
        if base in ("conversations.json",) or base.startswith("conversations-"):
            return True
        if base in ("codex.json", "transcript.json", "updates.json", "summary.json"):
            return True
        if any(k in base for k in _SESSIONISH):
            return True
        # local_*.json (claude desktop), meta.json under acp sessions
        if base.startswith(("local_", "ses_", "session-")) or base == "meta.json":
            return True
        return False
    return False


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(HASH_CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _extract_ts(obj, out):
    if isinstance(obj, dict):
        for k in TS_KEYS:
            v = obj.get(k)
            if isinstance(v, str) and len(v) >= 8:
                out.append(v)
                break


def _norm_ts(s: str):
    t = s.strip().replace("Z", "+00:00") if s.endswith("Z") else s.strip()
    for cand in (t, t.replace("T", " ")):
        try:
            return _dt.datetime.fromisoformat(cand)
        except Exception:
            continue
    try:
        return _dt.datetime.utcfromtimestamp(float(s))
    except Exception:
        return None


def parse_jsonl_stream(fh, counter):
    """fh: binary file of decompressed text; counts dict lines, tracks ts."""
    n = 0
    tss = []
    for raw in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            n += 1
            _extract_ts(obj, tss)
    counter[0] = n
    counter[1] = tss


def parse_text(path: str, st: str, budget):
    """Returns (parse_ok, message_count, first_ts, last_ts, note, bytes_parsed)."""
    if st not in ("jsonl", "zst", "gz", "json"):
        return False, None, None, None, "format_not_parsed", 0
    size = os.path.getsize(path)
    if size > PARSE_FILE_CAP:
        return False, None, None, None, "size_cap", 0
    if budget[0] <= 0:
        return False, None, None, None, "deferred_budget", 0
    try:
        if st == "zst":
            if not HAVE_ZSTD:
                return False, None, None, None, "no_zstd", 0
            with open(path, "rb") as fh:
                dctx = zstandard.ZstdDecompressor()
                with dctx.stream_reader(fh) as r:
                    mem = io.BytesIO()
                    while True:
                        chunk = r.read(HASH_CHUNK)
                        if not chunk:
                            break
                        mem.write(chunk)
                    # budget may overshoot by at most one file (<= PARSE_FILE_CAP);
                    # every later file is deferred until budget replenishes
                    budget[0] -= mem.getbuffer().nbytes
                    mem.seek(0)
                    return _finish_parse(mem, st, size)
        elif st == "gz":
            with gzip.open(path, "rb") as fh:
                mem = io.BytesIO(fh.read())
            budget[0] -= mem.getbuffer().nbytes
            return _finish_parse(mem, st, size)
        else:
            with open(path, "rb") as fh:
                data = fh.read()
            budget[0] -= len(data)
            return _finish_parse(io.BytesIO(data), st, size)
    except Exception as e:
        return False, None, None, None, "error:%s" % type(e).__name__, 0


def _finish_parse(mem, st, size):
    counter = [0, []]
    ok = True
    note = ""
    try:
        if st == "json":
            obj = json.loads(mem.read().decode("utf-8", "replace"))
            if isinstance(obj, list):
                counter[0] = sum(1 for x in obj if isinstance(x, dict))
                for x in obj[:2000]:
                    _extract_ts(x, counter[1])
            elif isinstance(obj, dict):
                best = 0
                for k in LIST_KEYS:
                    v = obj.get(k)
                    if isinstance(v, list) and len(v) > best:
                        best = len(v)
                        counter[0] = sum(1 for x in v if isinstance(x, dict))
                        for x in v[:2000]:
                            _extract_ts(x, counter[1])
                if best == 0:
                    counter[0] = 1
                    _extract_ts(obj, counter[1])
        else:
            parse_jsonl_stream(mem, counter)
    except Exception as e:
        ok = False
        note = "error:%s" % type(e).__name__
    ts = [_norm_ts(t) for t in counter[1]]
    ts = [t for t in ts if t is not None]
    firsts = min(ts).isoformat() if ts else None
    lasts = max(ts).isoformat() if ts else None
    return ok, (counter[0] if ok else None), firsts, lasts, note, size


def walk_files(root: str, top_only=False, top2_only=False, extra_prune=()):
    """Yield (path, rel). READ-ONLY scandir walk honouring exclusions."""
    if os.path.isfile(root):
        yield root, os.path.basename(root)
        return
    depth_cap = 0 if top_only else (1 if top2_only else None)

    def rec(dirpath, relbase, depth):
        try:
            with os.scandir(dirpath) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as e:
            log("  scandir-error %s: %s" % (dirpath, e))
            return
        for entry in entries:
            name = entry.name
            rel = os.path.join(relbase, name) if relbase else name
            if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                # junction check: st_reparse_tag; never traverse reparse points
                try:
                    mode = entry.stat(follow_symlinks=False).st_mode
                except OSError:
                    continue
                if mode & _stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    continue
                if name in EXCLUDE_DIR_NAMES or name in extra_prune:
                    continue
                if SELF_EXCLUDE and entry.path.lower().startswith(SELF_EXCLUDE + os.sep.lower()):
                    continue
                if depth_cap is not None and depth >= depth_cap:
                    continue
                yield from rec(entry.path, rel, depth + 1)
            elif entry.is_file(follow_symlinks=False):
                if SELF_EXCLUDE and entry.path.lower().startswith(SELF_EXCLUDE + os.sep.lower()):
                    continue
                yield entry.path, rel

    yield from rec(root, "", 0)


def classify_origin(path: str, root_origin: str, markers_enabled: bool = False) -> str:
    """Curated roots carry their configured origin verbatim (e.g. ~/.codex/
    archived_sessions is LIVE - codex moves finished sessions there). Only the
    generic sweeps (arbitrary dotdirs on C:/D:) demote backup-named paths."""
    if root_origin == "live" and markers_enabled:
        p = path.lower()
        for marker in ("backup", "-bak", ".bak", "archive", "swap-backup"):
            if marker in p:
                return "backup"
        return "live"
    return root_origin


def grok_sessions(root: str):
    """Yield session directory paths (depth 2: <enc-cwd>/<session-id>)."""
    try:
        cwds = [e.path for e in os.scandir(root) if e.is_dir(follow_symlinks=False)]
    except OSError:
        return []
    out = []
    for c in cwds:
        try:
            for e in os.scandir(c):
                if e.is_dir(follow_symlinks=False) and e.name != "subagents":
                    out.append(e.path)
        except OSError:
            pass
    return out


def grok_dir_fingerprint(sess_dir: str):
    """Stat-only (file_count, total_size, newest_mtime_ns) for a session dir.
    Returns None if any entry cannot be stat'ed (forces a full re-hash)."""
    n = 0
    total = 0
    newest = 0
    try:
        for p, rel in walk_files(sess_dir):
            st = os.stat(p)
            n += 1
            total += st.st_size
            if st.st_mtime > newest:
                newest = st.st_mtime
    except OSError:
        return None
    return (n, total, int(newest * 1e9))


def grok_dir_record(sess_dir: str, budget):
    files = []
    for p, rel in walk_files(sess_dir):
        try:
            st = os.stat(p)
        except OSError:
            continue
        files.append((rel, p, st))
    files.sort(key=lambda x: x[0].lower())
    h = hashlib.sha256()
    total = 0
    newest = 0
    for rel, p, st in files:
        fh = hashlib.sha256()
        try:
            with open(p, "rb") as f:
                while True:
                    b = f.read(HASH_CHUNK)
                    if not b:
                        break
                    fh.update(b)
        except OSError:
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(fh.hexdigest().encode("ascii"))
        h.update(b"\x00")
        total += st.st_size
        newest = max(newest, st.st_mtime)
    msg = 0
    tss = []
    for rel, p, st in files:
        base = os.path.basename(p).lower()
        if base in ("updates.jsonl", "chat_history.jsonl", "events.jsonl"):
            ok, m, f1, l1, note, _ = parse_text(p, "jsonl", budget)
            if ok and m:
                msg += m
                for t in (f1, l1):
                    if t:
                        tss.append(t)
    ts = sorted(tss)
    return dict(
        sha256=h.hexdigest(),
        size=total,
        mtime_ns=int(newest * 1e9),
        message_count=(msg or None),
        first_ts=(ts[0] if ts else None),
        last_ts=(ts[-1] if ts else None),
        file_count=len(files),
    )


def tar_record(path: str, budget):
    members = 0
    jsonl_members = 0
    try:
        with tarfile.open(path, "r|") as tf:  # streaming: reads headers, skips data
            for m in tf:
                members += 1
                if m.name.endswith((".jsonl", ".jsonl.zst", ".json")):
                    jsonl_members += 1
    except Exception as e:
        log("  tar-list-error %s: %s" % (path, e))
        members = None
    sha = hash_file(path)
    st = os.stat(path)
    return dict(
        sha256=sha,
        size=st.st_size,
        mtime_ns=st.st_mtime_ns,
        members=members,
        jsonl_members=jsonl_members,
    )


def leveldb_dirs(root: str):
    """Yield leveldb directory paths ( contain *.ldb/log files ) under root, depth<=2."""
    out = []
    try:
        for e in os.scandir(root):
            if not e.is_dir(follow_symlinks=False):
                continue
            try:
                names = [x.name.lower() for x in os.scandir(e.path)]
            except OSError:
                continue
            if any(n.endswith((".ldb", ".log", ".sst")) for n in names):
                out.append(e.path)
            else:
                for sub in names:
                    sp = os.path.join(e.path, sub)
                    if os.path.isdir(sp):
                        try:
                            subnames = [x.name.lower() for x in os.scandir(sp)]
                        except OSError:
                            continue
                        if any(n.endswith((".ldb", ".log", ".sst")) for n in subnames):
                            out.append(sp)
    except OSError:
        pass
    return out


def dir_record(dpath: str):
    """Aggregate record for a leveldb/other directory-shaped store."""
    files = []
    for p, rel in walk_files(dpath):
        try:
            st = os.stat(p)
        except OSError:
            continue
        files.append((rel, st))
    files.sort(key=lambda x: x[0].lower())
    h = hashlib.sha256()
    total = 0
    newest = 0
    for rel, st in files:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(("%d" % st.st_size).encode("ascii"))
        h.update(b"\x00")
        total += st.st_size
        newest = max(newest, st.st_mtime)
    return dict(sha256=h.hexdigest(), size=total, mtime_ns=int(newest * 1e9), file_count=len(files))


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            log("state unreadable, starting fresh")
    return {}


def atomic_write(path: str, data: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", default=True)
    ap.add_argument(
        "--parse-budget-gb",
        type=float,
        default=40.0,
        help="decompressed-byte budget for parsing this run; 0 = unlimited",
    )
    ap.add_argument("--roots", default="", help="comma-separated substring filter of root paths")
    args = ap.parse_args()

    budget_gb = args.parse_budget_gb
    budget = [float("inf")] if budget_gb == 0 else [budget_gb * 1e9]
    state = load_state()
    log("scan start; zstandard=%s; parse budget=%s GB" % (HAVE_ZSTD, budget_gb))

    filt = [s.strip().lower() for s in args.roots.split(",") if s.strip()]

    new_state = {}
    counts = dict(files=0, hashed=0, reused=0, missing=0, errors=0)
    per_runtime = {}
    discovery = []

    def register(rec):
        path = rec["path"]
        key = path
        prev = state.get(key)
        if (
            prev
            and prev.get("size") == rec.get("size")
            and prev.get("mtime_ns") == rec.get("mtime_ns")
            and prev.get("sha256")
        ):
            # reuse cached parse results too (same bytes)
            merged = dict(prev)
            merged["status"] = "ok"
            merged["drive"] = rec["drive"]
            merged["runtime"] = rec["runtime"]
            merged["origin"] = rec["origin"]
            merged["storage_type"] = rec["storage_type"]
            counts["reused"] += 1
        else:
            merged = rec
            counts["hashed"] += 1
        new_state[key] = merged
        counts["files"] += 1
        if counts["files"] % 5000 == 0:
            try:
                merged_state = dict(state)  # entries not yet re-visited this run
                merged_state.update(new_state)
                with open(STATE_PATH + ".tmp", "w", encoding="utf-8") as fh:
                    json.dump(merged_state, fh)
                os.replace(STATE_PATH + ".tmp", STATE_PATH)
                log("  checkpoint: %d records" % counts["files"])
            except Exception as e:
                log("  checkpoint-error: %r" % e)
        return merged

    def base_rec(path, runtime, origin, stype, stt, markers=False):
        return dict(
            path=path,
            drive=os.path.splitdrive(path)[0],
            runtime=runtime,
            origin=classify_origin(path, origin, markers),
            storage_type=stype,
            size=stt.st_size,
            mtime_ns=stt.st_mtime_ns,
            mtime=iso(stt.st_mtime),
            sha256=None,
            parse_ok=False,
            message_count=None,
            first_ts=None,
            last_ts=None,
            status="ok",
        )

    for root in ROOTS:
        rp = root["path"]
        if filt and not any(f in rp.lower() for f in filt):
            continue
        if not os.path.exists(rp):
            discovery.append(dict(root=rp, status="absent"))
            log("root absent: %s" % rp)
            continue
        mode = root["mode"]
        log("scanning %s (%s/%s)" % (rp, root["runtime"], mode))
        n_before = counts["files"]
        try:
            if mode == "tar":
                prev = state.get(rp)
                try:
                    _st = os.stat(rp)
                except OSError:
                    _st = None
                if (
                    prev
                    and _st
                    and prev.get("size") == _st.st_size
                    and prev.get("mtime_ns") == _st.st_mtime_ns
                    and prev.get("sha256")
                    and prev.get("members") is not None
                ):
                    info = dict(
                        size=prev["size"],
                        mtime_ns=prev["mtime_ns"],
                        sha256=prev["sha256"],
                        members=prev.get("members"),
                        jsonl_members=prev.get("jsonl_members"),
                    )
                else:
                    info = tar_record(rp, budget)
                fake = type(
                    "S",
                    (),
                    {
                        "st_size": info["size"],
                        "st_mtime_ns": info["mtime_ns"],
                        "st_mtime": info["mtime_ns"] / 1e9,
                    },
                )()
                rec = base_rec(rp, root["runtime"], root["origin"], "other", fake)
                rec.update(
                    sha256=info["sha256"],
                    members=info["members"],
                    jsonl_members=info["jsonl_members"],
                    parse_note="tar; members listed only, never extracted",
                )
                register(rec)
            elif mode == "grok_dir":
                for sd in sorted(grok_sessions(rp)):
                    # 2026-10-30 incremental fix: cheap stat-only fingerprint of the
                    # session dir (file_count, total size, newest mtime_ns); reuse the
                    # cached merkle sha256 when unchanged, so warm runs do not re-hash
                    # the whole ~4GiB grok store. Same size+mtime skip rule as files.
                    fp = grok_dir_fingerprint(sd)
                    prev = state.get(sd)
                    if (
                        prev
                        and fp
                        and prev.get("sha256")
                        and prev.get("file_count") == fp[0]
                        and prev.get("size") == fp[1]
                        and prev.get("mtime_ns") == fp[2]
                    ):
                        info = dict(
                            size=prev["size"],
                            mtime_ns=prev["mtime_ns"],
                            sha256=prev["sha256"],
                            message_count=prev.get("message_count"),
                            first_ts=prev.get("first_ts"),
                            last_ts=prev.get("last_ts"),
                            file_count=prev["file_count"],
                        )
                    else:
                        info = grok_dir_record(sd, budget)
                    rec = dict(
                        path=sd,
                        drive=os.path.splitdrive(sd)[0],
                        runtime=root["runtime"],
                        origin="live",
                        storage_type="directory",
                        size=info["size"],
                        mtime_ns=info["mtime_ns"],
                        mtime=iso(info["mtime_ns"] / 1e9),
                        sha256=info["sha256"],
                        parse_ok=True,
                        message_count=info["message_count"],
                        first_ts=info["first_ts"],
                        last_ts=info["last_ts"],
                        status="ok",
                        file_count=info["file_count"],
                        parse_note="merkle over session dir files",
                    )
                    register(rec)
            elif mode == "leveldb_dir":
                for ld in leveldb_dirs(rp):
                    info = dir_record(ld)
                    rec = dict(
                        path=ld,
                        drive=os.path.splitdrive(ld)[0],
                        runtime=root["runtime"],
                        origin="live",
                        storage_type="directory",
                        size=info["size"],
                        mtime_ns=info["mtime_ns"],
                        mtime=iso(info["mtime_ns"] / 1e9),
                        sha256=info["sha256"],
                        parse_ok=False,
                        status="ok",
                        file_count=info["file_count"],
                        parse_note="leveldb; file-level inventory only",
                    )
                    register(rec)
            else:
                top_only = bool(root.get("top_only"))
                top2 = bool(root.get("top2_only"))
                extra_prune = tuple(root.get("prune", ()))
                for p, rel in walk_files(
                    rp, top_only=top_only, top2_only=top2, extra_prune=extra_prune
                ):
                    name = os.path.basename(p)
                    if mode in ("walk_all",):
                        acc = True
                    else:
                        acc = file_accepts(rel, name)
                    if not acc:
                        continue
                    try:
                        stt = os.stat(p)
                    except OSError as e:
                        counts["errors"] += 1
                        log("  stat-error %s: %s" % (p, e))
                        continue
                    if stt.st_size == 0 and storage_type_of(name) not in (
                        "jsonl",
                        "json",
                        "zst",
                        "gz",
                    ):
                        pass  # still record empty files; they exist
                    stype = storage_type_of(name)
                    if mode == "walk_all":
                        stype = storage_type_of(name)
                    rec = base_rec(p, root["runtime"], root["origin"], stype, stt)
                    prev = state.get(p)
                    if (
                        prev
                        and prev.get("size") == stt.st_size
                        and prev.get("mtime_ns") == stt.st_mtime_ns
                        and prev.get("sha256")
                    ):
                        rec["sha256"] = prev["sha256"]
                        for k in (
                            "parse_ok",
                            "message_count",
                            "first_ts",
                            "last_ts",
                            "parse_note",
                            "file_count",
                            "members",
                        ):
                            if k in prev:
                                rec[k] = prev[k]
                    else:
                        try:
                            rec["sha256"] = hash_file(p)
                        except OSError as e:
                            counts["errors"] += 1
                            log("  hash-error %s: %s" % (p, e))
                            continue
                        ok, m, f1, l1, note, _ = parse_text(p, stype, budget)
                        rec["parse_ok"] = ok
                        rec["message_count"] = m
                        rec["first_ts"] = f1
                        rec["last_ts"] = l1
                        if note:
                            rec["parse_note"] = note
                    register(rec)
        except Exception as e:
            counts["errors"] += 1
            log("root-error %s: %r" % (rp, e))
        discovery.append(
            dict(
                root=rp, mode=mode, runtime=root["runtime"], files_added=counts["files"] - n_before
            )
        )

    # ---------------- generic dotdir sweep (home) ----------------
    if not filt:
        log("generic home dotdir sweep")
        try:
            dotdirs = [
                e.name
                for e in os.scandir(HOME)
                if e.is_dir(follow_symlinks=False) and e.name.startswith(".")
            ]
        except OSError:
            dotdirs = []
        root_paths = [r["path"].lower() for r in ROOTS]
        for name in sorted(dotdirs):
            if name in HOME_CURATED or name in HOME_SWEEP_PRUNE:
                continue
            p = os.path.join(HOME, name)
            pl = p.lower()
            if any(rp == pl or rp.startswith(pl + os.sep) for rp in root_paths):
                continue  # subtree covered by an explicit root
            n_before = counts["files"]
            for fp, rel in walk_files(p):
                if not file_accepts(rel, os.path.basename(fp)):
                    continue
                try:
                    stt = os.stat(fp)
                except OSError:
                    continue
                stype = storage_type_of(os.path.basename(fp))
                rec = base_rec(fp, "other:" + name.lstrip("."), "live", stype, stt, markers=True)
                prev = state.get(fp)
                if (
                    prev
                    and prev.get("size") == stt.st_size
                    and prev.get("mtime_ns") == stt.st_mtime_ns
                    and prev.get("sha256")
                ):
                    rec["sha256"] = prev["sha256"]
                    for k in ("parse_ok", "message_count", "first_ts", "last_ts", "parse_note"):
                        if k in prev:
                            rec[k] = prev[k]
                else:
                    try:
                        rec["sha256"] = hash_file(fp)
                    except OSError:
                        continue
                    ok, m, f1, l1, note, _ = parse_text(fp, stype, budget)
                    rec.update(parse_ok=ok, message_count=m, first_ts=f1, last_ts=l1)
                    if note:
                        rec["parse_note"] = note
                register(rec)
            if counts["files"] > n_before:
                discovery.append(
                    dict(
                        root=p,
                        mode="dotdir_sweep",
                        runtime="other:" + name.lstrip("."),
                        files_added=counts["files"] - n_before,
                    )
                )

        # ---------------- generic D: depth-2 discovery ----------------
        log("generic D: depth-2 discovery walk")
        markers = {
            ".claude",
            ".codex",
            ".zcode",
            ".grok",
            ".gemini",
            ".cursor",
            ".opencode",
            ".goose",
            ".aider",
            ".continue",
            ".cline",
            ".copilot",
            ".cyberstrike",
            "rollout",
            "sessions",
        }
        hits = []
        try:
            level1 = [e for e in os.scandir("D:\\") if e.is_dir(follow_symlinks=False)]
        except OSError:
            level1 = []
        for e1 in sorted(level1, key=lambda x: x.name):
            if e1.name in D_PRUNE or e1.name in EXCLUDE_DIR_NAMES:
                continue
            if e1.name.lower() in markers:
                hits.append(e1.path)
                continue
            try:
                for e2 in os.scandir(e1.path):
                    if not e2.is_dir(follow_symlinks=False):
                        continue
                    if e2.name in EXCLUDE_DIR_NAMES:
                        continue
                    if e2.name.lower() in markers:
                        hits.append(e2.path)
            except OSError:
                pass
        for hpath in hits:
            # skip discovery hits inside roots already scanned explicitly
            # (e.g. D:\codex-seed-extracted\sessions under D:\codex-seed-extracted)
            if any(
                hpath.lower().startswith(r["path"].lower() + os.sep)
                or hpath.lower() == r["path"].lower()
                for r in ROOTS
            ):
                discovery.append(
                    dict(root=hpath, mode="d_discovery", status="already-scanned-root")
                )
                continue
            n_before = counts["files"]
            for fp, rel in walk_files(hpath):
                if not file_accepts(rel, os.path.basename(fp)):
                    continue
                try:
                    stt = os.stat(fp)
                except OSError:
                    continue
                stype = storage_type_of(os.path.basename(fp))
                rec = base_rec(
                    fp, "d-discovery:" + os.path.basename(hpath), "backup", stype, stt, markers=True
                )
                prev = state.get(fp)
                if (
                    prev
                    and prev.get("size") == stt.st_size
                    and prev.get("mtime_ns") == stt.st_mtime_ns
                    and prev.get("sha256")
                ):
                    rec["sha256"] = prev["sha256"]
                    for k in ("parse_ok", "message_count", "first_ts", "last_ts", "parse_note"):
                        if k in prev:
                            rec[k] = prev[k]
                else:
                    try:
                        rec["sha256"] = hash_file(fp)
                    except OSError:
                        continue
                    ok, m, f1, l1, note, _ = parse_text(fp, stype, budget)
                    rec.update(parse_ok=ok, message_count=m, first_ts=f1, last_ts=l1)
                    if note:
                        rec["parse_note"] = note
                register(rec)
            discovery.append(
                dict(root=hpath, mode="d_discovery", files_added=counts["files"] - n_before)
            )
        log("D: discovery hits: %s" % (hits,))

    # ---------------- vanished files ----------------
    for path, prev in state.items():
        if path in new_state:
            continue
        if not os.path.exists(path):
            gone = dict(prev)
            gone["status"] = "missing"
            new_state[path] = gone
            counts["missing"] += 1
        else:
            # exists but filtered out this run (--roots): keep history untouched
            new_state[path] = prev

    # ---------------- write outputs ----------------
    ordered = sorted(new_state.values(), key=lambda r: r["path"].lower())

    # orphan-backup reclassification: backup roots with no surviving original
    # (C: counterpart is a stub, or the content came from VM/cloud snapshots)
    orphan_roots = tuple((r["path"].lower(),) for r in ROOTS if r.get("orphan"))
    for rec in ordered:
        if rec.get("origin") == "backup" and rec.get("status") == "ok":
            pl = rec["path"].lower()
            for (orp,) in orphan_roots:
                if pl.startswith(orp + os.sep):
                    rec["origin"] = "orphan-backup"
                    break

    # per-runtime rollup computed from the FULL record set (never a filtered view)
    per_runtime = {}
    for r in ordered:
        if r.get("status") != "ok":
            continue
        d = per_runtime.setdefault(r["runtime"], dict(files=0, bytes=0, parsed=0, by_origin={}))
        d["files"] += 1
        d["bytes"] += r.get("size") or 0
        if r.get("parse_ok"):
            d["parsed"] += 1
        d["by_origin"][r["origin"]] = d["by_origin"].get(r["origin"], 0) + 1

    with open(MANIFEST_PATH + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        for rec in ordered:
            out = {
                k: rec.get(k)
                for k in (
                    "path",
                    "drive",
                    "runtime",
                    "origin",
                    "storage_type",
                    "size",
                    "mtime",
                    "sha256",
                    "parse_ok",
                    "message_count",
                    "first_ts",
                    "last_ts",
                    "status",
                    "parse_note",
                    "file_count",
                    "members",
                    "jsonl_members",
                )
            }
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")
    os.replace(MANIFEST_PATH + ".tmp", MANIFEST_PATH)

    # dedup + canonical over ok-status records with a sha256
    by_hash = {}
    for rec in ordered:
        if rec.get("status") != "ok" or not rec.get("sha256"):
            continue
        by_hash.setdefault(rec["sha256"], []).append(rec)
    dup_index = {}
    canonical = []
    for sha, recs in by_hash.items():
        if len(recs) > 1:
            dup_index[sha] = [r["path"] for r in sorted(recs, key=lambda r: r["path"].lower())]
        canon = sorted(
            recs,
            key=lambda r: (-(r.get("mtime_ns") or 0), -(r.get("size") or 0), r["path"].lower()),
        )[0]
        canonical.append(
            dict(
                sha256=sha,
                path=canon["path"],
                runtime=canon["runtime"],
                origin=canon["origin"],
                storage_type=canon["storage_type"],
                size=canon.get("size") or 0,
            )
        )
    canonical.sort(key=lambda r: r["path"].lower())

    ok_recs = [r for r in ordered if r.get("status") == "ok"]
    atomic_write(
        DEDUP_PATH,
        json.dumps(
            dict(
                generated=_dt.datetime.now().isoformat(timespec="seconds"),
                duplicate_hashes=len(dup_index),
                duplicate_files=sum(len(v) for v in dup_index.values()),
                groups=dup_index,
            ),
            indent=1,
        ),
    )
    atomic_write(
        CANON_PATH,
        json.dumps(
            dict(
                generated=_dt.datetime.now().isoformat(timespec="seconds"),
                unique_files=len(canonical),
                annotation_set=canonical,
            ),
            indent=1,
        ),
    )

    by_drive = {}
    by_stype = {}
    by_origin = {}
    for r in ok_recs:
        by_drive[r["drive"]] = by_drive.get(r["drive"], 0) + 1
        by_stype[r["storage_type"]] = by_stype.get(r["storage_type"], 0) + 1
        by_origin[r["origin"]] = by_origin.get(r["origin"], 0) + 1
    parsed = sum(1 for r in ok_recs if r.get("parse_ok"))
    msgs = sum(r.get("message_count") or 0 for r in ok_recs)

    # orphan analysis: backup records whose runtime has no live record
    live_runtimes = {r["runtime"] for r in ok_recs if r["origin"] == "live"}
    orphan_roots = []
    for r in ok_recs:
        if r["origin"] in ("backup", "orphan-backup") and r["runtime"] not in live_runtimes:
            orphan_roots.append(r["runtime"])
    orphans = sorted(set(orphan_roots))

    stats = dict(
        generated=_dt.datetime.now().isoformat(timespec="seconds"),
        totals=dict(
            records=len(ordered),
            ok=len(ok_recs),
            missing=counts["missing"],
            unique=len(canonical),
            duplicates=sum(len(v) for v in dup_index.values()),
            duplicate_hashes=len(dup_index),
            parsed=parsed,
            parse_deferred=sum(1 for r in ok_recs if r.get("parse_note") == "deferred_budget"),
            total_bytes=sum(r.get("size") or 0 for r in ok_recs),
            total_messages=msgs,
        ),
        counts=counts,
        by_drive=by_drive,
        by_storage_type=by_stype,
        by_origin=by_origin,
        per_runtime=per_runtime,
        discovery=discovery,
        orphan_backup_runtimes=orphans,
        parse_budget_gb=budget_gb,
        zstandard=HAVE_ZSTD,
    )
    atomic_write(STATS_PATH, json.dumps(stats, indent=1))

    with open(STATE_PATH + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(new_state, fh)
    os.replace(STATE_PATH + ".tmp", STATE_PATH)

    log(
        "scan done: %d records (%d ok, %d missing), %d unique hashes, "
        "%d dup files; hashed=%d reused=%d errors=%d parsed=%d"
        % (
            len(ordered),
            len(ok_recs),
            counts["missing"],
            len(canonical),
            sum(len(v) for v in dup_index.values()),
            counts["hashed"],
            counts["reused"],
            counts["errors"],
            parsed,
        )
    )
    print(json.dumps(stats["totals"], indent=1))


if __name__ == "__main__":
    main()
