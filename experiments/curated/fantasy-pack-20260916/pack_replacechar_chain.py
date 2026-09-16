"""Fantasy pack, replace-character LoRA, second research batch (16 September 2026, straight against ComfyUI, not a Studio recipe yet):
  chain  image 1 = the depth-Combine output that lost the face (Workspace asset 7a8a5d27, staged through POST /api/assets/reference the way
         *Continue with this* does), image 2 = the batch's portrait: does the pose route + the face route chain? three seeds.
  cross  image 1 = the batch's full-body render, image 2 = the anime SHARK character: does identity cross styles, do image 1's clothes hold? two seeds.
Every accepted prompt ID is persisted before polling. Re-running resumes an interrupted submitted or timed-out prompt and skips terminal
records, so a recorded (group, seed) is never submitted again. Graphs live under the committed research-graphs/ evidence directory."""
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
COMFY = "http://127.0.0.1:8188"
STUDIO = "http://127.0.0.1:8191"
RESULTS = OUT / "pack_replacechar_chain.json"
GRAPH_DIR = OUT / "research-graphs"
FULLBODY = "9c880763266a454091725b57ad392762_Anima-v1-Baseline_00005_.png.png"
PORTRAIT = "aa93fb465e364532a33d40dfb21894a9_Anima-v1-Baseline_00004_.png.png"
SHARK = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
DEPTH_OUTPUT_ASSET = "7a8a5d27c1975ced96ff3d04f2fc7d03"
CLOTHES = ("She wears image 1's clothes: a navy double-breasted travelling coat with brass buttons, a teal scarf, dark trousers, brown lace-up boots, "
           "holding a brass lantern, a leather satchel on a strap. ")
TEXT = {
    "chain": ("Replace the woman in image 1 with the woman in image 2, while keeping the same pose, action, camera angle, composition, background and "
              "lighting as in image 1. The woman in image 2 has long centre-parted dark hair with a fringe, brown eyes, a calm face and small gold earrings; "
              "keep her face, hair and expression exactly as in image 2. " + CLOTHES + "Keep image 1's clean rendering and its plain light background. "
              "One figure only, nobody else in the picture."),
    "cross": ("Replace the woman in image 1 with the character in image 2, while keeping the same pose, action, camera angle, composition, background and "
              "lighting as in image 1. The character in image 2 is Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker; "
              "keep her face, hair and expression exactly as in image 2. " + CLOTHES + "Keep image 1's painterly rendering and its station platform. "
              "One figure only, nobody else in the picture."),
}
BASE = json.loads((ROOT / "workflows/api/combine-klein-9b-api.json").read_text(encoding="utf-8"))


def load_records(path=RESULTS):
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Research receipt must be a JSON array: {path}")
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValueError(f"Research receipt row {index} must be a JSON object: {path}")
    return value


def save_records(records, path=RESULTS):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def find_record(records, group, seed):
    matches = [record for record in records
               if record.get("group") == group and record.get("seed") == seed]
    if len(matches) > 1:
        raise ValueError(f"Duplicate research receipt rows for {group} seed {seed}")
    return matches[0] if matches else None


def upsert(records, record):
    matches = [index for index, current in enumerate(records)
               if current.get("group") == record["group"]
               and current.get("seed") == record["seed"]]
    if len(matches) > 1:
        raise ValueError(
            f"Duplicate research receipt rows for {record['group']} seed {record['seed']}"
        )
    if matches:
        records[matches[0]] = record
    else:
        records.append(record)


def post_studio(path, body, *, open_url=urllib.request.urlopen):
    request = urllib.request.Request(STUDIO + path, json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "Origin": STUDIO})
    try:
        return json.load(open_url(request, timeout=120))
    except urllib.error.HTTPError as error:
        raise SystemExit("rejected %s %s %s" %
                         (path, error.code, error.read().decode("utf-8", "replace")[:800]))


