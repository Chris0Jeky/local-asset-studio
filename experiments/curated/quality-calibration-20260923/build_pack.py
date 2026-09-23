"""Build the blind calibration pack of 23 September 2026: metadata-stripped copies under shuffled labels, a brief file,
and a sealed key, all under the gitignored .runtime/quality-calibration/. Paths are this PC's ComfyUI output and the
old receipts checkout's Workspace media. Seed 20260923 reproduces the label order used on the night."""
import json, os, random, hashlib, shutil
from PIL import Image

OUT = "C:/AI/ComfyUI_windows_portable/ComfyUI/output"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PACK = os.path.join(REPO, ".runtime", "quality-calibration", "pack")  # gitignored
WS = "C:/Users/jekyt/source/local-asset-studio/experiments/workspace/media"

SORCERESS_WAI = "1girl, solo, adult woman, elven sorceress, long white hair, pointy ears, ornate robe, magic circle, floating particles, rim lighting, backlighting, upper body, dutch angle, depth of field, fantasy (WAI v17 Illustrious, tag prompt)"
WITCH = ("Painterly oil-textured anime illustration: a young witch sits peacefully in a dense magical meadow of vibrant flowers, "
         "frilly black witch outfit, a real big witch hat, wavy indigo gradient hair, eyes gently closed, light smile; a small sleek "
         "black cat in her lap leaning against her hands; a curious tabby cat sits nearby on yellow flowers; rich painterly texture.")
LANTERN = ("adult woman, solo, original fantasy cartographer and lanternkeeper, navy travel coat with brass clasps, teal scarf, high collar, "
           "leather gloves, ankle boots, holding a brass compass and a warm lantern, map case at her hip, misty ruined observatory at dusk, "
           "warm rim light, teal and amber palette, painterly illustration")
STATION = ("A fully clothed adult original character with long dark hair wears a tailored travelling coat, high-neck shirt, trousers and "
           "leather boots. She stands calmly on a rain-washed station platform in soft evening light, full body, detailed modern anime "
           "illustration, cinematic composition. (Anima base model; this is a candidate STARTING LOOK for a fantasy character pack.)")
RESTYLE = ("RESTYLE task: redraw the source picture REF-restyle-source.png in the look of the style picture REF-restyle-style.png, keeping the "
           "witch, her pose on the throne, costume, throne and setting. Judge style against the style picture, control against the source.")

