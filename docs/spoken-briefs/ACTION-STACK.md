# Prepared narration for Action Stack

Consumer: Chris0Jeky/action-stack issue #14. Producer slice: #834.

Action Stack is now a reading/listening surface, not a speech-generation UI. Its server projects existing source text into a short immutable brief, and an explicitly enabled local preparer sends the exact narration through `scripts/action_stack_export.py`. This wrapper reuses `spoken_brief_runtime.plan/run`; it does not load another model, install packages, rewrite the source, watch folders, or start Studio.

## Supported route

The current executable profile is `kokoro-af-heart-control-v1`, delivery `calm-brief`, using the configured Kokoro `af_heart` baseline. Qwen3-TTS is not silently substituted or claimed as installed. Existing Voice-profile and producer fingerprint validation remains authoritative. Studio and the isolated Voice baseline must already be configured and running.

```powershell
python scripts/action_stack_export.py --request <job-dir>/request.json --job-dir <job-dir> --base-url http://127.0.0.1:8191
```

The executable and job directory are trusted local operator settings, not fields taken from Notion. The request permits exactly schema, jobId, briefId, actionId, narration, narrationSha256, profileId and deliveryId. Narration is one UTF-8 paragraph of at most 1600 characters. Lowercase SHA-256 identities bind exact text and voice. Job identity is SHA256 of briefId, narrationSha256, profileId and deliveryId joined by newlines.

## Publication protocol

The wrapper creates immutable `COMPRESSED.md` bytes (narration plus newline). The existing compiler's spoken projection must match the supplied narration before generation begins. The existing coordinator retains child project identities, plans, source/producer hashes, uncertainty and completed reuse. Its output/receipt must remain beneath this job's `_spoken` directory.

On success, source bytes and receipt source hash must still match, WAV bytes must match the receipt output hash, and the output must be bounded 48 kHz mono PCM16. `audio.wav` is atomically replaced first, then `bundle.json` last. The bundle schema `action-stack.audio/v1` carries jobId, briefId, narrationSha256, profileId, deliveryId, audioSha256, receiptSha256 and producerSha256. The full LAS receipt remains in `_spoken`; the consumer retains its digest and copies the verified audio into its own local storage transaction.

The consumer must compare every binding against its retained request and recheck current source content before publication. It must not accept a producer-chosen remote URL or serve arbitrary local files. Reading a brief and clicking Play only retrieve prepared content. They cannot create projects or submit inference.

## Recovery and limits

Exact valid completed bundles are reused without inference. Corrupt bundles or outputs block, never regenerate automatically. `.action-stack-export.lock` is exclusive and never expires merely by time. After a hard crash inspect the retained coordinator state, child jobs and owned processes before removing a stale lock or retrying the same request. Never create a replacement for an uncertain child submission.

Audio limit is 12 MB and 120 seconds. Publication stores bounded files and excludes private text/paths from CLI errors. A local filesystem administrator can replace files; hashes prove consistency, not an adversarial authenticity signature or subjective voice quality. The consumer must retain source access controls and invalidate audio after source changes.

## Verification

`python -m unittest discover -s tests -p "test_action_stack_export.py"` currently exercises 12 offline synthetic contracts. A corrupt-retained-provenance regression was observed failing before repair. Projection mismatch is rejected before `run`, and cached corruption cannot trigger a fresh generation. CI also runs the repository's normal checks. No real model generation or listening acceptance is implied by synthetic PCM. The configured workstation and HUMAN_TODO voice choices remain separate acceptance.
