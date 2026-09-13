# Wan decode capacity

The ordinary Wan 2.2 decoder is held above the recorded short-run envelope:
512x768 or its landscape orientation, at most 33 frames, one latent batch, and
no edge longer than 768 pixels. Quick diagnostic and Balanced remain available.
The browser explains the hold for Quality and Canonical upstream. Server
preparation, Production preflight and the final submission check inspect the
actual graph, so removing mode metadata or restoring an older queued job does
not repeat the known long untiled path.

This is a conservative admission limit based on this workstation's retained
failure, not a memory estimator or a promise that every admitted result succeeds.
The 1280x704, 41-frame canonical control completed sampling but failed during
ordinary VAE decode while requesting 18.56 GiB on a 15.92 GiB GPU. Its original
job, prompt, graph and error remain preserved. No capacity is inferred from
additional host paging or a successful model download.

A separate zero-latent probe on 13 September 2026 decoded all 41 frames at
1280x704 using `VAEDecodeTiled`, spatial tile 512, overlap 64, temporal tile 8 and
temporal overlap 4. It completed in 59.65 seconds. The exact prompt is
`b30b19f6-3bac-4e28-9f4f-bbed8b8b8ff7`; the graph, VAE hash, preflight and output
manifest are retained locally under `.runtime/goal-20260913/wan-tiled-decode-only/`.

That probe loaded only the VAE and decoded a synthetic zero latent. It performed
no source encoding or sampling. All 41 output files were checked for 1280x704
dimensions and one diagnostic frame was inspected; its neutral patterned output
is expected diagnostic material, not animation quality evidence. The probe does
not establish full-model coexistence, an improved real video, temporal identity,
or creative acceptance. The guard does not certify arbitrary tiled graphs.

A subsequent full canonical control, prompt
`7722bd99-5a2f-4233-b799-82b126ff278a`, completed in **1005.258 seconds** with
the same source, model files, 1280x704 canvas, 41 frames, 30 steps, seed
869177064731501, CFG 5 and uni_pc/simple sampler settings as the retained failed
canonical graph. Only the decoder was changed to the tiled settings above and
the output prefix was changed. Preflight hashed all three model files and the
source. The output is an H.264 MP4, 41 frames at 24 fps, 1.708008 seconds.

**The video failed visual inspection.** Frame 0 retains the source composition;
frame 1 already shows oversaturated mosaic breakup. Later frames flicker with
cyan/white corruption and smeared anatomy. All 41 frames were extracted and the
complete contact sheet was inspected. This exact run completed within memory;
it did not establish usable animation, improved temporal consistency, a safe
general tiled configuration or art acceptance. No further sampling attempt is
scheduled from this result. Do not infer a cause from the apparent flicker alone.

The graph, original graph, full model hashes, history, MP4, ffprobe result and all
frames remain under `.runtime/goal-20260913/wan-tiled-canonical-control/` and the
recorded ComfyUI Diagnostics output path. A small machine-independent failure
record with output hash is curated in
[`wan-tiled-control-failure.json`](../experiments/curated/goal-baselines-20260913/wan-tiled-control-failure.json).
Before any future full run, define a distinct control and retain its sampled
latent so decode-only comparisons can reuse the same input. The current run has
no durable sampled-latent artifact; an in-memory cache is not evidence of one.

Offline checks are `python -m unittest discover -s tests -p test_wan_capacity.py`.
The optional browser proof is
`python tests/wan_capacity_browser.py --out .runtime/wan-capacity-browser` and
serves synthetic APIs without contacting ComfyUI or submitting generation.
