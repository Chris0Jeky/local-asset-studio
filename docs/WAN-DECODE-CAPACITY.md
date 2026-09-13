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
or creative acceptance. A full source-bound run with the changed decoder remains
a distinct bounded experiment. The guard does not certify arbitrary tiled graphs.

Offline checks are `python -m unittest discover -s tests -p test_wan_capacity.py`.
The optional browser proof is
`python tests/wan_capacity_browser.py --out .runtime/wan-capacity-browser` and
serves synthetic APIs without contacting ComfyUI or submitting generation.
