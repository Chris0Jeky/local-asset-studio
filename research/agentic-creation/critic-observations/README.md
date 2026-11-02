# Retained critic observations and continuation

This directory makes the earlier pixel-policy experiment inspectable from Git,
without depending on a conversation attachment or committing generated media.
`observations.jsonl` contains all **24 raw comparison receipts**, constructed review
labels and per-case hypothetical decisions. `manifest.json` pins the observations,
source hashes, environment and aggregate results. These are owned synthetic pixels,
**not native Blender measurements or artistic judgements**.

The 0.4% per-view floor still suppresses five constructed defects. No production
threshold has been raised. The archived 26-pixel nuisance case is nuisance by
construction, not proof of a Cycles noise distribution. Views, resolutions and
copies of one case are related; no statistical independence is claimed.

## Reproduce

From the repository root, with its existing Python/Pillow environment:

```console
python -m unittest discover -s tests -p "test_render_critic_retained_evidence.py" -v
python scripts/render_critic_study.py --out-dir .runtime/critic-study-NEW
```

The first command replays every saved policy decision **and regenerates the full
owned image study**, checking exact semantic receipts and aggregate results. The
second retains all images and a local HTML comparison page. The original run's
encoded artifact digest is historical provenance: PNG bytes may depend on
Pillow/zlib versions, so tests do not pretend encoded byte identity across hosts.

## Saved native-result replay

New sentinel results retain the full pixel observation at
`second_signal.observation`. The adapter marks failed/incomplete observations
unavailable instead of counting the conservative `changed=true` compatibility bit
as an independent detection. Primary warnings are left unchanged.

```console
python scripts/render_critic_policy.py replay PATH_TO_RESULT_JSON --input-kind sentinel --fraction 0.004 --out .runtime/critic-policy-NEW.json
```

Replace `PATH_TO_RESULT_JSON` with an existing sentinel `result.json`. Its input
byte hash is retained. Nothing is rendered, inferred or launched; document asset
paths are not followed. The fraction is an **experiment**, not a selected default.
Exit 0 means that hypothetical pixel policy does not request review; 1 means it
does; 2 means incomplete or invalid input. None is overall asset/art acceptance.
Old summary-only results stay incomplete rather than receiving guessed dimensions.

## What is saved elsewhere

- [Current verification, findings and next native experiment](../../../docs/research/CRITIC-OBSERVATION-CONTINUATION-2026-11-02.md).
- [Original policy study and qualification plan](../../../docs/research/RENDER-CRITIC-POLICY-STUDY-2026-11-02.md).
- [Losslessly preserved earlier capture-contract source](../archive/capture-contract-followup/README.md); archived, not activated.

Private source assets and the complete private research export remain outside this
public repository. This directory never grants upload, runtime or licence permission.
