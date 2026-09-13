# Anima baseline execution — 13 September 2026

This is a bounded execution record for the registered `anima-v1-baseline` preset. The three
completed jobs used the same source graph template SHA-256
`d20751dd896497052b56f60bb27b78eef862ce96c40fd74d10fea05b04194e19`, 832×1216 output, 30
steps, CFG 4.5, Euler/simple sampling and the same fully clothed adult original-character
prompt. The source receipts are retained under
`.runtime/session-2026-09-12/reconciliation/modular-probes/`.

| Case | Job ID / ComfyUI prompt ID | Controls changed from A | Output and file proof | Elapsed |
| --- | --- | --- | --- | ---: |
| A — base | `058abcb0-e962-45da-8534-43443e9a3f60` / `47dd2edd-8fc1-45d2-9d99-64ccb6f587dd` | All six Anima style slots disabled (`0`) | `C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio/Anima-v1-Baseline_00001_.png`; 1,052,391 bytes; SHA-256 `a3ee765d1dc1d2813ccbb0f2372b039eb3b34916da6d8a666c5dc4c641bc6d5b` | 28.098 s |
| B — first style | `91b42081-f15f-46ac-9d36-a819d6e5d857` / `75f6f833-6e5f-41bf-9eac-ab8c202f117d` | Only slot 1 changed from `0` to `1.0`; same prompt and seed `2026091301` | `C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio/Anima-v1-Baseline_00002_.png`; 1,133,744 bytes; SHA-256 `c88233c7320a6fc1520213edf05c491f71403d0365bb23545ec93f5336560a13` | 20.146 s |
| C — style, seed 2 | `a14fac06-2359-46f3-867e-feea7497118e` / `52345ff4-863b-4b79-a69b-e0f7784f7fde` | Same single slot-1 change as B; seed changed to `2026091302` | `C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio/Anima-v1-Baseline_00003_.png`; 1,055,309 bytes; SHA-256 `99c1a25c4b77630b9d0c2ade29e2cc7e464ea9521122ab1992b5c523105ce7c3` | 18.078 s |

The three PNGs were visually inspected by the root agent. A showed a clean graphic coat,
trousers and boots on the station platform. B kept the same prompt and seed and supplied the
preferred softer cinematic shading. C, with the second seed, kept a similar wardrobe and softer
look but produced a new face and bangs. In all three images the hands were hidden in pockets, so
hand quality is unproven. B is the owner's selected starting look for the fantasy-character pack;
all three outputs remain experiments and none was added to the private shortlist.

These runs establish completed generation and visual inspection for this exact registered graph
and control boundary. They do not establish character identity consistency, pose/reference,
masked correction, upscale quality, licensing, commercial permission or general reliability.
Elapsed times are confounded by cache state and carry no performance claim. Native crash
prevention is unproven; this is a light Anima execution only.
