"""Contact sheet for pose round two (15 September 2026): the two sources, the owner's preferred first-round Qwen render, and every
round-two render, one row per route, each tile labelled. Writes examples/combine-research/combine-pose-round2.jpg (local-only, gitignored)."""
import os, json
from PIL import Image, ImageDraw
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
INP = "C:/AI/ComfyUI_windows_portable/ComfyUI/input/"; OUT = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"
CHAR = INP + "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = INP + "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
ROWS = [
    [("character (image 2)", CHAR), ("pose picture", POSE), ("depth map (Depth Anything V2)", OUT + "klein-9b-depth-first-ref_00001_.png"),
     ("OpenPose skeleton (failed)", OUT + "qwen2-skeleton_00001_.png"), ("DWPose skeleton (failed)", OUT + "probe-dwpose_00001_.png")],
    [("Klein 9B depth first, seed 11 (115 s)", OUT + "klein-9b-depth-first_00001_.png"), ("Klein 9B depth first, seed 12 (114 s)", OUT + "klein-9b-depth-first_00002_.png"),
     ("Klein 9B depth first, seed 13", OUT + "klein-9b-depth-first_00003_.png"), ("Klein 9B depth first, seed 14", OUT + "klein-9b-depth-first_00004_.png"),
     ("Studio proving run (combine-klein-9b-depth)", "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Combine/Klein-9B-depth_00001_.png")],
    [("Klein 9B blank canvas first, seed 11 (90 s)", OUT + "klein-9b-blank-first_00001_.png"), ("Klein 9B blank canvas first, seed 12 (87 s)", OUT + "klein-9b-blank-first_00002_.png"),
     ("Klein 9B failed skeleton first, seed 11 (99 s)", OUT + "klein-9b-skel-first_00001_.png")],
    [("Qwen round 1, owner's pick (14.5 min)", OUT + "qwen-pose_00001_.png"), ("Qwen refs at 0.5 MP (12.9 min)", OUT + "qwen2-ref05_00001_.png"),
     ("Qwen failed skeleton as picture 2 (18.7 min)", OUT + "qwen2-skel05_00001_.png"), ("Qwen depth map as picture 2 (10.7 min)", OUT + "qwen2-depth05_00001_.png"),
    ],
]
H = 560; PAD = 8; LABEL = 22
tiles = []
for row in ROWS:
    ims = []
    for label, path in row:
        if os.path.exists(path): im = Image.open(path).convert("RGB"); im = im.resize((int(im.width * H / im.height), H))
        else: im = Image.new("RGB", (int(H * 2 / 3), H), (40, 40, 40)); ImageDraw.Draw(im).text((10, 10), "not rendered", fill="white")
        ims.append((label, im))
    tiles.append(ims)
W = max(sum(im.width for _, im in ims) + PAD * (len(ims) - 1) for ims in tiles)
sheet = Image.new("RGB", (W, len(tiles) * (H + LABEL + PAD)), "white"); d = ImageDraw.Draw(sheet); y = 0
for ims in tiles:
    x = 0
    for label, im in ims:
        sheet.paste(im, (x, y + LABEL)); d.text((x + 4, y + 4), label, fill="black"); x += im.width + PAD
    y += H + LABEL + PAD
dest = REPO + "/examples/combine-research/combine-pose-round2.jpg"; sheet.save(dest, quality=82); print(dest, sheet.size)