ITEMS = [
    # key, path, brief, owner tier (pre-registered; never shown to judges)
    ("wai12", f"{OUT}/Studio/WAI-Illustration_00012_.png", SORCERESS_WAI),
    ("noob4", f"{OUT}/Studio/noob_00004_.png", SORCERESS_WAI.replace("dutch angle, ", "").replace("(WAI v17 Illustrious, tag prompt)", "(NoobAI XL 1.1, tag prompt)")),
    ("pony2", f"{OUT}/Studio/pony_00002_.png", "adult elven sorceress, long white hair, pointy ears, ornate robe, magic circle, floating particles, rim lighting, backlighting, cowboy shot, depth of field, fantasy (Pony V6, score-tag prompt)"),
    ("krea_atelier1", f"{OUT}/Studio/krea-anime-atelier_00001_.png", "Medium close-up portrait at eye level, shallow depth of field, warm lantern light crossing cool moonlight, a young witch with long lavender hair and amber eyes in a wide-brimmed hat and deep indigo travelling cloak trimmed with gold, on the mossy stone balcony of a hillside tower, drifting motes of light and open grimoires floating around her, calm half-smile, one hand steadying her hat while the wind lifts the cloak, painterly anime illustration with soft cel shading and delicate line work."),
    ("krea_stylelab1", f"{OUT}/Studio/krea-style-lab_00001_.png", "a fox spirit shrine on a cliff at dawn, paper lanterns and drifting petals, soft mist over the valley, airy anime watercolor style (scene, not a character)"),
    ("w_ersde4", f"{OUT}/Studio/probes/witch-target-ersde-4step_00001_.png", WITCH),
    ("w_baroque4", f"{OUT}/Studio/probes/witch-target-plus-baroque-oil-4step_00001_.png", WITCH + " (plus a baroque dreamscape oil style)"),
    ("w_stack", f"{OUT}/Studio/probes/witch-target-stack_00001_.png", WITCH),
    ("w_stack4", f"{OUT}/Studio/probes/witch-target-stack-4step_00001_.png", WITCH),
    ("w_nijisis", f"{OUT}/Studio/probes/witch-nijisis-baseline_00001_.png", WITCH),
    ("w_nijisis4", f"{OUT}/Studio/probes/witch-nijisis-4step_00001_.png", WITCH),
    ("w_airy4", f"{OUT}/Studio/probes/witch-airy-watercolor-short-4step_00001_.png", "A young witch with wavy indigo hair and a big black hat sits in a glowing meadow of orange and purple wildflowers, a black cat in her lap and a tabby cat beside her, eyes closed, gentle smile, painterly texture, airy anime watercolor style"),
    ("wai13", f"{OUT}/Studio/WAI-Illustration_00013_.png", LANTERN + ", bold lineart, high contrast, limited palette, subtle grain, poster style (WAI v17 + a graphic poster LoRA)"),
    ("anima4", f"{OUT}/Studio/anima-artist-stack_00004_.png", LANTERN + ", detailed background (Anima + artist-style LoRAs)"),
    ("animaA", f"{OUT}/Studio/Anima-v1-Baseline_00001_.png", STATION),
    ("animaB", f"{OUT}/Studio/Anima-v1-Baseline_00002_.png", STATION),
    ("compassA", f"{REPO}/experiments/curated/compass-first-batch/seed-2026091103-large.png", "pixel art, one brass compass with teal enamel, three quarter view, clear silhouette, white background, game inventory icon (will be exported at 128 px; judge at 1024 and imagine 128)"),
    ("compassB", f"{REPO}/experiments/curated/compass-first-batch/seed-2026091104-large.png", "pixel art, one brass compass with teal enamel, three quarter view, clear silhouette, white background, game inventory icon (will be exported at 128 px; judge at 1024 and imagine 128)"),
    ("restyle_owner", f"{OUT}/Style-Pose/Nova_00007_.png", RESTYLE + " (style weight 0.7)"),
]
REFS = {
    "REF-restyle-source.png": f"{OUT}/Style-Pose/Nova_00004_.png",
    "REF-restyle-style.png": f"{WS}/cc25e72f01542544eb1544194f067f496cd2bc06f0812886ddca1430c0cbd62d.png",
}

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def strip_copy(src, dst):
    im = Image.open(src)
    im.load()
    clean = Image.new(im.mode, im.size)
    clean.frombytes(im.tobytes())
    clean.save(dst, format="PNG")

def main():
    os.makedirs(PACK, exist_ok=True)
    rng = random.Random(20260923)
    order = list(range(len(ITEMS)))
    rng.shuffle(order)
    key = {}
    briefs = {}
    for n, i in enumerate(order, 1):
        k, p, brief = ITEMS[i]
        lab = f"C{n:02d}"
        strip_copy(p, os.path.join(PACK, lab + ".png"))
        key[lab] = {"key": k, "source": p, "sha256": sha(p)}
        briefs[lab] = brief
    for name, p in REFS.items():
        strip_copy(p, os.path.join(PACK, name))
    json.dump(briefs, open(os.path.join(PACK, "briefs.json"), "w", encoding="utf-8"), indent=1)
    json.dump(key, open(os.path.join(os.path.dirname(PACK), "key.sealed.json"), "w", encoding="utf-8"), indent=1)
    print("pack", PACK, len(key))

if __name__ == "__main__":
    main()