def build(group, image1, image2, seed):
    graph = copy.deepcopy(BASE)
    graph["14"]["inputs"]["image"] = image1
    graph["20"]["inputs"]["image"] = image2
    graph["40"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "replace_character_v1_klein.safetensors", "strength_model": 1.0, "model": ["1", 0]}}
    graph["6"]["inputs"]["model"] = ["40", 0]
    graph["4"]["inputs"]["text"] = TEXT[group]
    graph["7"]["inputs"]["noise_seed"] = seed
    for node in ("9", "10"):
        graph[node]["inputs"]["width"] = 832
        graph[node]["inputs"]["height"] = 1216
    graph["13"]["inputs"]["filename_prefix"] = "Research/pack-replacechar-" + group
    return graph


def poll(prompt_id, submitted_at, *, open_url=urllib.request.urlopen, clock=time.time,
         sleeper=time.sleep, timeout_seconds=1800):
    started = clock()
    while clock() - started < timeout_seconds:
        sleeper(4)
        history = json.load(open_url(COMFY + "/history/" + prompt_id, timeout=30))
        if prompt_id not in history:
            continue
        entry = history[prompt_id]
        status = entry.get("status", {})
        files = [output["subfolder"] + "/" + output["filename"]
                 for node in entry.get("outputs", {}).values()
                 for output in node.get("images", [])]
        errors = [message[1].get("exception_message")
                  for message in status.get("messages", [])
                  if message[0] == "execution_error"]
        return {"status": status.get("status_str"),
                "seconds": round(clock() - submitted_at, 1),
                "files": files, "error": errors}
    return {"status": "timeout", "seconds": round(clock() - submitted_at, 1),
            "files": [], "error": []}


def run(group, image1, image2, seed, *, results_path=RESULTS, graph_dir=GRAPH_DIR,
        open_url=urllib.request.urlopen, clock=time.time, sleeper=time.sleep):
    records = load_records(results_path)
    record = find_record(records, group, seed)
    if record and record.get("status") not in {"submitted", "timeout"}:
        print("skip", group, seed, "(recorded)", flush=True)
        return record

    if record:
        record = dict(record)
        prompt_id = record["prompt_id"]
        submitted_at = float(record["submitted_at"]) if "submitted_at" in record else clock()
    else:
        graph = build(group, image1, image2, seed)
        graph_dir.mkdir(parents=True, exist_ok=True)
        (graph_dir / f"pack-replacechar-{group}-{seed}.graph.json").write_text(
            json.dumps(graph, indent=1) + "\n", encoding="utf-8")
        request = urllib.request.Request(COMFY + "/prompt",
                                         json.dumps({"prompt": graph}).encode(),
                                         {"Content-Type": "application/json"})
        prompt_id = json.load(open_url(request, timeout=60))["prompt_id"]
        submitted_at = clock()
        record = {"group": group, "seed": seed, "prompt_id": prompt_id,
                  "status": "submitted", "submitted_at": submitted_at,
                  "image1": image1, "image2": image2, "text": TEXT[group],
                  "lora": "replace_character_v1_klein.safetensors",
                  "size": "832x1216"}
        upsert(records, record)
        save_records(records, results_path)

    record.update(poll(prompt_id, submitted_at, open_url=open_url,
                       clock=clock, sleeper=sleeper))
    upsert(records, record)
    save_records(records, results_path)
    print(group, seed, prompt_id[:8], record["status"], record.get("seconds"),
          record.get("files"), record.get("error"), flush=True)
    return record


def has_unrecorded(group, seeds, path=RESULTS):
    records = load_records(path)
    return any(find_record(records, group, seed) is None for seed in seeds)


if __name__ == "__main__":
    groups = sys.argv[1:] or ["chain", "cross"]
    chain_seeds = (2026091311, 2026091312, 2026091313)
    if "chain" in groups:
        staged_file = ""
        if has_unrecorded("chain", chain_seeds):
            staged = post_studio("/api/assets/reference", {"id": DEPTH_OUTPUT_ASSET})
            staged_file = staged["file"]
            print("staged depth output as", staged_file, flush=True)
        for requested_seed in chain_seeds:
            run("chain", staged_file, PORTRAIT, requested_seed)
    if "cross" in groups:
        for requested_seed in (2026091321, 2026091322):
            run("cross", FULLBODY, SHARK, requested_seed)