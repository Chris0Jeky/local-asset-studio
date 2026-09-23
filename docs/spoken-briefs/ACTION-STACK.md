# Prepared narration for Action Stack

Consumer: Chris0Jeky/action-stack issue #14 / PR #15. Producer slice: #834 / PR #835.

Action Stack is a reading/listening surface, not a speech-generation UI. Its server projects source text into a short immutable brief; an explicitly enabled local preparer sends exact narration through `scripts/action_stack_export.py`. This wrapper reuses the existing compiler and `spoken_brief_runtime.run`. It adds no model loader, network server, folder watcher or source editor.

## Supported route and invocation

Current executable profile: `kokoro-af-heart-control-v1`, delivery `calm-brief`, using the configured Kokoro `af_heart` baseline. Qwen3-TTS is not silently substituted or claimed as installed. Existing profile/producer fingerprint checks remain authoritative. Studio and the isolated Voice baseline must already be configured and running.

```powershell
python scripts/action_stack_export.py --request <job-dir>/request.json --job-dir <job-dir> --base-url http://127.0.0.1:8191
```

Executable, endpoint and directory are trusted operator settings, never taken from Notion. The request permits exactly schema, jobId, briefId, actionId, narration, narrationSha256, profileId and deliveryId. Narration is one UTF-8 paragraph, at most 1600 characters. Lowercase SHA256 identities bind the text and voice. Job ID is SHA256 of briefId, narrationSha256, profileId and deliveryId joined by newlines.

## Compilation and publication

Immutable `COMPRESSED.md` bytes contain narration plus newline. Use the existing **non-mutating** `compile_source` with the resolved executable voice binding. Compare its spoken projection to the supplied transcript before generation. If an existing run's manifest differs, block without replacing it. Do not call `plan()` here: that command writes the manifest before the runtime's integrity check.

The existing coordinator retains child-project identities, source/producer hashes and uncertainty. Its output and receipt must resolve beneath the job's `_spoken` directory. Verify unchanged source bytes, receipt source/output hashes, producer identity, bounded 48 kHz mono PCM16 and duration before publishing. Limits: 12 MB and 120 seconds.

Publish a local `.receipt-reference.json` pointing to the original owned `_spoken` receipt, then `audio.wav`, then `bundle.json` last, using atomic replacements. The public exchange schema `action-stack.audio/v1` carries jobId, briefId, narrationSha256, profileId, deliveryId, audioSha256, receiptSha256 and producerSha256. The reference file is producer-local recovery metadata, not a path the consumer follows.

On completed reuse, read the **actual retained receipt bytes**, recheck their digest, producer identity, source and output binding, and revalidate audio. Missing/changed provenance or an escaping receipt reference blocks without invoking inference. A syntactically valid digest alone does not establish retained provenance.

The consumer independently validates every binding, derives audio metadata from bytes and rechecks current source text before atomically publishing its local audio/manifest. It must not serve producer-chosen remote URLs or arbitrary local files. GET/open/Play are read-only delivery operations.

## Recovery and limits

Valid completed bundles are reused. Corrupt bundles, receipts or audio never trigger automatic regeneration. The exclusive `.action-stack-export.lock` never expires merely because time passed. After a hard crash inspect owned processes, retained coordinator state and exact child projects before removing any lock or explicitly retrying. Never recreate an uncertain child submission.

Hashes establish content consistency, not an authenticity signature against a malicious local administrator or subjective voice quality. Private source text, audio, paths and credentials stay outside Git and CLI errors.

## Verification

`python -m unittest discover -s tests -p "test_action_stack_export.py" -v` exercises **18 offline synthetic contracts**. Four review regressions were observed failing before repair: missing/changed original receipt, changed retained producer identity, and projection checking that overwrote a retained manifest. Matching projection and confined-reference cases also pass. Focused Ubuntu/Windows CI and normal repository gates qualify each published head.

Synthetic PCM and compiler doubles do not establish real model inference or listening acceptance. The configured workstation and HUMAN_TODO voice decisions remain separate. No private source data or generated speech is committed.

## Upstream handoff content

[Handoff compression and listening provenance](HANDOFF-PROVENANCE.md) proposes an editorial lineage sidecar and listening pilot around this implemented route. It does not add fields to the request/bundle, another producer, or generation on GET/Play.
