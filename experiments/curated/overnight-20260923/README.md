# Overnight lab, 23 September 2026: index

One agent ran the GPU queue from 03:02 to about 08:30 local and judged every output. It used the shared rubric (R1-R8), blind
comparisons where the protocol allowed, and full-resolution crops of hands and faces. Everything here is **generated and
agent-judged, not accepted**. Art acceptance and licence clearance stay with the owner. Pictures of famous characters and every
fanservice case live only in ComfyUI `output/Research/overnight-20260923/`; its `index.html` links each experiment's gallery. Git
holds the text evidence and original-character sheets only.

| experiment | question | headline | PR |
| --- | --- | --- | --- |
| [speed-census](speed-census/) | which verified presets are slow, and why | SDXL jobs are load- and decode-bound (sampling 9-10 s of 38-50 s; a 4-5 GB decode spill); Z-Image bf16 thrashes (308 s); Krea fp8 209 s | #859 |
| [sdxl-vae-decode](sdxl-vae-decode/) | does a tiled decode avoid the spill | tile 512 decodes in 1.3 s (median) against 2.4-6.8 s, is pixel-equivalent in a blind tie, and is usually spill-free (3/7 after a checkpoint switch still spilled) | #868 |
| [krea-gguf](krea-gguf/) | Krea 2 Q5_K_M GGUF against fp8 | with the text encoder on the CPU: 2.4 s/step, 77-101 s per new prompt against 175-544 s fp8, and a blind tie; the target stack takes 173 s against 828 s | #873, #880 |
| [q32-loras](q32-loras/) | q-32 LoRA candidates against controls | all four tie their control; Gothic Neon replaced the subject once | #875 |
| [combine-adult](combine-adult/) | the Combine routes on an adult original pair | drawn skeleton 3/3 keep; Copy Pose 2 keep + 1 fixable; the depth route lost the face on 2/3 | #875 |
| [combine-scale](combine-scale/) | is the depth face loss a portrait-scale effect | no: the same seeds fail with a full-body character picture | #883 |
| [hand-inpaint](hand-inpaint/) | a correction pass that fixes a six-digit hand | masked repaint at 0.6 with a feathered mask: five digits 3/3 with no seam; the old 0.4 fixed 0/3 | #881 |
| [klein-restyle](klein-restyle/) | the q-27 foot and colour defects | naming the true colours and the footwear went with both fixes, 3/3 (an association: both changed together) | #883 |
| [krea-refine-foxes](krea-refine-foxes/) | krea-refine on the fox shrine with its own prompt | 0.25 kept the foxes (3/3 by the lab, 2/3 by the second judge #889); 0.35 lost foxes on 3/3; the default is now 0.25 | #886 |
| [hand-fix](hand-fix/) | does the automatic detector hand route fix hands when turned up | no: 0 of 4 defects fixed at any setting (missed hands, the wrong hand, six redrawn as six, off-style at 0.6) | #890 |
| [stylepose-pack](stylepose-pack/) | Style + Pose on the pack's own adult original | poses mostly held, but all 18 renders burned neon at style weight 0.7 (second judge #891: standing held 5/9, not 9/9) | #890 |

Shared tooling: `labkit.py` (lease and queue guard, evidence records, GPU timelines, websocket timings, sealing), `crop.py` and
`strip.py` (full-resolution crops), `addjudge.py` and `judge_batch.py` (protocol-shaped judgements with the R7 check),
`gallery.py` and `gallery_index.py` (local galleries), and `suite.py` (the fixed showcase suite).
