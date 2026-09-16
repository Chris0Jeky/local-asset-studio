"""Fantasy pack, full body that keeps the face (16 September 2026, research straight against ComfyUI, not a Studio recipe yet):
the round-three `replace-character` LoRA (replace_character_v1_klein, pinned) with image 1 = the batch's full-body render (pose, camera,
composition, background kept) and image 2 = the batch's portrait (the face to keep), on the shipped 9B pose-first graph. Three seeds.
Evidence: pack_replacechar.json next to this file (prompt IDs, timing, outputs); graphs live under research-graphs/.

Every accepted prompt ID is persisted before polling. Re-running resumes an interrupted submitted or timed-out prompt and skips
terminal records, so an expensive seed is never intentionally submitted twice."""
import copy
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
COMFY = "http://127.0.0.1:8188"
RESULTS = OUT / "pack_replacechar.json"
GRAPH_DIR = OUT / "research-graphs"
FULLBODY = "9c880763266a454091725b57ad392762_Anima-v1-Baseline_00005_.png.png"
PORTRAIT = "aa93fb465e364532a33d40dfb21894a9_Anima-v1-Baseline_00004_.png.png"
TEXT = ("Replace the woman in image 1 with the woman in image 2, while keeping the same pose, action, camera angle, composition, background "
        "and lighting as in image 1. The woman in image 2 has long centre-parted dark hair, brown eyes, a calm face and small gold earrings; keep "
        "her face, hair and expression exactly as in image 2. She wears image 1's clothes: a navy double-breasted travelling coat with brass buttons, "
        "a teal scarf, dark trousers, brown lace-up boots, holding a brass lantern, a leather satchel on a strap. Keep image 1's painterly "
        "rendering and its station platform. One figure only, nobody else in the picture.")
BASE = json.loads((ROOT / "workflows/api/combine-klein-9b-api.json").read_text(encoding="utf-8"))


def load_records(path=RESULTS):
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Research receipt must be a JSON array: {path}")
    return value


def save_records(records, path=RESULTS):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def upsert(records, record):
    for index, current in enumerate(records):
        if current.get("variant") == record["variant"] and current.get("seed") == record["seed"]:
            records[index] = record
            return
    records.append(record)


def build(seed):
    graph = copy.deepcopy(BASE)
    graph["14"]["inputs"]["image"] = FULLBODY
    graph["20"]["inputs"]["image"] = PORTRAIT
    graph["40"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "replace_character_v1_klein.safetensors", "strength_model": 1.0, "model": ["1", 0]}}
    graph["6"]["inputs"]["model"] = ["40", 0]
    graph["4"]["inputs"]["text"] = TEXT
    graph["7"]["inputs"]["noise_seed"] = seed
    graph["9"]["inputs"]["width"] = graph["10"]["inputs"]["width"] = 832
    graph["9"]["inputs"]["height"] = graph["10"]["inputs"]["height"] = 1216
    graph["13"]["inputs"]["filename_prefix"] = "Research/pack-replacechar"
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


def run(seed, *, results_path=RESULTS, graph_dir=GRAPH_DIR,
        open_url=urllib.request.urlopen, clock=time.time, sleeper=time.sleep):
    records = load_records(results_path)
    record = next((item for item in records
                   if item.get("variant") == "replacechar" and item.get("seed") == seed), None)
    if record and record.get("status") not in {"submitted", "timeout"}:
        print("skip", "replacechar", seed, "(recorded)", flush=True)
        return record

    if record:
        record = dict(record)
        prompt_id = record["prompt_id"]
        submitted_at = float(record["submitted_at"]) if "submitted_at" in record else clock()
    else:
        graph = build(seed)
        graph_dir.mkdir(parents=True, exist_ok=True)
        (graph_dir / f"pack-replacechar-{seed}.graph.json").write_text(
            json.dumps(graph, indent=1) + "\n", encoding="utf-8")
        request = urllib.request.Request(COMFY + "/prompt",
                                         json.dumps({"prompt": graph}).encode(),
                                         {"Content-Type": "application/json"})
        prompt_id = json.load(open_url(request, timeout=60))["prompt_id"]
        submitted_at = clock()
        record = {"variant": "replacechar", "seed": seed,
                  "prompt_id": prompt_id, "status": "submitted",
                  "submitted_at": submitted_at, "image1": FULLBODY,
                  "image2": PORTRAIT, "text": TEXT,
                  "lora": "replace_character_v1_klein.safetensors"}
        upsert(records, record)
        save_records(records, results_path)

    record.update(poll(prompt_id, submitted_at, open_url=open_url,
                       clock=clock, sleeper=sleeper))
    upsert(records, record)
    save_records(records, results_path)
    print("replacechar", seed, prompt_id[:8], record["status"],
          record.get("seconds"), record.get("files"), record.get("error"), flush=True)
    return record


if __name__ == "__main__":
    for requested_seed in [int(value) for value in (sys.argv[1:] or
                           ["2026091301", "2026091302", "2026091303"])]:
        run(requested_seed)
