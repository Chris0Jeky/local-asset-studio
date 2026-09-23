# Design-agent asset handoff contract

Status: proposed consumer contract, 2026-09-23. Documentation only. No endpoint, queue, database, model route or automatic generation is introduced.

## Ownership and existing decisions

Design research belongs to [agent-hq D3 #17](https://github.com/Chris0Jeky/agent-hq/issues/17), advanced by [playbook PR #20](https://github.com/Chris0Jeky/agent-hq/pull/20). Runnable orchestration belongs to [claude-config design-frontend #320](https://github.com/Chris0Jeky/claude-config/pull/320). Evidence/judge semantics belong to [agent-harness #289](https://github.com/Chris0Jeky/agent-harness/pull/289). LAS owns asset records, reviewed generation, lineage and reuse.

This contract consumes the proposed playbook, not the unavailable September 22 brief itself. Its original machine-local source still needs reconciliation in agent-hq; no research SoT moves here.

Existing [#313](https://github.com/Chris0Jeky/local-asset-studio/issues/313) requires intent → reviewed setup → generation → review → repair/variation → explicit owner acceptance → reuse with lineage. It expressly excludes another generic critic, queue, asset database or executor. Existing Workspace/reference/production mechanisms remain the implementation owners. [#772](https://github.com/Chris0Jeky/local-asset-studio/issues/772) remains the product journey QA tracker; this is not a competing backlog.

Successful generation, art acceptance and rights clearance are separate states. The open fantasy-pack review in `HUMAN_TODO.md` remains an owner decision. This document neither accepts candidates nor changes that record.

## Proposed request envelope

These are proposed semantic fields, not an implemented API schema. A future adapter must map them to existing LAS records rather than accept arbitrary paths or commands.

| Field group | Required meaning |
|---|---|
| Identity | Contract version, request ID, consumer repository and exact revision, named surface and asset slot/role. Reusing an ID does not authorize repeating an uncertain submission. |
| Direction | Reviewed style-pack identity/revision, allowed reference asset IDs and their intended roles, explicit constraints and counterexamples. Missing style approval stays visible. |
| Fit | Aspect ratio, dimensions, crop/safe area, variants, permitted formats, byte budget, editable-source requirement and accessibility intent. Decorative versus informative is an explicit choice. |
| Rights and use | Intended use, territory/context constraints where applicable, provenance requirements and allowed transformations. Unknown rights is a recorded gap, not assumed clearance. |
| Retrieval | Prefer existing accepted assets; record candidate IDs and concrete reasons for rejecting each before proposing generation. A retrieval miss is a valid outcome. |
| Authorization | Generation allowed defaults to false; explicit attempt/time/resource ceilings and any paid-call allowance. Missing permission or required limits means do not generate or bill. |

A request expresses demand. It does not grant access to the consumer repository, a filesystem directory, a provider account, a network host or installed ComfyUI. User/tool authorization and LAS admission remain separate.

## Proposed response envelope

Return one of `retrieved`, `generation_proposed`, `generated_unaccepted`, `refused`, or `unavailable`, with a reason and unresolved requirements. Keep these orthogonal records separate:

- **Asset identity:** existing LAS asset ID/revision, exact content digest, original/editable source reference and variant/derivative relationships. A digest binds bytes, not creator identity or license authenticity.
- **Production evidence:** existing job/prompt ID, exact recipe/graph/model/runtime references, attempts and known outcome. Preserve failed/rejected/uncertain work. Unknown completion must never trigger blind resubmission.
- **Acceptance evidence:** who accepted which exact revision for which intended role, when, and with which limitations. An agent critique or model similarity score cannot impersonate owner acceptance.
- **Rights evidence:** source/provenance records, license-reference identity/date and unresolved restrictions. Technical success and art acceptance do not establish permission for a new use.
- **Delivery fit:** dimensions, format/size, crop/variants, accessibility metadata and allowed transformations. A different crop or edited derivative may require renewed role-specific acceptance.

`retrieved` does not by itself mean accepted or cleared. Consumers may publish/reuse only after the required identity, acceptance, rights and fit records are satisfied for that use. `generated_unaccepted` is a candidate, never a finished product asset. No placeholder is promoted by omitting a status field.

## Retrieval-first exchange

1. Freeze the consumer slot and constraints. Search existing approved records without changing acceptance labels.
2. Return suitable candidates and rejection reasons. Prefer a reusable variant over a near-duplicate generation where the constraints allow it.
3. On a genuine gap, return a bounded generation proposal. Do not submit on page load, automatically launch a backend, change packages, or infer authorization from a chat reference.
4. Once separately authorized, use existing reviewed LAS routes and preserve their prompt/job identities. If submission outcome is uncertain, reconcile that job; do not create another.
5. Review and accept the exact candidate through the existing owner workflow. Preserve source/derivative relationships and failed attempts.
6. Deliver immutable references plus the manifest. The consumer verifies actual bytes and role fit before adding the asset to a product. Raw local paths, private prompts and unreviewed images do not become public Git artifacts automatically.

## First qualification slice, not run

Use one synthetic UI asset slot and an already accepted asset if available. Prove retrieve → inspect exact revision → reuse with lineage without generating anything. If no accepted asset exists, record that blocker rather than fabricate an acceptance receipt.

Then test refusal/abstention for: missing acceptance; changed content under an old identity; unknown rights; missing generation budget; an uncertain existing job; unsupported crop/format; an untrusted path/URL; and a failed candidate incorrectly labelled final. These are proposed checks, not implemented or executed tests.

A later adapter may implement these boundaries in LAS after the concrete seam is chosen. Research conclusions stay in agent-hq; observer/rubric infrastructure stays in agent-harness; invocation recipes stay in claude-config. Product code, ComfyUI installation, live queues, existing CI and merge policies are unchanged. LLM quality judgments remain advisory.
