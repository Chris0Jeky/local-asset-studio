# P35 qualification implementation plan

**Goal:** make multi-reference consistency measurable without turning proxy scores into owner decisions.

**Architecture:** a deterministic Python qualification package and declarative route bundle; an explicit loopback adapter uses existing Studio Production ownership. The pinned production app and catalog remain unchanged.

**Tech stack:** Python 3.12+ standard library; JSON; native ComfyUI API graphs as data; Windows `py -3` launcher. No compiler, GPU or added model dependency for offline evidence.

**Spec:** `DESIGN.md`; owner brief P35-B-20261125-1; pinned `docs/PRODUCT_DIRECTION.md` Priority 1.

## Global constraints

- Source/tests/docs/compact evidence only in this prototype directory; report in the matching research directory.
- UTF-8, LF; each committed file under 300 KB, combined contribution under 3 MB, at most two images (none planned).
- Four current native routes, twenty cases across ten families, three fixed seeds. Missing/unsupported cells remain visible.
- All new output claims planned. No generation, human review, owner acceptance or licence state inferred.
- GitHub connector writes only to `pro/P35-B-20261125-1`; no merge. At most ten files per commit.

## Tasks

- [x] Read pinned contracts; create branch, restart record and draft PR #2047.
- [ ] Implement owner-calibrated scoring, reference-role conflict analysis and suite validation. Write adversarial tests before implementation; include false agreement, leakage, non-finite scores and missing-denominator cases.
- [ ] Build source-pinned route graphs/presets and offline plan compiler. Test ordering, binding, unsupported reference refusal, deterministic plans and default bounded smoke profile.
- [ ] Build explicit prepare/start/status adapter and launcher. Test against fake local HTTP with response loss, concurrent launch, backend mismatch and repeated invocation; never use a live generation endpoint here.
- [ ] Run one-command reproducible offline evidence; verify compact output hashes. Perform independent whole-package review and fix concrete failures.
- [ ] Write research, provenance/terms and ADOPTION handoff; check every named branch file and applicable hosted repository checks; finalize RUN_STATE and mark PR ready.

## Shared interfaces

Suite owns pose families, case IDs, routes, seeds and immutable trial identities. Route bundle maps its route IDs to source preset IDs, graphs, roles and controls. Plan compiler consumes the suite plus explicit owner references; owner runner consumes only a frozen `p35-owner-run/v1` plan. The runner creates no roles, recipes or alternate queues.

## Review focus

Owner mark attribution; missing/unsupported trials; wrong source order or source bytes; uncertain HTTP dispatch; mismatched graph/runtime/model claims. Each belongs to its component's adversarial tests and the independent review.

## Execution record

The owner authorized autonomous implementation and parallel agents. Root is the only repository writer; delegated drafts are built in separate scratch directories and integrated after review. The user-specified connector branch/checkpoint workflow takes precedence over generic local-worktree/branch naming instructions. No repository clone or raw GitHub network access is used.
