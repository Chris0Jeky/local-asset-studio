"""Contact sheet for pose round three (15 September 2026): one row per question, the prepared image 1 at the left of each row, every seed
labelled. Writes examples/combine-research/combine-pose-round3.jpg (local-only, gitignored)."""
import os
from PIL import Image, ImageDraw
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
RS = os.path.dirname(os.path.abspath(__file__)) + "/"; OUT = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"
INP = "C:/AI/ComfyUI_windows_portable/ComfyUI/input/"
CHAR = INP + "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = INP + "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
def seeds(prefix, labels, n=3): return [(labels + " seed " + str(11 + i), OUT + prefix + "_0000" + str(i + 1) + "_.png") for i in range(n)]
ROWS = [
    [("character (image 2)", CHAR), ("pose picture", POSE), ("depth map, feet painted out", RS + "pose3-depth-feet.png"), ("depth map, tail + skirt + feet painted", RS + "pose3-depth-painted.png"),
     ("drawn skeleton", RS + "pose3-skeleton-drawn.png"), ("drawn capsule mannequin", RS + "pose3-mannequin-drawn.png")],
    [("feet painted out, seed 11", OUT + "pose3-depth-feet_00002_.png"), ("feet painted out, seed 12", OUT + "pose3-depth-feet_00003_.png"), ("feet painted out, seed 13", OUT + "pose3-depth-feet_00004_.png")] + seeds("pose3-depth-painted", "tail+skirt+feet painted,"),
    seeds("pose3-hands-camera", "hand + camera words,") + seeds("pose3-depth-8steps", "8 steps,"),
    seeds("pose3-skeleton-drawn", "drawn skeleton,") + seeds("pose3-mannequin-drawn", "capsule mannequin,"),
    [("slow state: after /free (377 s)", OUT + "probe-speed-afterfree_00001_.png"), ("after the ComfyUI restart (95 s)", OUT + "probe-speed-afterrestart_00001_.png")] + seeds("pose3-depth-q8", "Q8_0 GGUF,"),
    seeds("pose3-copypose", "Copy Pose LoRA,") + seeds("pose3-copypose-depth", "Copy Pose LoRA + depth map,"),
    seeds("pose3-replacechar", "replace-character LoRA,") + seeds("pose3-refcontrol-skel", "RefControl LoRA + drawn skeleton,"),
    seeds("pose3-refcontrol-depth", "RefControl LoRA + depth map,") + [("Mannequin LoRA: the pose picture as a mannequin", OUT + "pose3-mannequin-gen_00001_.png")] + seeds("pose3-mannequin-combine", "that mannequin through the depth recipe,"),
    [("Studio: combine-klein-9b-skeleton proving run (job 26448d58)", OUT + "../Combine/Klein-9B-skeleton_00001_.png"),
     ("Studio two-pass, pass 1: depth Combine, hands+camera fill (job c31e7777)", OUT + "../Combine/Klein-9B-depth_00002_.png"), ("Studio two-pass, pass 2: Change one thing, bare feet (job b92dae0c)", OUT + "../Verified/FLUX-Edit_00009_.png")],
]
H = 480; PAD = 8; LABEL = 22
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
dest = REPO + "/examples/combine-research/combine-pose-round3.jpg"; sheet.save(dest, quality=80); print(dest, sheet.size)
