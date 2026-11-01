# TSIS Agent Evaluation — Multi-Model Benchmark + Failure Taxonomy Study

![tsis-ci](https://github.com/Prekzursil/tsis-agent-evaluation/actions/workflows/ci.yml/badge.svg) ![quality](https://github.com/Prekzursil/tsis-agent-evaluation/actions/workflows/quality.yml/badge.svg) ![CodeQL](https://github.com/Prekzursil/tsis-agent-evaluation/actions/workflows/codeql.yml/badge.svg)

Course project for **TSIS (Topici Speciale în Inginerie Software)**, FMI Master IS, 2026-2027.

## Three evaluation lanes, one decision

| Lane | Paper | Verdict | Key result |
|------|-------|---------|-----------|
| **τ²-bench** (winner) | [arXiv:2506.07982](https://arxiv.org/abs/2506.07982) | **GO** | 2,852-sim grok-4.7 + 2,344-sim GLM-5.3 full-domain sweep; custom 14-task e-commerce domain (mean 0.786); upstream docs errata filed as [issue #635](https://github.com/sierra-research/tau2-bench/issues/635) |
| MASTscope (supporting) | [arXiv:2503.13657](https://arxiv.org/abs/2503.13657) | NO-GO (solo) | 33,889-session MAST-14 annotation (100% of dedup corpus); AdaMAST self-rejected (κ=0.315) |
| TRAIL (supporting) | [arXiv:2505.08638](https://arxiv.org/abs/2505.08638) | NO-GO (solo) | 148/148 gold-set agreement (wF1 0.368); 7,011-session corpus annotation; sensitivity verdict at full N (2026-11-01): **STILL UNSTABLE** — 5/5 top-5 class + 3/3 impact shares outside the full-N bootstrap CI (`trail/fullrun/sensitivity.md`) |

## Key artifacts

- **`DECISION.md`** — council verdict, 14-week plan, conditions, xlsx-ready registration lines
- **`corpus/CROSS_TAXONOMY.md`** — MAST-14 × TRAIL-20 cross-taxonomy study (unpublished; both-flag 60.3%, Resource-Abuse 1.5× above independence)
- **`mastscope/fullrun/adamast_comparison.md`** — AdaMAST vs fixed MAST-14 (Jaccard 0.150; AdaMAST's own agreement gate rejected its induced taxonomy)
- **`tau2-bench/UPSTREAM_DOCS_ERRATA.md`** + `ISSUE_DRAFT.md` — documentation errors found and filed upstream
- **`INTEGRITY.md`** — zero-corruption audit of all 124,327 corpus records
- Per-lane `RESULTS.md` + `research-sota.md` — full-scale results, SOTA dossiers

## Corpus

124,327 session files across both drives (C:+D:), 41,877 unique content hashes, ~45 runtimes (Claude, Codex, ZCode, Gemini, Grok, Cursor, OpenCode, Antigravity, etc.), deduplicated by sha256, zero-loss (sources untouched).

## Tooling

Each lane has verify scripts (`verify*.py`) that validate results offline. The corpus builder (`corpus/build_corpus.py`) is incremental and re-runnable.
