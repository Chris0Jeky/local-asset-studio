# NSFW lab media policy — 21 September 2026

`ORCHESTRATOR.md` is the plan, `FINDINGS.md` is the inspection record. This file says where the
pictures are and how to get them back, because they are deliberately not in Git.

Generated is not accepted art and not licence clearance. Catalog `verified` stays false on every
preset this lab touched. No owner creative item is ticked by this work.

## The rule

The lab produced 148 contact JPEGs: 118 in `examples/nsfw-lab/` and 30 in `examples/civitai-intake/`,
17.3 MB in total. The owner decided they must not be uploaded to GitHub, but must stay easy to find
and to look at on this PC. So:

- `.gitignore` refuses `*.jpg`, `*.jpeg`, `*.png`, `*.webp` and the generated `index.html` in both folders.
- `examples/<folder>/MANIFEST.json` **is** tracked and is the record: per picture, the id, file name,
  sha256, byte count, pixel size, job id, prompt id, cell or recipe id, the source PNG relative to the
  ComfyUI output folder, and the one-line inspection note from `FINDINGS.md` or the intake `README.md`.
- The Studio keeps showing them anyway: `/api/examples/<path>` is served straight from `<repo>/examples/`
  on disk, so a gitignored file still renders in the gallery and in Creative Bundles.
- `presets/nsfw-intel.json` also carries the job id per example and a `media` block repeating this policy.

The Grok branch `grok/nsfw-hentai-lab`, which does contain the 148 blobs in its history, is to be
deleted from `origin` once this work has landed. Delete it there and keep the local copy only if you
want a second restore source; `scripts/lab-media.py restore --from-ref <ref>` can read from any ref
that still has the bytes.

## Working with the pictures

```bash
python scripts/lab-media.py verify                     # every manifest entry present and hash-matching
python scripts/lab-media.py restore                    # rebuild missing/changed files from the job PNGs
python scripts/lab-media.py restore --from-ref <ref>   # or take the exact bytes from a git ref
python scripts/lab-media.py index                      # write examples/<folder>/index.html and open it
```

`restore` from a PNG re-encodes with Pillow at quality 85 with `optimize`, which reproduces the recorded
sha256 byte for byte — 147 of the 148 were re-proved that way on 21 September 2026, and the 148th
(`b-hairless`) was identified by the same re-encode test after its job record was ambiguous. A rebuilt
file that does not match its manifest hash is reported and **not** written.

`index` writes a local, gitignored contact sheet per folder: thumbnail, id, note, job id, prompt id,
file path and source PNG, with a labelled placeholder where a file is missing. The Studio gallery
(`/static/nsfw-lab.html`) degrades the same way — a missing picture becomes a tile naming the cell, the
job and the restore command, never a broken image.

`scripts/validate-repo.py` refuses a `/api/examples/nsfw-lab/...` or `/api/examples/civitai-intake/...`
reference that has no manifest entry, and refuses any image binary tracked under those two folders. It
does not require the files to exist, so CI and a fresh clone are green with no pictures at all.

## Source PNGs

The JPEGs are downscales of Studio job outputs. The PNGs themselves live under the ComfyUI output
folder (`comfy_root` in `config/local.json`, `C:/AI/ComfyUI_windows_portable/ComfyUI/output` on this
PC); the owning Studio job record is `experiments_root/runs/<job_id>/state.json`, which also holds the
submitted graph. Both are outside Git by design. If the ComfyUI output folder is ever cleared, the
manifest hashes still identify what was lost and `--from-ref` is the remaining restore path.

## Franchise characters: what the plan said and what happened

`ORCHESTRATOR.md` was written with a hard rule "No named franchise characters, no real people". Waves
C and onwards did not follow it: they use adult-coded Danbooru character tags (2B, Kafka, Darkness,
Aqua, Cynthia, Asuna, Yelan, Raiden, Tifa), `presets/wildcards/nsfw_character.txt` lists them, and
they appear in `FINDINGS.md`, in `presets/nsfw-intel.json` and in the manifests. The no-real-people and
adult-only parts of the rule were kept: Megumin and child-coded franchise tags were explicitly skipped.
Nothing has been deleted here — the record now says what actually ran. Whether the lab should use
named franchise characters at all is an owner decision, raised in `HUMAN_TODO.md`, not one an agent
takes.
