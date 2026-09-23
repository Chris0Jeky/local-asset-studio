# Handoff compression and listening provenance

Status: architecture proposal, 2026-09-23. Extends Spoken Briefs; no runtime or wire-format change. Inspected main `25dcf5d8eb269cb31affd6c3dcdf221cedb86208`, umbrella [#635](https://github.com/Chris0Jeky/local-asset-studio/issues/635) and merged exporter [#835](https://github.com/Chris0Jeky/local-asset-studio/pull/835). See [ACTION-STACK](ACTION-STACK.md) for the implemented producer contract.

## The missing boundary is before synthesis

The existing pipeline compiles Markdown, coordinates existing voice projects, assembles audio and retains receipts. It does not certify that an upstream compressed summary faithfully represents the detailed engineering report. Add an explicit editorial boundary rather than another speech product:

```text
canonical report and retained evidence
  -> source-backed COMPRESSED.md, with omission notes
  -> existing deterministic spoken projection and preview
  -> explicit generation through the existing coordinator
  -> existing assembly, receipt and optional exports
  -> skimmable text plus a pointer back to the canonical pack
```

The report is produced once. Corrections create a new identified revision, followed by a new summary when the meaning changes. Do not summarize an earlier summary repeatedly until the provenance or limitations disappear. Keep fact, proposal, previously recorded evidence and newly executed evidence distinguishable in the script.

The original completed research report was not retrievable during this work. This is a source-checked architectural recommendation, not a claimed transcription or a measured listening improvement. [W3C PROV-Overview](https://www.w3.org/TR/prov-overview/), a Working Group Note dated 2013-04-30, motivates recording inputs, transformation and producer separately. It does not establish truth or require a graph database.

## Two supported shapes, one speech spine

For a full handoff pack, retain the existing COMPRESSED-first, INDEX-fallback selection and `_spoken/` coordinator state. Ops owns canonical REPORT/INDEX, disk/Notion/chat findability and shared memory; LAS owns rendering and its evidence. A document revision already advertised or narrated is not edited in place to claim a different result.

For Action Stack, retain the implemented bounded route in [ACTION-STACK](ACTION-STACK.md): one narration paragraph, at most 1600 characters, the current executable `kokoro-af-heart-control-v1` / `calm-brief` binding, verified 48 kHz mono PCM16, 12 MB and 120-second limits. These are adapter limits, not a claim that every full handoff must fit one Action Stack card.

A long report must be deliberately compressed upstream, not silently truncated into a apparently complete story. Do not add a summary model to the consumer GET/Play path. The current Kokoro baseline is executable; it is not evidence of a custom voice identity or subjective owner acceptance. Qwen3-TTS qualification stays in its existing separate track.

## Passive pack lineage, unchanged exchange schema

Keep a proposed pack-local `PROVENANCE.md` beside REPORT/COMPRESSED/INDEX. It is an editorial sidecar, not a LAS runtime input or another evidence envelope. Record:

| Record | Required meaning |
|---|---|
| Canonical source | Pack ID/revision, source document locator and exact report byte hash |
| Compression | COMPRESSED byte hash, source sections/claim references, material omissions, writer/tool identity and time |
| Source evidence | Repository or issue locator, full revision where available, observation time and access classification |
| Rendering | Existing manifest/receipt locator, narrated source hash, selected profile/delivery and actual output hash |
| Navigation | Human-readable pack signpost and source entry point; actual private locators remain local |

Compute hashes from the retained bytes; unknown values remain unknown. A mutable URL alone is not a retained snapshot. Hashes bind the rendering chain but cannot prove factual completeness, authenticity against a malicious local actor or human approval.

Do not append canonicalPackPath, Notion URLs, report hashes or arbitrary metadata to the strict `action-stack.audio/v1` request or bundle. The current request and bundle key sets remain unchanged. Extra lineage belongs outside that exchange until a separately versioned producer/consumer migration is specified and tested. The consumer must never resolve a producer-supplied arbitrary path or remote URL.

For the existing Action Stack route, the consumer-owned source reference remains the way back to the task. Pack lineage can be retained upstream in the canonical report or source-owned description. This proposal does not claim that the current player already displays a pack sidecar.

## Script and preview rules

The compressed script states the result, the limitation that changes the decision, and the next action or "no action needed". Say a short pack identifier aloud; leave full paths, code and URLs in the skimmable view. Preserve numbers with units and the meaning of qualified results. An omission ledger points to material detail that was excluded for length.

Inspect the existing spoken projection before generation. A Markdown link or table may render differently from its written appearance, so verify that the caveat survives the compiler, not just the source review. For Action Stack, use the existing non-mutating projection check; never call a planning operation that overwrites a retained manifest while checking it.

A changed source, profile, delivery or retained provenance requires the existing identity and recovery handling. A corrupted bundle or uncertain child is a blocked inspection task, not permission to synthesize again. Reassembly and an export over valid retained audio do not imply another TTS run.

## Listening without notification noise

Narration is a prepared view requested by the operator or admitted under the existing explicit configuration, not an announcement for every agent event. Routine progress, duplicate comments, unchanged checks and status-only edits remain silent. One material result may join a requested recap; a real unresolved choice gets a short question and its canonical record, not a narrated issue backlog.

Keep text usable before audio is available. Do not auto-play, synthesize on page load, introduce browser speech fallback or interrupt an existing recording with another one. Missing audio says unavailable/preparing/blocked as appropriate. Playback completion means heard, not approved, accepted, merged or completed.

The owner's preferred pacing and acceptable fatigue are listening outcomes. No synthetic PCM fixture, transcript match or green CI run substitutes for those outcomes. Existing HUMAN_TODO voice choices remain owner-controlled.

## Gaps and bounded follow-through

| Slice | Owner / existing track | Smallest useful next step |
|---|---|---|
| Source-to-summary lineage | Ops pack authoring, with #635 integration notes | One manual PROVENANCE sidecar and omission map; no schema migration |
| Preview findability | Existing aggregate/review work #638 and #641 | Confirm the source, projection and retained receipt can be reached through the current UI; keep #829 navigation work separate |
| Long-form listening | #640 | Reuse existing chapter/export and playback work; chapters must use actual assembly offsets, not estimated speech timings |
| Consumer signpost | Existing Action Stack focus consumer | Trial a source-authored pack signpost before proposing a new typed metadata field |

These are proposals, not reopened implementation claims. The exporter is already delivered by #835; do not seed it again. No new TTS stub is justified by this documentation gap.

## Pilot fixtures to retain locally

1. A short synthetic report with an important failed check. Confirm COMPRESSED and the spoken projection retain that limitation and point to the same report revision.
2. A corrected report revision with unchanged short narration. Confirm the editorial lineage distinguishes source freshness from audio-byte reuse; do not falsely label an old receipt as a new report's receipt.
3. A full pack and a bounded Action Stack request. Confirm each uses its existing route, and that an over-limit consumer request is not silently truncated or sent to another speech engine.
4. One real operator-selected walk: ask for the result, caveat, next action and location of the detailed record afterward. Record misses, fatigue and correction effort without interpreting a preference as universal quality.

No inference, private source import, listening trial or new native acceptance was performed to author this note. Existing test and receipt owners remain unchanged.
